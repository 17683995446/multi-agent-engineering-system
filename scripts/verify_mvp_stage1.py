#!/usr/bin/env python3
"""
MVP阶段1验证脚本: 核心Agent基类与消息系统
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mvp_core.agent_base import (
    AgentBase, MessageBus, Message, MessageType, AgentStatus
)


class TestAgent(AgentBase):
    """测试Agent"""
    
    def __init__(self, name: str, message_bus=None):
        super().__init__(name, message_bus)
        self.received_messages = []
    
    def execute(self, task):
        return {"result": f"executed by {self.name}", "task": task}
    
    def on_message(self, message):
        self.received_messages.append(message)


def test_message_bus():
    """测试消息总线"""
    print("\n[Test] 消息总线基础功能")
    
    bus = MessageBus("test_bus")
    agent1 = TestAgent("agent1", bus)
    agent2 = TestAgent("agent2", bus)
    
    # 注册
    assert bus.register(agent1) == True
    assert bus.register(agent2) == True
    assert bus.register(agent1) == False  # 重复注册
    print("  ✓ Agent注册成功")
    
    # 获取列表
    agents = bus.get_registered_agents()
    assert "agent1" in agents
    assert "agent2" in agents
    print("  ✓ Agent列表正确")
    
    # 发送消息
    msg = Message.create(
        msg_type=MessageType.REQUEST,
        sender="agent1",
        receiver="agent2",
        content={"action": "test"}
    )
    assert bus.send(msg) == True
    print("  ✓ 消息发送成功")
    
    # 接收消息
    received = bus.receive("agent2", timeout=1.0)
    assert received is not None
    assert received.content["action"] == "test"
    print("  ✓ 消息接收成功")
    
    # 广播
    broadcast_msg = Message.create(
        msg_type=MessageType.EVENT,
        sender="agent1",
        receiver=None,
        content={"event": "broadcast"}
    )
    assert bus.broadcast(broadcast_msg) == True
    print("  ✓ 消息广播成功")
    
    # 注销
    assert bus.unregister("agent1") == True
    assert bus.unregister("agent1") == False  # 重复注销
    print("  ✓ Agent注销成功")
    
    print("[Pass] 消息总线基础功能\n")
    return True


def test_agent_lifecycle():
    """测试Agent生命周期"""
    print("[Test] Agent生命周期")
    
    bus = MessageBus("test_bus2")
    agent = TestAgent("lifecycle_agent", bus)
    
    # 初始化前状态
    assert agent.status == AgentStatus.IDLE
    assert agent._running == False
    print("  ✓ 初始状态正确")
    
    # 初始化
    assert agent.initialize() == True
    assert agent._running == True
    assert agent.status == AgentStatus.IDLE
    print("  ✓ 初始化成功")
    
    # 状态查询
    status = agent.get_status()
    assert status["name"] == "lifecycle_agent"
    assert status["status"] == "idle"
    print("  ✓ 状态查询正确")
    
    # 关闭
    assert agent.shutdown() == True
    assert agent._running == False
    assert agent.status == AgentStatus.STOPPED
    print("  ✓ 关闭成功")
    
    print("[Pass] Agent生命周期\n")
    return True


def test_agent_messaging():
    """测试Agent消息通信"""
    print("[Test] Agent消息通信")
    
    bus = MessageBus("test_bus3")
    sender = TestAgent("sender", bus)
    receiver = TestAgent("receiver", bus)
    
    sender.initialize()
    receiver.initialize()
    
    # 注册处理器
    receiver.register_handler(MessageType.REQUEST, receiver.on_message)
    
    # 发送消息
    assert sender.send_message(
        receiver="receiver",
        content={"action": "process", "data": "hello"},
        msg_type=MessageType.REQUEST
    ) == True
    print("  ✓ Agent发送消息成功")
    
    # 等待消息处理
    time.sleep(0.2)
    
    # 验证接收
    assert len(receiver.received_messages) == 1
    assert receiver.received_messages[0].content["data"] == "hello"
    print("  ✓ Agent接收消息成功")
    
    sender.shutdown()
    receiver.shutdown()
    
    print("[Pass] Agent消息通信\n")
    return True


def test_message_entity():
    """测试消息实体"""
    print("[Test] 消息实体")
    
    msg = Message.create(
        msg_type=MessageType.REQUEST,
        sender="agent_a",
        receiver="agent_b",
        content={"key": "value"},
        correlation_id="corr_123"
    )
    
    assert msg.msg_id is not None
    assert len(msg.msg_id) == 8
    assert msg.msg_type == MessageType.REQUEST
    assert msg.sender == "agent_a"
    assert msg.receiver == "agent_b"
    assert msg.content["key"] == "value"
    assert msg.correlation_id == "corr_123"
    assert msg.timestamp is not None
    print("  ✓ 消息实体属性正确")
    
    print("[Pass] 消息实体\n")
    return True


def main():
    print("=" * 60)
    print("MVP阶段1验证: 核心Agent基类与消息系统")
    print("=" * 60)
    
    results = []
    results.append(("消息总线基础功能", test_message_bus()))
    results.append(("Agent生命周期", test_agent_lifecycle()))
    results.append(("Agent消息通信", test_agent_messaging()))
    results.append(("消息实体", test_message_entity()))
    
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
        print("\n🎉 MVP阶段1验收通过！")
        return 0
    else:
        print("\n⚠️ 存在失败测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
