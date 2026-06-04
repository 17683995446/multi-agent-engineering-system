"""
MVP阶段1: 核心Agent基类与消息系统
遵循第一性原理：责任正交性、状态分离
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
import threading
import uuid

from src.common.utils import setup_logger

logger = setup_logger(__name__)


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    NOTIFICATION = "notification"
    ERROR = "error"


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class Message:
    """
    消息实体 - 系统的最小通信单元
    
    属性：
    - msg_id: 消息唯一标识
    - msg_type: 消息类型
    - sender: 发送者
    - receiver: 接收者（None表示广播）
    - content: 消息内容
    - timestamp: 时间戳
    - correlation_id: 关联ID（用于请求-响应匹配）
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
        """工厂方法创建消息"""
        return cls(
            msg_id=str(uuid.uuid4())[:8],
            msg_type=msg_type,
            sender=sender,
            receiver=receiver,
            content=content,
            correlation_id=correlation_id
        )


class MessageBus:
    """
    消息总线 - 负责Agent间消息路由
    
    核心方法：
    - register: 注册Agent
    - unregister: 注销Agent
    - send: 发送消息
    - broadcast: 广播消息
    """
    
    def __init__(self, name: str = "message_bus"):
        """初始化消息总线"""
        self.name = name
        self._agents: Dict[str, 'AgentBase'] = {}
        self._queues: Dict[str, Queue] = {}
        self._lock = threading.RLock()
        logger.info(f"消息总线初始化: {name}")
    
    def register(self, agent: 'AgentBase') -> bool:
        """注册Agent到总线"""
        with self._lock:
            if agent.name in self._agents:
                logger.warning(f"Agent已注册: {agent.name}")
                return False
            self._agents[agent.name] = agent
            self._queues[agent.name] = Queue()
            logger.info(f"Agent注册成功: {agent.name}")
            return True
    
    def unregister(self, agent_name: str) -> bool:
        """从总线注销Agent"""
        with self._lock:
            if agent_name not in self._agents:
                return False
            del self._agents[agent_name]
            del self._queues[agent_name]
            logger.info(f"Agent注销成功: {agent_name}")
            return True
    
    def send(self, message: Message) -> bool:
        """发送消息到指定Agent"""
        with self._lock:
            if message.receiver is None:
                return self.broadcast(message)
            
            if message.receiver not in self._agents:
                logger.error(f"接收者不存在: {message.receiver}")
                return False
            
            self._queues[message.receiver].put(message)
            logger.debug(f"消息发送: {message.sender} -> {message.receiver}")
            return True
    
    def broadcast(self, message: Message) -> bool:
        """广播消息给所有Agent"""
        with self._lock:
            count = 0
            for agent_name in self._agents:
                if agent_name != message.sender:
                    msg_copy = Message.create(
                        msg_type=message.msg_type,
                        sender=message.sender,
                        receiver=agent_name,
                        content=message.content.copy(),
                        correlation_id=message.correlation_id
                    )
                    self._queues[agent_name].put(msg_copy)
                    count += 1
            logger.debug(f"消息广播: {message.sender} -> {count}个Agent")
            return count > 0
    
    def receive(self, agent_name: str, timeout: Optional[float] = None) -> Optional[Message]:
        """接收消息"""
        with self._lock:
            if agent_name not in self._queues:
                return None
            queue = self._queues[agent_name]
        
        try:
            return queue.get(timeout=timeout)
        except Exception:
            return None
    
    def get_registered_agents(self) -> List[str]:
        """获取已注册的Agent列表"""
        with self._lock:
            return list(self._agents.keys())


class AgentBase(ABC):
    """
    Agent基类 - 所有Agent的抽象基类
    
    核心方法：
    - initialize: 初始化
    - execute: 执行任务
    - handle_message: 处理消息
    - shutdown: 关闭
    """
    
    def __init__(self, name: str, message_bus: Optional[MessageBus] = None):
        """初始化Agent"""
        self.name = name
        self.status = AgentStatus.IDLE
        self.message_bus = message_bus
        self._message_handlers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        self._running = False
        self._thread: Optional[threading.Thread] = None
        logger.info(f"Agent初始化: {name}")
    
    def initialize(self) -> bool:
        """初始化Agent"""
        logger.info(f"Agent启动: {self.name}")
        self._running = True
        self.status = AgentStatus.IDLE
        
        if self.message_bus:
            self.message_bus.register(self)
            self._thread = threading.Thread(target=self._message_loop, daemon=True)
            self._thread.start()
        
        return True
    
    def shutdown(self) -> bool:
        """关闭Agent"""
        logger.info(f"Agent关闭: {self.name}")
        self._running = False
        self.status = AgentStatus.STOPPED
        
        if self.message_bus:
            self.message_bus.unregister(self.name)
        
        return True
    
    def register_handler(self, msg_type: MessageType, handler: Callable) -> None:
        """注册消息处理器"""
        self._message_handlers[msg_type].append(handler)
        logger.debug(f"注册处理器: {self.name} -> {msg_type.value}")
    
    def send_message(
        self,
        receiver: Optional[str],
        content: Dict[str, Any],
        msg_type: MessageType = MessageType.REQUEST,
        correlation_id: Optional[str] = None
    ) -> bool:
        """发送消息"""
        if not self.message_bus:
            logger.error("未连接消息总线")
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
            
            message = self.message_bus.receive(self.name, timeout=0.1)
            if message:
                self._handle_message(message)
    
    def _handle_message(self, message: Message) -> None:
        """处理消息"""
        handlers = self._message_handlers.get(message.msg_type, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"消息处理失败: {e}")
    
    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务 - 子类必须实现"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "name": self.name,
            "status": self.status.value,
            "running": self._running,
            "handlers": {k.value: len(v) for k, v in self._message_handlers.items()}
        }
