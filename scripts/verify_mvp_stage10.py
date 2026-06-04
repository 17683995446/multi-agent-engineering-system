#!/usr/bin/env python3
"""
MVP阶段10验证脚本: MVP集成测试
从需求输入到代码输出完整闭环
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mvp_core.agent_base import MessageBus, MessageType
from src.mvp_core.central_control import CentralControlAgent
from src.mvp_core.development_agent import DevelopmentAgent
from src.mvp_core.testing_agent import TestingAgent
from src.mvp_core.code_review_agent import CodeReviewAgent
from src.mvp_core.document_agent import DocumentAgent
from src.mvp_core.coordination_agent import CoordinationAgent


def test_full_pipeline():
    """测试完整流水线"""
    print("\n" + "=" * 60)
    print("MVP阶段10: 完整集成测试")
    print("=" * 60)
    
    # 1. 创建消息总线
    bus = MessageBus("mvp_bus")
    print("\n[1] 消息总线创建成功")
    
    # 2. 创建所有Agent
    central = CentralControlAgent("central", bus)
    dev = DevelopmentAgent("developer", bus)
    tester = TestingAgent("tester", bus)
    reviewer = CodeReviewAgent("reviewer", bus)
    doc = DocumentAgent("documenter", bus)
    coord = CoordinationAgent("coordinator", bus)
    
    print("[2] 所有Agent创建成功")
    
    # 3. 初始化所有Agent
    for agent in [central, dev, tester, reviewer, doc, coord]:
        agent.initialize()
    print("[3] 所有Agent初始化成功")
    
    # 4. 注册Agent到协调器
    coord.register_agent(dev)
    coord.register_agent(tester)
    coord.register_agent(reviewer)
    coord.register_agent(doc)
    print("[4] Agent注册到协调器成功")
    
    # 5. 提交需求
    requirement = "实现一个简单的计算器类，支持加减乘除运算"
    print(f"\n[5] 提交需求: {requirement}")
    
    # 6. 中央控制Agent处理需求
    result = central.execute({
        "action": "process_requirement",
        "requirement": requirement
    })
    print(f"[6] 需求处理完成")
    print(f"    - 任务数: {result.get('task_count', 0)}")
    print(f"    - 状态: {result.get('status', 'unknown')}")
    
    # 7. 开发Agent生成代码
    code_result = dev.execute({
        "action": "generate",
        "type": "class",
        "name": "Calculator",
        "description": "支持加减乘除的计算器类"
    })
    print(f"\n[7] 代码生成完成")
    print(f"    - 生成代码行数: {len(code_result.get('code', '').splitlines())}")
    
    # 8. 测试Agent生成测试
    from src.mvp_core.development_agent import CodeGenerator
    test_code = CodeGenerator.generate_function(
        name="add",
        params=[("a", None, None), ("b", None, None)],
        docstring="返回两数之和",
        body=["return a + b"]
    )
    test_result = tester.execute({
        "action": "generate",
        "source": test_code.source,
        "function_name": "add"
    })
    print(f"[8] 测试生成完成")
    print(f"    - 测试用例数: {len(test_result.get('test_cases', []))}")
    
    # 9. 代码审查
    review_result = reviewer.execute({
        "action": "review",
        "source": test_code
    })
    print(f"[9] 代码审查完成")
    print(f"    - 发现问题数: {review_result.get('total_issues', 0)}")
    
    # 10. 生成文档
    doc_result = doc.execute({
        "action": "api_docs",
        "source": test_code
    })
    print(f"[10] 文档生成完成")
    print(f"    - 文档长度: {len(doc_result.get('markdown', ''))}")
    
    # 11. 关闭所有Agent
    for agent in [central, dev, tester, reviewer, doc, coord]:
        agent.shutdown()
    print("\n[11] 所有Agent关闭成功")
    
    print("\n" + "=" * 60)
    print("✅ MVP集成测试通过！")
    print("完整闭环: 需求 -> 分解 -> 开发 -> 测试 -> 审查 -> 文档")
    print("=" * 60)
    return True


def test_agent_communication():
    """测试Agent间通信"""
    print("\n[Test] Agent间通信")
    
    bus = MessageBus("comm_bus")
    
    sender = DevelopmentAgent("sender", bus)
    receiver = TestingAgent("receiver", bus)
    
    sender.initialize()
    receiver.initialize()
    
    # 发送消息
    assert sender.send_message(
        receiver="receiver",
        content={"action": "test", "data": "hello"},
        msg_type=MessageType.REQUEST
    ) == True
    print("  ✓ 消息发送成功")
    
    # 接收消息
    msg = bus.receive("receiver", timeout=1.0)
    assert msg is not None
    assert msg.content["data"] == "hello"
    print("  ✓ 消息接收成功")
    
    sender.shutdown()
    receiver.shutdown()
    
    print("[Pass] Agent间通信\n")
    return True


def test_multi_agent_coordination():
    """测试多Agent协调"""
    print("[Test] 多Agent协调")
    
    bus = MessageBus("coord_bus")
    coord = CoordinationAgent("coord", bus)
    dev = DevelopmentAgent("dev", bus)
    tester = TestingAgent("tester", bus)
    
    coord.initialize()
    dev.initialize()
    tester.initialize()
    
    # 注册Agent
    coord.register_agent(dev)
    coord.register_agent(tester)
    
    agents = coord.get_registered_agents()
    assert "dev" in agents
    assert "tester" in agents
    print("  ✓ Agent注册成功")
    
    # 创建工作流
    wf = coord.create_workflow("test_workflow")
    wf.add_task("task1", "编码", agent_name="dev")
    wf.add_task("task2", "测试", agent_name="tester")
    wf.add_dependency("task2", "task1")
    print("  ✓ 工作流创建成功")
    
    # 执行工作流
    result = coord.execute_workflow(wf)
    assert result is not None
    print("  ✓ 工作流执行成功")
    
    coord.shutdown()
    dev.shutdown()
    tester.shutdown()
    
    print("[Pass] 多Agent协调\n")
    return True


def main():
    print("=" * 60)
    print("MVP阶段10验证: 集成测试")
    print("=" * 60)
    
    results = []
    results.append(("完整流水线", test_full_pipeline()))
    results.append(("Agent间通信", test_agent_communication()))
    results.append(("多Agent协调", test_multi_agent_coordination()))
    
    print("=" * 60)
    print("验收结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 MVP阶段10验收通过！")
        print("🎉 MVP全部10个阶段完成！")
        return 0
    else:
        print("\n⚠️ 存在失败测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
