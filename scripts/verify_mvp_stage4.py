"""
MVP阶段4验证脚本：中央控制Agent
测试内容：
1. 中央控制Agent初始化
2. 任务接收与分解
3. 任务分发
4. 状态跟踪
5. 结果汇总
"""

import sys
import os
import time

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mvp_core.central_control import (
    CentralControlAgent,
    TaskDispatcher,
    TaskType,
    ExecutionStatus
)
from src.mvp_core.agent_base import AgentBase, MessageBus, AgentStatus
from src.mvp_core.htd_decomposer import HTDDecomposer, TaskStatus


class MockAgent(AgentBase):
    """模拟Agent，用于测试"""

    def __init__(self, name: str, message_bus=None):
        super().__init__(name, message_bus)
        self.executed_tasks = []

    def execute(self, task: dict) -> dict:
        self.executed_tasks.append(task)
        self.status = AgentStatus.BUSY
        result = {"agent": self.name, "task": task.get("task_id"), "status": "done"}
        self.status = AgentStatus.IDLE
        return result


def test_initialization():
    """测试1: 中央控制Agent初始化"""
    print("\n" + "=" * 60)
    print("测试1: 中央控制Agent初始化")
    print("=" * 60)

    # 1.1 基础初始化
    cca = CentralControlAgent(name="test_cca")
    assert cca.name == "test_cca"
    assert cca.decomposer is not None
    assert cca.dispatcher is not None
    print("✓ 基础初始化成功")

    # 1.2 带MessageBus初始化
    bus = MessageBus("test_bus")
    cca2 = CentralControlAgent(name="test_cca2", message_bus=bus)
    assert cca2.message_bus == bus
    print("✓ 带MessageBus初始化成功")

    # 1.3 自定义Decomposer和Dispatcher
    decomposer = HTDDecomposer(name="custom_decomposer")
    dispatcher = TaskDispatcher()
    cca3 = CentralControlAgent(
        name="test_cca3",
        decomposer=decomposer,
        dispatcher=dispatcher
    )
    assert cca3.decomposer.name == "custom_decomposer"
    assert cca3.dispatcher is dispatcher
    print("✓ 自定义组件初始化成功")

    # 1.4 状态检查
    status = cca.get_status()
    assert status["name"] == "test_cca"
    assert status["executions_count"] == 0
    assert status["dispatcher_agents"] == []
    print("✓ 初始状态正确")

    print("\n测试1通过 ✓")
    return True


def test_task_receive_and_decompose():
    """测试2: 任务接收与分解"""
    print("\n" + "=" * 60)
    print("测试2: 任务接收与分解")
    print("=" * 60)

    cca = CentralControlAgent(name="cca_decompose")

    # 2.1 接收任务
    requirement = "实现用户登录功能"
    execution_id = cca.receive_task(requirement)
    assert execution_id is not None
    assert len(execution_id) > 0
    print(f"✓ 任务接收成功，执行ID: {execution_id}")

    # 2.2 检查执行记录
    history = cca.get_execution_history()
    assert len(history) == 1
    assert history[0]["requirement"] == requirement
    assert history[0]["status"] == ExecutionStatus.PENDING.value
    print("✓ 执行记录正确")

    # 2.3 分解任务
    success = cca.decompose_task(execution_id)
    assert success is True
    print("✓ 任务分解成功")

    # 2.4 检查分解后的状态
    history = cca.get_execution_history()
    assert history[0]["task_count"] > 1  # 应该有子任务
    print(f"✓ 分解后任务数: {history[0]['task_count']}")

    # 2.5 测试不同需求类型的分解
    test_cases = [
        ("编写单元测试", "testing"),
        ("编写API文档", "documentation"),
        ("重构代码", "refactoring"),
        ("实现新功能", "development"),
    ]

    for req, expected_type in test_cases:
        eid = cca.receive_task(req)
        cca.decompose_task(eid)
        task_type = cca._detect_task_type(req)
        assert task_type.value == expected_type, f"需求 '{req}' 类型检测错误"
        print(f"✓ 需求类型检测: '{req[:10]}...' -> {task_type.value}")

    print("\n测试2通过 ✓")
    return True


def test_task_dispatch():
    """测试3: 任务分发"""
    print("\n" + "=" * 60)
    print("测试3: 任务分发")
    print("=" * 60)

    bus = MessageBus("dispatch_bus")
    cca = CentralControlAgent(name="cca_dispatch", message_bus=bus)

    # 3.1 注册模拟Agent
    dev_agent = MockAgent("dev_agent", bus)
    test_agent = MockAgent("test_agent", bus)
    doc_agent = MockAgent("doc_agent", bus)

    cca.dispatcher.register_agent(dev_agent, [TaskType.DEVELOPMENT], is_default=True)
    cca.dispatcher.register_agent(test_agent, [TaskType.TESTING])
    cca.dispatcher.register_agent(doc_agent, [TaskType.DOCUMENTATION])

    assert len(cca.dispatcher.get_registered_agents()) == 3
    print("✓ Agent注册成功")

    # 3.2 分发开发任务
    req = "实现订单管理模块"
    eid = cca.receive_task(req)
    cca.decompose_task(eid)
    dispatch_map = cca.dispatch_tasks(eid)

    assert len(dispatch_map) > 0
    for task_id, agent_name in dispatch_map.items():
        assert agent_name == "dev_agent"  # 开发任务应分发给dev_agent
    print(f"✓ 开发任务分发正确，共 {len(dispatch_map)} 个子任务")

    # 3.3 分发测试任务
    req2 = "编写单元测试用例"
    eid2 = cca.receive_task(req2)
    cca.decompose_task(eid2)
    dispatch_map2 = cca.dispatch_tasks(eid2)

    for task_id, agent_name in dispatch_map2.items():
        assert agent_name == "test_agent"
    print(f"✓ 测试任务分发正确，共 {len(dispatch_map2)} 个子任务")

    # 3.4 无可用Agent的情况
    cca2 = CentralControlAgent(name="cca_no_agent")
    eid3 = cca2.receive_task("通用任务")
    cca2.decompose_task(eid3)
    dispatch_map3 = cca2.dispatch_tasks(eid3)
    assert len(dispatch_map3) == 0  # 没有注册Agent，无法分发
    print("✓ 无可用Agent时分发为空")

    # 3.5 Agent注销
    cca.dispatcher.unregister_agent("doc_agent")
    assert "doc_agent" not in cca.dispatcher.get_registered_agents()
    print("✓ Agent注销成功")

    print("\n测试3通过 ✓")
    return True


def test_status_tracking():
    """测试4: 状态跟踪"""
    print("\n" + "=" * 60)
    print("测试4: 状态跟踪")
    print("=" * 60)

    cca = CentralControlAgent(name="cca_track")

    # 4.1 跟踪不存在的执行
    status = cca.track_execution("nonexistent")
    assert "error" in status
    print("✓ 跟踪不存在的执行返回错误")

    # 4.2 完整执行流程跟踪
    eid = cca.receive_task("实现支付功能")

    # 初始状态
    status = cca.track_execution(eid)
    assert status["status"] == ExecutionStatus.PENDING.value
    assert status["progress"] == 0.0
    print("✓ 初始状态正确")

    # 分解后
    cca.decompose_task(eid)
    status = cca.track_execution(eid)
    assert status["status"] == ExecutionStatus.READY.value
    print("✓ 分解后状态正确")

    # 4.3 更新任务结果并跟踪
    record = cca._get_execution(eid)
    leaf_tasks = cca.decomposer.get_leaf_tasks(record.task_tree)

    # 更新部分任务为完成
    for i, leaf in enumerate(leaf_tasks[:2]):
        cca.update_task_result(eid, leaf.task_id, {"output": f"result_{i}"}, success=True)

    status = cca.track_execution(eid)
    assert status["completed_tasks"] == 2
    assert status["progress"] == 2 / len(leaf_tasks)
    print(f"✓ 部分完成跟踪正确: {status['completed_tasks']}/{status['total_tasks']}")

    # 更新任务为失败
    if len(leaf_tasks) > 2:
        cca.update_task_result(eid, leaf_tasks[2].task_id, {"error": "failed"}, success=False)
        status = cca.track_execution(eid)
        assert status["failed_tasks"] == 1
        print("✓ 失败任务跟踪正确")

    # 4.4 更新不存在的结果
    result = cca.update_task_result(eid, "nonexistent_task", {}, success=True)
    assert result is False
    print("✓ 更新不存在任务返回False")

    print("\n测试4通过 ✓")
    return True


def test_result_summary():
    """测试5: 结果汇总"""
    print("\n" + "=" * 60)
    print("测试5: 结果汇总")
    print("=" * 60)

    bus = MessageBus("summary_bus")
    cca = CentralControlAgent(name="cca_summary", message_bus=bus)

    dev_agent = MockAgent("dev_agent2", bus)
    cca.dispatcher.register_agent(dev_agent, [TaskType.DEVELOPMENT], is_default=True)

    # 5.1 完整执行流程
    req = "实现用户注册功能"
    result = cca.execute({"requirement": req})

    assert result["success"] is True
    assert result["requirement"] == req
    assert result["total_tasks"] > 0
    assert result["completed_tasks"] == result["total_tasks"]
    assert result["failed_tasks"] == 0
    assert "task_tree" in result
    assert "duration_seconds" in result
    print(f"✓ 完整执行汇总成功，总任务: {result['total_tasks']}")

    # 5.2 汇总不存在的执行
    summary = cca.summarize_results("nonexistent")
    assert summary["success"] is False
    print("✓ 汇总不存在的执行返回错误")

    # 5.3 执行历史
    history = cca.get_execution_history()
    assert len(history) >= 1
    print(f"✓ 执行历史记录数: {len(history)}")

    # 5.4 空需求测试
    empty_result = cca.execute({"requirement": ""})
    assert empty_result["success"] is False
    print("✓ 空需求处理正确")

    # 5.5 多执行记录
    cca.execute({"requirement": "任务A"})
    cca.execute({"requirement": "任务B"})
    history = cca.get_execution_history()
    assert len(history) >= 3
    print(f"✓ 多执行记录正确: {len(history)} 条")

    print("\n测试5通过 ✓")
    return True


def test_task_dispatcher():
    """测试6: TaskDispatcher独立测试"""
    print("\n" + "=" * 60)
    print("测试6: TaskDispatcher独立测试")
    print("=" * 60)

    dispatcher = TaskDispatcher()

    # 6.1 空分发器
    assert dispatcher.get_registered_agents() == []
    assert dispatcher.dispatch(None, TaskType.DEVELOPMENT) is None
    print("✓ 空分发器行为正确")

    # 6.2 注册和查询
    agent1 = MockAgent("agent1")
    agent2 = MockAgent("agent2")

    dispatcher.register_agent(agent1, [TaskType.DEVELOPMENT, TaskType.TESTING])
    dispatcher.register_agent(agent2, [TaskType.DOCUMENTATION], is_default=True)

    assert dispatcher.get_agents_by_type(TaskType.DEVELOPMENT) == ["agent1"]
    assert dispatcher.get_agents_by_type(TaskType.DOCUMENTATION) == ["agent2"]
    print("✓ Agent类型映射正确")

    # 6.3 重复注册
    result = dispatcher.register_agent(agent1, [TaskType.DEVELOPMENT])
    assert result is False
    print("✓ 重复注册返回False")

    # 6.4 获取Agent实例
    assert dispatcher.get_agent("agent1") == agent1
    assert dispatcher.get_agent("nonexistent") is None
    print("✓ Agent实例获取正确")

    print("\n测试6通过 ✓")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MVP阶段4验证: 中央控制Agent")
    print("=" * 60)

    tests = [
        ("初始化测试", test_initialization),
        ("任务接收与分解", test_task_receive_and_decompose),
        ("任务分发", test_task_dispatch),
        ("状态跟踪", test_status_tracking),
        ("结果汇总", test_result_summary),
        ("TaskDispatcher", test_task_dispatcher),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"\n✗ {name} 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    print(f"通过: {passed}/{len(tests)}")
    print(f"失败: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 所有测试通过！MVP阶段4完成。")
        return 0
    else:
        print("\n❌ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
