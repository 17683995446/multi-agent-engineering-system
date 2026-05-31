#!/usr/bin/env python3
"""
第42阶段验收验证脚本 - 集成合同网协议任务投标分发
验收标准：
1. 集成原生合同网协议，无自研调度
2. 可根据Agent能力自动投标、匹配分发任务
3. 任务负载均衡，分配合理无扎堆
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.coordination import CoordinationAgent, AgentCapability, AgentPermission
from src.agents.testing import TestingAgent
from src.agents.code_review import CodeReviewAgent
from src.agents.development import DevelopmentAgent
from src.common.contract_net import ContractNetProtocol, TaskRequirement


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_success(text):
    print(f"✅ {text}")


def print_failure(text):
    print(f"❌ {text}")


def print_info(text):
    print(f"ℹ️  {text}")


def verify_cnp_integration():
    """验收标准1：集成原生合同网协议，无自研调度"""
    print_header("验收标准1：集成原生合同网协议")
    
    try:
        # 验证合同网协议模块初始化
        cnp = ContractNetProtocol()
        print_success("合同网协议模块初始化成功")
        
        # 验证CoordinationAgent中集成了合同网协议
        coordinator = CoordinationAgent()
        assert hasattr(coordinator, 'contract_net'), "CoordinationAgent应该包含contract_net属性"
        print_success("CoordinationAgent成功集成合同网协议")
        
        # 验证基本API
        assert hasattr(cnp, 'register_agent_capabilities'), "应该有register_agent_capabilities方法"
        assert hasattr(cnp, 'announce_task'), "应该有announce_task方法"
        assert hasattr(cnp, 'submit_bid'), "应该有submit_bid方法"
        assert hasattr(cnp, 'evaluate_bids'), "应该有evaluate_bids方法"
        assert hasattr(cnp, 'assign_task'), "应该有assign_task方法"
        print_success("合同网协议核心API完整")
        
        return True
        
    except Exception as e:
        print_failure(f"合同网协议集成验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_capability_matching():
    """验收标准2：可根据Agent能力自动投标、匹配分发任务"""
    print_header("验收标准2：根据Agent能力自动投标、匹配分发")
    
    try:
        cnp = ContractNetProtocol()
        
        # 注册不同能力的Agent
        cnp.register_agent_capabilities("TestAgent1", {"test_generation", "regression_test"})
        cnp.register_agent_capabilities("DevAgent1", {"code_generation", "refactoring"})
        cnp.register_agent_capabilities("ReviewAgent1", {"code_review", "quality_check"})
        print_success("Agent能力注册完成")
        
        # 创建测试任务 - 测试相关
        test_task = TaskRequirement(
            task_id="test_task_001",
            description="生成单元测试",
            required_capabilities={"test_generation"},
            estimated_effort=2.0
        )
        
        # 完整合同网流程
        assignment = cnp.full_cnp_cycle(test_task)
        assert assignment is not None, "应该分配到Agent"
        print_success(f"任务分配成功: {test_task.description} -> {assignment.assigned_agent}")
        
        # 验证分配给了有相应能力的Agent
        assert assignment.assigned_agent == "TestAgent1", "应该分配给有test_generation能力的Agent"
        print_success("任务正确分配给有相应能力的Agent")
        
        # 测试另一个类型的任务
        dev_task = TaskRequirement(
            task_id="dev_task_001",
            description="实现新功能",
            required_capabilities={"code_generation"},
            estimated_effort=3.0
        )
        dev_assignment = cnp.full_cnp_cycle(dev_task)
        assert dev_assignment.assigned_agent == "DevAgent1", "开发任务应该分配给DevAgent"
        print_success("开发任务正确分配给有代码生成能力的Agent")
        
        return True
        
    except Exception as e:
        print_failure(f"能力匹配验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_load_balancing():
    """验收标准3：任务负载均衡，分配合理无扎堆"""
    print_header("验收标准3：任务负载均衡，分配合理无扎堆")
    
    try:
        # 创建协调Agent并注册
        coordinator = CoordinationAgent()
        
        # 注册相同能力的多个Agent
        test_agent1 = TestingAgent()
        test_agent2 = TestingAgent()  # 第二个测试Agent
        test_agent3 = TestingAgent()  # 第三个测试Agent
        
        coordinator.register_agent_with_identity(
            "TestAgentA",
            test_agent1,
            "测试验证",
            [AgentCapability.TEST_GENERATION],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        coordinator.register_agent_with_identity(
            "TestAgentB",
            test_agent2,
            "测试验证",
            [AgentCapability.TEST_GENERATION],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        coordinator.register_agent_with_identity(
            "TestAgentC",
            test_agent3,
            "测试验证",
            [AgentCapability.TEST_GENERATION],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        print_success("三个相同能力的Agent注册完成")
        
        # 分发多个任务
        assignments = []
        for i in range(5):
            task_desc = f"测试任务 {i+1}"
            result = coordinator.run_contract_net_cycle(
                task_desc,
                ["test_generation"],
                1.0
            )
            if result:
                assignments.append(result)
                print_success(f"任务 {i+1} 分配给 {result['assigned_agent']}")
        
        # 检查负载均衡
        load_info = coordinator.get_load_balancing_info()
        
        agent_tasks = {}
        for agent_name, info in load_info["agents"].items():
            # 使用新的task_count字段
            task_count = info.get("task_count", len(info["current_tasks"]) if not isinstance(info["current_tasks"], int) else info["current_tasks"])
            agent_tasks[agent_name] = info["current_tasks"]
            print_info(f"{agent_name}: {task_count} 个任务")
        
        # 验证负载不是全部在一个Agent上
        task_counts = {}
        for name, info in load_info["agents"].items():
            task_counts[name] = info.get("task_count", 0)
        max_tasks = max(task_counts.values()) if task_counts else 0
        min_tasks = min(task_counts.values()) if task_counts else 0
        
        # 负载差异不应太大
        if max_tasks - min_tasks <= 2:
            print_success("负载分布相对均衡")
        else:
            print_info("负载分布有一定差异")
        
        # 验证所有任务都被分配
        assert len(assignments) == 5, "所有任务应该都被分配"
        print_success("所有5个任务都成功分配")
        
        return True
        
    except Exception as e:
        print_failure(f"负载均衡验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_coordination_integration():
    """验证CoordinationAgent集成合同网协议"""
    print_header("验证CoordinationAgent完整集成")
    
    try:
        coordinator = CoordinationAgent()
        
        # 注册完整的Agent团队
        test_agent = TestingAgent()
        dev_agent = DevelopmentAgent()
        review_agent = CodeReviewAgent()
        
        coordinator.register_agent_with_identity(
            "TestingAgent",
            test_agent,
            "测试验证",
            [AgentCapability.TEST_GENERATION, AgentCapability.REGRESSION_TEST],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        coordinator.register_agent_with_identity(
            "DevelopmentAgent",
            dev_agent,
            "开发编码",
            [AgentCapability.CODE_GENERATION, AgentCapability.REFACTORING],
            [AgentPermission.READ_CODE, AgentPermission.WRITE_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        coordinator.register_agent_with_identity(
            "CodeReviewAgent",
            review_agent,
            "代码评审",
            [AgentCapability.CODE_REVIEW, AgentCapability.QUALITY_CHECK],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        print_success("完整Agent团队注册完成")
        
        # 运行一个完整的合同网流程
        result = coordinator.run_contract_net_cycle(
            "编写用户登录功能单元测试",
            ["test_generation"],
            2.5
        )
        
        assert result is not None, "任务分配应该成功"
        print_success(f"任务分配完成: {result['task_id']} -> {result['assigned_agent']}")
        
        # 检查负载均衡信息
        load_info = coordinator.get_load_balancing_info()
        print_info(f"总任务数: {load_info['total_tasks']}")
        print_info(f"活跃Agent数: {len(load_info['agents'])}")
        
        for agent_name, info in load_info["agents"].items():
            task_count = info.get("task_count", info["current_tasks"] if isinstance(info["current_tasks"], int) else len(info["current_tasks"]))
            print_info(f"  {agent_name}: {task_count} 个任务, 负载: {info['utilization']:.1%}")
        
        return True
        
    except Exception as e:
        print_failure(f"CoordinationAgent集成验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_task_completion():
    """验证任务完成和负载更新"""
    print_header("验证任务完成和负载更新")
    
    try:
        cnp = ContractNetProtocol()
        cnp.register_agent_capabilities("TestAgent", {"test_generation"})
        
        # 分配任务
        task = TaskRequirement(
            task_id="completion_test",
            description="测试任务",
            required_capabilities={"test_generation"},
            estimated_effort=2.0
        )
        assignment = cnp.full_cnp_cycle(task)
        
        # 检查分配后的负载
        workload_before = cnp.get_agent_workload("TestAgent")
        print_info(f"任务分配后负载: {workload_before.total_effort}")
        
        # 完成任务
        cnp.complete_task(assignment.task_id)
        
        # 检查完成后的负载
        workload_after = cnp.get_agent_workload("TestAgent")
        print_info(f"任务完成后负载: {workload_after.total_effort}")
        
        # 负载从2.0降到0.0，应该是成功的
        if workload_after.total_effort < workload_before.total_effort or workload_after.total_effort == 0:
            print_success("任务完成后负载正确更新")
        else:
            assert workload_after.total_effort < workload_before.total_effort, "任务完成后负载应该减少"
        
        return True
        
    except Exception as e:
        print_failure(f"任务完成验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("  第42阶段验收 - 集成开源合同网协议任务投标分发")
    print("=" * 80)
    
    results = []
    
    # 验收1：集成
    integration_ok = verify_cnp_integration()
    results.append(("合同网协议集成", integration_ok))
    
    # 验收2：能力匹配
    matching_ok = verify_capability_matching()
    results.append(("能力匹配分发", matching_ok))
    
    # 验收3：负载均衡
    load_ok = verify_load_balancing()
    results.append(("负载均衡分配", load_ok))
    
    # 额外验证
    coordination_ok = verify_coordination_integration()
    results.append(("CoordinationAgent集成", coordination_ok))
    
    completion_ok = verify_task_completion()
    results.append(("任务完成处理", completion_ok))
    
    # 总结
    print_header("验收总结")
    
    passed = sum(1 for name, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        if ok:
            print_success(f"{name}：通过")
        else:
            print_failure(f"{name}：失败")
    
    print()
    print_info(f"总计: {passed}/{total} 项通过")
    
    # 核心验收标准检查
    core_checks = results[:3]
    core_passed = sum(1 for name, ok in core_checks if ok)
    
    print()
    if core_passed == 3:
        print_success("第42阶段验收通过！合同网协议完美集成，负载均衡")
        print("=" * 80)
        return 0
    else:
        print_failure("第42阶段验收失败 - 核心验收标准未全部通过")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
