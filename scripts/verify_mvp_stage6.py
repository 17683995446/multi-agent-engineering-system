#!/usr/bin/env python3
"""
MVP阶段6验证脚本：协调Agent与工作流

测试项：
1. 协调Agent初始化
2. 工作流定义
3. 任务依赖管理
4. 工作流执行（串行/并行）
5. 多Agent协调
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mvp_core.coordination_agent import (
    CoordinationAgent,
    Workflow,
    WorkflowExecutor,
    WorkflowStatus,
)
from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus
from src.mvp_core.htd_decomposer import TaskStatus


class FakeAgent(AgentBase):
    """用于测试的模拟Agent"""

    def __init__(self, name: str):
        super().__init__(name)
        self.executed_tasks: list = []

    def execute(self, task: dict) -> dict:
        self.status = AgentStatus.BUSY
        self.executed_tasks.append(task)
        # 模拟执行耗时
        time.sleep(0.01)
        self.status = AgentStatus.IDLE
        return {
            "agent": self.name,
            "task_id": task.get("task_id"),
            "result": f"executed_by_{self.name}",
        }


def test_coordination_agent_init():
    """测试1: 协调Agent初始化"""
    print("=" * 50)
    print("测试1: 协调Agent初始化")
    print("=" * 50)

    bus = MessageBus("test_bus")
    agent = CoordinationAgent(name="test_coordination", message_bus=bus)
    assert agent.name == "test_coordination"
    assert agent.decomposer is not None
    assert agent.executor is not None
    assert len(agent.workflows) == 0
    assert len(agent.get_registered_agents()) == 0

    status = agent.get_status()
    assert status["name"] == "test_coordination"
    assert status["workflow_count"] == 0
    assert status["agent_count"] == 0

    print("✅ 协调Agent初始化通过")
    return True


def test_workflow_definition():
    """测试2: 工作流定义"""
    print("=" * 50)
    print("测试2: 工作流定义")
    print("=" * 50)

    workflow = Workflow(name="test_workflow", description="测试工作流")
    assert workflow.workflow_id is not None
    assert workflow.name == "test_workflow"
    assert workflow.status == WorkflowStatus.PENDING

    # 添加任务
    t1 = workflow.add_task("t1", "任务1", "第一个任务")
    t2 = workflow.add_task("t2", "任务2", "第二个任务")
    t3 = workflow.add_task("t3", "任务3", "第三个任务")

    assert len(workflow.tasks) == 3
    assert workflow.get_task("t1").name == "任务1"

    # 重复添加应抛出异常
    try:
        workflow.add_task("t1", "重复任务")
        assert False, "应抛出ValueError"
    except ValueError:
        pass

    # 移除任务
    assert workflow.remove_task("t3") is True
    assert workflow.remove_task("t3") is False
    assert len(workflow.tasks) == 2

    print("✅ 工作流定义测试通过")
    return True


def test_task_dependency_management():
    """测试3: 任务依赖管理"""
    print("=" * 50)
    print("测试3: 任务依赖管理")
    print("=" * 50)

    workflow = Workflow(name="dependency_test")

    workflow.add_task("a", "任务A")
    workflow.add_task("b", "任务B")
    workflow.add_task("c", "任务C")
    workflow.add_task("d", "任务D")

    # 设置依赖: B->A, C->A, D->B,C
    workflow.add_dependency("b", "a")
    workflow.add_dependency("c", "a")
    workflow.add_dependency("d", "b")
    workflow.add_dependency("d", "c")

    # 验证拓扑排序
    levels = workflow.topological_sort()
    assert len(levels) == 3
    assert levels[0] == ["a"]
    assert sorted(levels[1]) == ["b", "c"]
    assert levels[2] == ["d"]

    # 验证工作流有效性
    valid, error = workflow.validate()
    assert valid is True
    assert error is None

    # 循环依赖检测
    bad = Workflow(name="circular")
    bad.add_task("x", "X")
    bad.add_task("y", "Y")
    bad.add_dependency("x", "y")
    bad.add_dependency("y", "x")
    try:
        bad.topological_sort()
        assert False, "应检测到循环依赖"
    except ValueError as e:
        assert "循环依赖" in str(e)

    # 依赖不存在
    assert workflow.add_dependency("b", "nonexistent") is False

    # 自依赖
    assert workflow.add_dependency("a", "a") is False

    # 移除有依赖的任务应失败
    assert workflow.remove_task("a") is False

    print("✅ 任务依赖管理测试通过")
    return True


def test_workflow_execution():
    """测试4: 工作流执行（串行/并行）"""
    print("=" * 50)
    print("测试4: 工作流执行")
    print("=" * 50)

    # 串行执行
    workflow = Workflow(name="serial_test")
    workflow.add_task("s1", "串行1")
    workflow.add_task("s2", "串行2", dependencies=["s1"])
    workflow.add_task("s3", "串行3", dependencies=["s2"])

    executor = WorkflowExecutor()
    result = executor.execute(workflow, parallel=False)
    assert result["success"] is True
    assert workflow.status == WorkflowStatus.COMPLETED
    assert len(result["results"]) == 3

    # 并行执行
    pworkflow = Workflow(name="parallel_test")
    pworkflow.add_task("p1", "并行1")
    pworkflow.add_task("p2", "并行2")
    pworkflow.add_task("p3", "并行3", dependencies=["p1", "p2"])

    pexecutor = WorkflowExecutor()
    presult = pexecutor.execute(pworkflow, parallel=True)
    assert presult["success"] is True
    assert pworkflow.status == WorkflowStatus.COMPLETED
    assert len(presult["results"]) == 3

    # 验证任务状态
    for task in pworkflow.tasks.values():
        assert task.status == TaskStatus.COMPLETED

    print("✅ 工作流执行测试通过")
    return True


def test_multi_agent_coordination():
    """测试5: 多Agent协调"""
    print("=" * 50)
    print("测试5: 多Agent协调")
    print("=" * 50)

    bus = MessageBus("coordination_bus")
    coord = CoordinationAgent(name="coordinator", message_bus=bus)

    # 创建模拟Agent
    dev_agent = FakeAgent("dev_agent")
    test_agent = FakeAgent("test_agent")
    review_agent = FakeAgent("review_agent")

    # 注册Agent
    assert coord.register_agent(dev_agent) is True
    assert coord.register_agent(test_agent) is True
    assert coord.register_agent(review_agent) is True
    assert coord.register_agent(dev_agent) is False  # 重复注册

    agents = coord.get_registered_agents()
    assert sorted(agents) == ["dev_agent", "review_agent", "test_agent"]

    # 创建工作流并分配Agent
    workflow = coord.create_workflow(name="dev_workflow")
    workflow.add_task("analysis", "需求分析", agent_name="dev_agent")
    workflow.add_task("design", "架构设计", agent_name="dev_agent", dependencies=["analysis"])
    workflow.add_task("coding", "编码实现", agent_name="dev_agent", dependencies=["design"])
    workflow.add_task("testing", "单元测试", agent_name="test_agent", dependencies=["coding"])
    workflow.add_task("review", "代码审查", agent_name="review_agent", dependencies=["coding"])

    # 执行工作流
    result = coord.execute_workflow(workflow, parallel=True)
    assert result["success"] is True
    assert workflow.status == WorkflowStatus.COMPLETED

    # 验证各Agent执行了任务
    assert len(dev_agent.executed_tasks) == 3  # analysis, design, coding
    assert len(test_agent.executed_tasks) == 1  # testing
    assert len(review_agent.executed_tasks) == 1  # review

    # 注销Agent
    assert coord.unregister_agent("test_agent") is True
    assert coord.unregister_agent("test_agent") is False
    assert "test_agent" not in coord.get_registered_agents()

    # 通过execute接口执行任务
    status_result = coord.execute({"type": "get_status"})
    assert status_result["agent_count"] == 2
    assert status_result["workflow_count"] == 1

    print("✅ 多Agent协调测试通过")
    return True


def test_decompose_requirement():
    """测试6: 需求分解为工作流"""
    print("=" * 50)
    print("测试6: 需求分解为工作流")
    print("=" * 50)

    coord = CoordinationAgent(name="decompose_coord")
    result = coord.execute({
        "type": "decompose_requirement",
        "requirement": "实现用户登录功能",
    })
    assert result["success"] is True
    assert "workflow_id" in result

    workflow_id = result["workflow_id"]
    workflow = coord.get_workflow(workflow_id)
    assert workflow is not None
    assert len(workflow.tasks) > 0

    # 验证工作流可以执行
    exec_result = coord.execute({
        "type": "execute_workflow",
        "workflow_id": workflow_id,
        "parallel": True,
    })
    assert exec_result["success"] is True

    print("✅ 需求分解为工作流测试通过")
    return True


def test_workflow_to_dict():
    """测试7: 工作流序列化"""
    print("=" * 50)
    print("测试7: 工作流序列化")
    print("=" * 50)

    workflow = Workflow(name="dict_test", description="测试序列化")
    workflow.add_task("t1", "任务1", agent_name="agent_a")
    workflow.add_task("t2", "任务2", dependencies=["t1"])

    data = workflow.to_dict()
    assert data["name"] == "dict_test"
    assert data["status"] == "pending"
    assert "tasks" in data
    assert "t1" in data["tasks"]
    assert data["tasks"]["t1"]["agent_name"] == "agent_a"

    print("✅ 工作流序列化测试通过")
    return True


def main():
    print("\n" + "=" * 50)
    print("MVP阶段6验证: 协调Agent与工作流")
    print("=" * 50 + "\n")

    tests = [
        test_coordination_agent_init,
        test_workflow_definition,
        test_task_dependency_management,
        test_workflow_execution,
        test_multi_agent_coordination,
        test_decompose_requirement,
        test_workflow_to_dict,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test.__name__} 失败")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} 异常: {e}")
            import traceback
            traceback.print_exc()
        print()

    print("=" * 50)
    print(f"验证结果: 通过 {passed} / 失败 {failed}")
    print("=" * 50)

    if failed > 0:
        sys.exit(1)
    else:
        print("🎉 MVP阶段6验证全部通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()
