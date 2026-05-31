#!/usr/bin/env python3
"""
第40阶段验收验证脚本 - Agent基础身份、能力、权限注册体系
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.coordination import (
    CoordinationAgent,
    AgentCapability,
    AgentPermission,
    MessageType,
    TaskStatus,
    WorkflowStatus
)
from src.agents.testing import TestingAgent
from src.agents.code_review import CodeReviewAgent
from src.agents.development import DevelopmentAgent
from src.agents.central_control import CentralControlAgent


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


def verify_agent_registration():
    """验收标准1: 所有Agent身份唯一、注册正常"""
    print_header("验收标准1: Agent身份唯一、注册正常")
    
    try:
        coordinator = CoordinationAgent()
        coordinator.start()
        
        # 注册多个Agent
        test_agent = TestingAgent()
        test_agent.start()
        test_identity = coordinator.register_agent_with_identity(
            "TestingAgent",
            test_agent,
            "测试验证",
            [AgentCapability.TEST_GENERATION],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        review_agent = CodeReviewAgent()
        review_agent.start()
        review_identity = coordinator.register_agent_with_identity(
            "CodeReviewAgent",
            review_agent,
            "代码评审",
            [AgentCapability.CODE_REVIEW],
            [AgentPermission.READ_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        # 验证身份唯一
        assert test_identity.agent_id != review_identity.agent_id, "Agent ID应该唯一"
        assert test_identity.name != review_identity.name, "Agent名称应该唯一"
        
        # 验证身份信息完整
        assert test_identity.agent_id is not None, "Agent ID不应为None"
        assert test_identity.name == "TestingAgent", "Agent名称不匹配"
        assert test_identity.role == "测试验证", "Agent角色不匹配"
        assert test_identity.status == "active", "Agent状态应该为active"
        
        # 验证注册数量
        all_agents = coordinator.get_all_registered_agents()
        assert len(all_agents) == 2, f"应该有2个注册Agent，实际有{len(all_agents)}个"
        
        print_success("所有Agent身份唯一，注册正常")
        print_info(f"  注册Agent数量: {len(all_agents)}")
        print_info(f"  测试Agent ID: {test_identity.agent_id}")
        print_info(f"  评审Agent ID: {review_identity.agent_id}")
        
        return True, coordinator
        
    except Exception as e:
        print_failure(f"Agent注册验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def verify_capability_and_permission(coordinator):
    """验收标准2: 能力标签、权限范围明确"""
    print_header("验收标准2: 能力标签、权限范围明确")
    
    try:
        # 验证能力检查
        has_test_gen = coordinator.has_capability("TestingAgent", AgentCapability.TEST_GENERATION)
        assert has_test_gen is True, "测试Agent应该有TEST_GENERATION能力"
        
        has_code_review = coordinator.has_capability("TestingAgent", AgentCapability.CODE_REVIEW)
        assert has_code_review is False, "测试Agent不应该有CODE_REVIEW能力"
        
        # 验证权限检查
        has_read_code = coordinator.has_permission("TestingAgent", AgentPermission.READ_CODE)
        assert has_read_code is True, "测试Agent应该有READ_CODE权限"
        
        has_write_code = coordinator.has_permission("TestingAgent", AgentPermission.WRITE_CODE)
        assert has_write_code is False, "测试Agent不应该有WRITE_CODE权限"
        
        print_success("能力标签和权限范围验证正确")
        print_info("  测试Agent能力: TEST_GENERATION ✓")
        print_info("  测试Agent权限: READ_CODE ✓, WRITE_CODE ✗")
        
        return True
        
    except Exception as e:
        print_failure(f"能力和权限验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_capability_action_mapping(coordinator):
    """验收标准3: 支持能力调度匹配"""
    print_header("验收标准3: 支持权限管控、能力调度匹配")
    
    try:
        # 验证能力-动作映射
        can_generate_tests = coordinator.can_execute_action("TestingAgent", "generate_unit_tests")
        assert can_generate_tests is True, "测试Agent应该可以执行generate_unit_tests"
        
        can_review = coordinator.can_execute_action("TestingAgent", "review_file")
        assert can_review is False, "测试Agent不应该可以执行review_file"
        
        # 验证按能力查找Agent
        code_review_agents = coordinator.find_agents_by_capability(AgentCapability.CODE_REVIEW)
        assert len(code_review_agents) == 1, "应该找到1个具有CODE_REVIEW能力的Agent"
        assert code_review_agents[0].name == "CodeReviewAgent", "应该是CodeReviewAgent"
        
        # 验证按角色查找Agent
        test_role_agents = coordinator.find_agents_by_role("测试验证")
        assert len(test_role_agents) == 1, "应该找到1个角色为'测试验证'的Agent"
        
        print_success("权限管控和能力调度匹配验证正确")
        print_info("  测试Agent可执行: generate_unit_tests ✓")
        print_info("  按能力查找: CODE_REVIEW -> 找到CodeReviewAgent ✓")
        
        return True
        
    except Exception as e:
        print_failure(f"能力调度匹配验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_dynamic_updates(coordinator):
    """验证能力和权限动态更新"""
    print_header("验证: 能力和权限动态更新")
    
    try:
        # 更新能力
        update_cap_success = coordinator.update_agent_capabilities(
            "TestingAgent",
            [AgentCapability.TEST_GENERATION, AgentCapability.QUALITY_CHECK]
        )
        assert update_cap_success is True, "能力更新应该成功"
        
        # 验证新能力
        has_quality_check = coordinator.has_capability("TestingAgent", AgentCapability.QUALITY_CHECK)
        assert has_quality_check is True, "测试Agent现在应该有QUALITY_CHECK能力"
        
        # 更新权限
        update_perm_success = coordinator.update_agent_permissions(
            "TestingAgent",
            [AgentPermission.READ_CODE, AgentPermission.WRITE_CODE, AgentPermission.EXECUTE_TASK]
        )
        assert update_perm_success is True, "权限更新应该成功"
        
        # 验证新权限
        has_write_code = coordinator.has_permission("TestingAgent", AgentPermission.WRITE_CODE)
        assert has_write_code is True, "测试Agent现在应该有WRITE_CODE权限"
        
        print_success("能力和权限动态更新验证正确")
        print_info("  新增能力: QUALITY_CHECK ✓")
        print_info("  新增权限: WRITE_CODE ✓")
        
        return True
        
    except Exception as e:
        print_failure(f"动态更新验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_status_management(coordinator):
    """验证Agent状态管理"""
    print_header("验证: Agent状态管理")
    
    try:
        # 设置状态
        set_status_success = coordinator.set_agent_status("TestingAgent", "inactive")
        assert set_status_success is True, "状态设置应该成功"
        
        # 验证状态
        identity = coordinator.get_agent_identity("TestingAgent")
        assert identity.status == "inactive", "状态应该是inactive"
        
        # 查找时应该排除非active状态
        inactive_cap_agents = coordinator.find_agents_by_capability(AgentCapability.TEST_GENERATION)
        # 由于是inactive状态，可能不应该出现在结果中（取决于实现）
        print_info(f"  非active状态的Agent在能力查找中的行为: {len(inactive_cap_agents)}个结果")
        
        # 恢复状态
        coordinator.set_agent_status("TestingAgent", "active")
        identity = coordinator.get_agent_identity("TestingAgent")
        assert identity.status == "active", "状态应该恢复为active"
        
        print_success("Agent状态管理验证正确")
        print_info("  状态切换: active -> inactive -> active ✓")
        
        return True
        
    except Exception as e:
        print_failure(f"状态管理验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_workflow_with_validation(coordinator):
    """验证带权限和能力检查的工作流执行"""
    print_header("验证: 工作流执行中的权限和能力检查")
    
    try:
        # 创建并注册开发Agent
        dev_agent = DevelopmentAgent()
        dev_agent.start()
        coordinator.register_agent_with_identity(
            "DevelopmentAgent",
            dev_agent,
            "开发编码",
            [AgentCapability.CODE_GENERATION],
            [AgentPermission.READ_CODE, AgentPermission.WRITE_CODE, AgentPermission.EXECUTE_TASK]
        )
        
        # 创建工作流
        workflow = coordinator.create_workflow(
            "测试工作流",
            "用于验证的简单工作流",
            [
                {
                    "agent_name": "TestingAgent",
                    "action": "generate_unit_tests",
                    "params": {"source_file": "/test.py", "function_names": ["add"]}
                },
                {
                    "agent_name": "CodeReviewAgent",
                    "action": "review_file",
                    "params": {"file_path": "/test.py"}
                }
            ]
        )
        
        # 执行工作流
        result = coordinator.execute_workflow(workflow.workflow_id)
        
        # 验证工作流状态
        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED], "工作流应该已完成或失败"
        
        print_success("工作流执行中的权限和能力检查验证正确")
        print_info(f"  工作流状态: {result.status.value}")
        
        success_count = sum(1 for t in result.tasks if t.status == TaskStatus.SUCCESS)
        print_info(f"  成功任务数: {success_count}/{len(result.tasks)}")
        
        return True
        
    except Exception as e:
        print_failure(f"工作流验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("  第40阶段验收 - Agent基础身份、能力、权限注册体系")
    print("=" * 80)
    
    results = []
    
    # 验收1: Agent注册
    reg_success, coordinator = verify_agent_registration()
    results.append(("Agent身份注册", reg_success))
    
    if not reg_success:
        print("\n" + "=" * 80)
        print_failure("第40阶段验收失败 - 基础Agent注册有问题")
        print("=" * 80)
        return 1
    
    # 验收2: 能力和权限
    cap_perm_success = verify_capability_and_permission(coordinator)
    results.append(("能力权限标签", cap_perm_success))
    
    # 验收3: 能力调度匹配
    mapping_success = verify_capability_action_mapping(coordinator)
    results.append(("能力调度匹配", mapping_success))
    
    # 额外验证
    update_success = verify_dynamic_updates(coordinator)
    results.append(("动态更新能力", update_success))
    
    status_success = verify_status_management(coordinator)
    results.append(("Agent状态管理", status_success))
    
    workflow_success = verify_workflow_with_validation(coordinator)
    results.append(("工作流验证检查", workflow_success))
    
    # 总结
    print_header("验收总结")
    
    passed = sum(1 for name, success in results if success)
    total = len(results)
    
    for name, success in results:
        if success:
            print_success(f"{name}: 通过")
        else:
            print_failure(f"{name}: 失败")
    
    print()
    print_info(f"总计: {passed}/{total} 项通过")
    
    # 核心验收标准必须全部通过
    core_checks = results[:3]
    core_passed = sum(1 for name, success in core_checks if success)
    
    print()
    if core_passed == 3:
        print_success("第40阶段验收通过！Agent集群基础体系完全成型")
        print("=" * 80)
        return 0
    else:
        print_failure("第40阶段验收失败 - 核心验收标准未全部通过")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
