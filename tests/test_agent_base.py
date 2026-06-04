"""
Agent基类测试
遵循项目规范：四类测试用例
"""

import unittest
from src.core.agent_base import (
    AgentBase, MessageBus, Message, MessageType, AgentStatus
)
from src.core.interfaces import AgentInterface


class MockAgent(AgentBase):
    """测试用Mock Agent"""

    def __init__(self, name: str, message_bus=None) -> None:
        """初始化Mock Agent

        Args:
            name: Agent名称
            message_bus: 消息总线
        """
        super().__init__(name, message_bus)
        self.received_messages = []

    def execute(self, task: dict) -> dict:
        """执行测试任务

        Args:
            task: 任务字典

        Returns:
            执行结果
        """
        return {"result": "mock_executed"}

    def on_message(self, message: Message) -> None:
        """消息处理回调

        Args:
            message: 收到的消息
        """
        self.received_messages.append(message)


class TestMessageBus(unittest.TestCase):
    """消息总线测试类"""

    def setUp(self) -> None:
        """测试前置"""
        self.bus = MessageBus("test_bus")
        self.agent1 = MockAgent("agent1", self.bus)
        self.agent2 = MockAgent("agent2", self.bus)

    def tearDown(self) -> None:
        """测试后置"""
        self.agent1.shutdown()
        self.agent2.shutdown()

    def test_register_normal(self) -> None:
        """正常注册测试"""
        result = self.bus.register_agent(self.agent1)
        self.assertTrue(result)
        agents = self.bus.get_registered_agents()
        self.assertIn("agent1", agents)

    def test_register_duplicate(self) -> None:
        """重复注册测试"""
        self.bus.register_agent(self.agent1)
        result = self.bus.register_agent(self.agent1)
        self.assertFalse(result)

    def test_send_normal(self) -> None:
        """正常发送消息测试"""
        self.bus.register_agent(self.agent1)
        self.bus.register_agent(self.agent2)
        result = self.bus.send(
            sender="agent1",
            receiver="agent2",
            content={"action": "test"}
        )
        self.assertTrue(result)

    def test_send_to_nonexistent(self) -> None:
        """发送到不存在Agent测试"""
        result = self.bus.send(
            sender="agent1",
            receiver="nonexistent",
            content={"action": "test"}
        )
        self.assertFalse(result)

    def test_receive_normal(self) -> None:
        """正常接收消息测试"""
        self.bus.register_agent(self.agent1)
        self.bus.register_agent(self.agent2)
        self.bus.send(
            sender="agent1",
            receiver="agent2",
            content={"data": "hello"}
        )
        received = self.bus.receive("agent2", timeout=1.0)
        self.assertIsNotNone(received)
        self.assertEqual(received.content["data"], "hello")

    def test_receive_empty(self) -> None:
        """空队列接收测试"""
        self.bus.register_agent(self.agent1)
        received = self.bus.receive("agent1", timeout=0.1)
        self.assertIsNone(received)

    def test_broadcast(self) -> None:
        """广播消息测试"""
        self.bus.register_agent(self.agent1)
        self.bus.register_agent(self.agent2)
        count = self.bus.broadcast(
            sender="agent1",
            content={"event": "broadcast"}
        )
        self.assertEqual(count, 1)

    def test_unregister_normal(self) -> None:
        """正常注销测试"""
        self.bus.register_agent(self.agent1)
        result = self.bus.unregister("agent1")
        self.assertTrue(result)

    def test_unregister_nonexistent(self) -> None:
        """注销不存在Agent测试"""
        result = self.bus.unregister("nonexistent")
        self.assertFalse(result)


class TestAgentBase(unittest.TestCase):
    """Agent基类测试"""

    def setUp(self) -> None:
        """测试前置"""
        self.agent = MockAgent("test_agent")

    def tearDown(self) -> None:
        """测试后置"""
        self.agent.shutdown()

    def test_init_normal(self) -> None:
        """正常初始化测试"""
        self.assertEqual(self.agent.name, "test_agent")
        self.assertEqual(self.agent.status, AgentStatus.IDLE)

    def test_init_empty_name(self) -> None:
        """空名称初始化测试"""
        agent = MockAgent("")
        self.assertEqual(agent.name, "")
        agent.shutdown()

    def test_initialize(self) -> None:
        """初始化启动测试"""
        result = self.agent.initialize()
        self.assertTrue(result)
        self.assertTrue(self.agent._running)

    def test_shutdown(self) -> None:
        """关闭测试"""
        self.agent.initialize()
        result = self.agent.shutdown()
        self.assertTrue(result)
        self.assertEqual(self.agent.status, AgentStatus.STOPPED)

    def test_execute_normal(self) -> None:
        """正常执行测试"""
        result = self.agent.execute({"action": "test"})
        self.assertEqual(result["result"], "mock_executed")

    def test_execute_empty(self) -> None:
        """空任务执行测试"""
        result = self.agent.execute({})
        self.assertEqual(result["result"], "mock_executed")

    def test_get_status(self) -> None:
        """状态查询测试"""
        status = self.agent.get_status()
        self.assertEqual(status["name"], "test_agent")
        self.assertEqual(status["status"], "idle")

    def test_register_handler(self) -> None:
        """处理器注册测试"""
        self.agent.register_handler(
            MessageType.REQUEST,
            self.agent.on_message
        )
        handlers = self.agent._handlers[MessageType.REQUEST]
        self.assertEqual(len(handlers), 1)

    def test_is_interface(self) -> None:
        """接口实现测试"""
        self.assertIsInstance(self.agent, AgentInterface)


class TestMessage(unittest.TestCase):
    """消息实体测试"""

    def test_create_normal(self) -> None:
        """正常创建测试"""
        msg = Message.create(
            msg_type=MessageType.REQUEST,
            sender="a",
            receiver="b",
            content={"key": "value"}
        )
        self.assertEqual(msg.msg_type, MessageType.REQUEST)
        self.assertEqual(msg.sender, "a")
        self.assertEqual(msg.content["key"], "value")
        self.assertIsNotNone(msg.msg_id)

    def test_create_empty_content(self) -> None:
        """空内容创建测试"""
        msg = Message.create(
            msg_type=MessageType.EVENT,
            sender="a",
            receiver=None,
            content={}
        )
        self.assertEqual(msg.content, {})

    def test_create_boundary_id(self) -> None:
        """ID长度边界测试"""
        msg = Message.create(
            msg_type=MessageType.REQUEST,
            sender="x",
            receiver="y",
            content={}
        )
        self.assertEqual(len(msg.msg_id), 8)


if __name__ == "__main__":
    unittest.main()
