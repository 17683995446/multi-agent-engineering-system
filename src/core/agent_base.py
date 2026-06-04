"""
Agent基类模块
遵循项目规范：函数≤7行、类型注解、标准docstring
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
import threading
import uuid


class MessageType(Enum):
    """消息类型枚举"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    NOTIFICATION = "notification"
    ERROR = "error"


class AgentStatus(Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class Message:
    """消息实体

    Args:
        msg_id: 消息唯一标识
        msg_type: 消息类型
        sender: 发送者名称
        receiver: 接收者名称
        content: 消息内容字典
        timestamp: 时间戳
        correlation_id: 关联ID

    Returns:
        Message实例

    Raises:
        ValueError: 参数无效时
    """
    msg_id: str
    msg_type: MessageType
    sender: str
    receiver: Optional[str]
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        msg_type: MessageType,
        sender: str,
        receiver: Optional[str],
        content: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> 'Message':
        """工厂方法创建消息

        Args:
            msg_type: 消息类型
            sender: 发送者
            receiver: 接收者
            content: 内容
            correlation_id: 关联ID

        Returns:
            新消息实例
        """
        return cls(
            msg_id=str(uuid.uuid4())[:8],
            msg_type=msg_type,
            sender=sender,
            receiver=receiver,
            content=content,
            correlation_id=correlation_id
        )


class MessageBus:
    """消息总线 - Agent间消息路由

    负责Agent注册、消息发送与接收
    """

    def __init__(self, name: str) -> None:
        """初始化消息总线

        Args:
            name: 总线名称
        """
        self.name = name
        self._agents: Dict[str, 'AgentBase'] = {}
        self._queues: Dict[str, Queue] = {}
        self._lock = threading.RLock()

    def register(self, agent: 'AgentBase') -> bool:
        """注册Agent到总线

        Args:
            agent: 要注册的Agent

        Returns:
            注册是否成功
        """
        with self._lock:
            if agent.name in self._agents:
                return False
            self._agents[agent.name] = agent
            self._queues[agent.name] = Queue()
            return True

    def unregister(self, agent_name: str) -> bool:
        """从总线注销Agent

        Args:
            agent_name: Agent名称

        Returns:
            注销是否成功
        """
        with self._lock:
            if agent_name not in self._agents:
                return False
            del self._agents[agent_name]
            del self._queues[agent_name]
            return True

    def send(self, message: Message) -> bool:
        """发送消息到指定Agent

        Args:
            message: 要发送的消息

        Returns:
            发送是否成功
        """
        with self._lock:
            if message.receiver is None:
                return self.broadcast(message)
            if message.receiver not in self._agents:
                return False
            self._queues[message.receiver].put(message)
            return True

    def broadcast(self, message: Message) -> bool:
        """广播消息给所有Agent

        Args:
            message: 要广播的消息

        Returns:
            是否有Agent收到
        """
        count = 0
        for agent_name in self._agents:
            if agent_name == message.sender:
                continue
            msg_copy = Message.create(
                msg_type=message.msg_type,
                sender=message.sender,
                receiver=agent_name,
                content=message.content.copy(),
                correlation_id=message.correlation_id
            )
            self._queues[agent_name].put(msg_copy)
            count += 1
        return count > 0

    def receive(
        self,
        agent_name: str,
        timeout: Optional[float] = None
    ) -> Optional[Message]:
        """接收消息

        Args:
            agent_name: Agent名称
            timeout: 超时时间

        Returns:
            消息或None
        """
        with self._lock:
            if agent_name not in self._queues:
                return None
            queue = self._queues[agent_name]
        try:
            return queue.get(timeout=timeout)
        except Exception:
            return None

    def get_registered_agents(self) -> List[str]:
        """获取已注册的Agent列表

        Returns:
            Agent名称列表
        """
        with self._lock:
            return list(self._agents.keys())


class AgentBase(ABC):
    """Agent抽象基类

    所有Agent必须继承此类并实现execute方法
    """

    def __init__(
        self,
        name: str,
        message_bus: Optional[MessageBus] = None
    ) -> None:
        """初始化Agent

        Args:
            name: Agent名称
            message_bus: 消息总线实例
        """
        self.name = name
        self.status = AgentStatus.IDLE
        self.message_bus = message_bus
        self._handlers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """初始化Agent

        Returns:
            初始化是否成功
        """
        self._running = True
        self.status = AgentStatus.IDLE
        if self.message_bus:
            self.message_bus.register(self)
            self._start_message_loop()
        return True

    def _start_message_loop(self) -> None:
        """启动消息循环线程"""
        self._thread = threading.Thread(
            target=self._message_loop,
            daemon=True
        )
        self._thread.start()

    def shutdown(self) -> bool:
        """关闭Agent

        Returns:
            关闭是否成功
        """
        self._running = False
        self.status = AgentStatus.STOPPED
        if self.message_bus:
            self.message_bus.unregister(self.name)
        return True

    def register_handler(
        self,
        msg_type: MessageType,
        handler: Callable
    ) -> None:
        """注册消息处理器

        Args:
            msg_type: 消息类型
            handler: 处理函数
        """
        self._handlers[msg_type].append(handler)

    def send_message(
        self,
        receiver: Optional[str],
        content: Dict[str, Any],
        msg_type: MessageType = MessageType.REQUEST,
        correlation_id: Optional[str] = None
    ) -> bool:
        """发送消息

        Args:
            receiver: 接收者
            content: 内容
            msg_type: 消息类型
            correlation_id: 关联ID

        Returns:
            发送是否成功
        """
        if not self.message_bus:
            return False
        message = Message.create(
            msg_type=msg_type,
            sender=self.name,
            receiver=receiver,
            content=content,
            correlation_id=correlation_id
        )
        return self.message_bus.send(message)

    def _message_loop(self) -> None:
        """消息循环"""
        while self._running:
            if not self.message_bus:
                break
            message = self.message_bus.receive(
                self.name,
                timeout=0.1
            )
            if message:
                self._handle_message(message)

    def _handle_message(self, message: Message) -> None:
        """处理消息

        Args:
            message: 收到的消息
        """
        handlers = self._handlers.get(message.msg_type, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception:
                pass

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务

        Args:
            task: 任务字典

        Returns:
            执行结果字典
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态

        Returns:
            状态字典
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "running": self._running
        }
