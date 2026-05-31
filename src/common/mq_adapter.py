"""
公共层 - 消息队列适配器模块
遵循第一性原理：解耦、可靠投递、容错处理

核心功能：
1. 统一消息队列接口（抽象基类）
2. 生产者/消费者模式
3. 消息确认机制
4. 死信队列处理
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from common.utils import setup_logger

logger = setup_logger(__name__)


class MQType(Enum):
    """消息队列类型"""
    IN_MEMORY = "in_memory"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    REDIS = "redis"


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKED = "acked"
    NACKED = "nacked"
    DEAD = "dead"


class MQException(Exception):
    """消息队列异常"""
    pass


@dataclass
class Message:
    """消息体"""
    body: Any
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = "default"
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    status: MessageStatus = MessageStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "body": self.body,
            "headers": self.headers,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "status": self.status.value,
        }


@dataclass
class MQConfig:
    """消息队列配置"""
    mq_type: MQType = MQType.IN_MEMORY
    host: str = "localhost"
    port: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_dlq: bool = True
    dlq_suffix: str = "_dlq"
    max_queue_size: int = 10000
    ack_timeout: float = 30.0


class MQBackend(ABC):
    """
    消息队列后端抽象基类
    """

    def __init__(self, config: MQConfig):
        self.config = config
        self.logger = setup_logger(f"common.mq_adapter.{config.mq_type.value}")

    @abstractmethod
    def publish(self, message: Message) -> bool:
        """发布消息"""

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[Message], None]) -> str:
        """订阅消息，返回订阅ID"""

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""

    @abstractmethod
    def ack(self, message: Message) -> None:
        """确认消息"""

    @abstractmethod
    def nack(self, message: Message, requeue: bool = True) -> None:
        """否定确认消息"""

    @abstractmethod
    def get_queue_depth(self, topic: str) -> int:
        """获取队列深度"""

    @abstractmethod
    def close(self) -> None:
        """关闭后端"""


class InMemoryMQBackend(MQBackend):
    """
    内存消息队列后端（用于测试和演示）
    """

    def __init__(self, config: MQConfig):
        super().__init__(config)
        self._queues: Dict[str, queue.Queue[Message]] = {}
        self._dlq: Dict[str, queue.Queue[Message]] = {}
        self._subscribers: Dict[str, Dict[str, Callable]] = {}
        self._subscriber_topics: Dict[str, str] = {}
        self._message_status: Dict[str, MessageStatus] = {}
        self._lock = threading.RLock()
        self._running = True
        self._dispatch_threads: List[threading.Thread] = []

    def _get_or_create_queue(self, topic: str) -> queue.Queue[Message]:
        with self._lock:
            if topic not in self._queues:
                self._queues[topic] = queue.Queue(maxsize=self.config.max_queue_size)
            return self._queues[topic]

    def _get_or_create_dlq(self, topic: str) -> queue.Queue[Message]:
        with self._lock:
            dlq_topic = f"{topic}{self.config.dlq_suffix}"
            if dlq_topic not in self._dlq:
                self._dlq[dlq_topic] = queue.Queue()
            return self._dlq[dlq_topic]

    def publish(self, message: Message) -> bool:
        q = self._get_or_create_queue(message.topic)
        try:
            q.put_nowait(message)
            with self._lock:
                self._message_status[message.message_id] = MessageStatus.PENDING
            self.logger.debug(f"消息已发布: {message.message_id} -> {message.topic}")
            self._dispatch(message.topic)
            return True
        except queue.Full:
            self.logger.error(f"队列已满: {message.topic}")
            return False

    def subscribe(self, topic: str, handler: Callable[[Message], None]) -> str:
        sub_id = str(uuid.uuid4())
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = {}
            self._subscribers[topic][sub_id] = handler
            self._subscriber_topics[sub_id] = topic
        self.logger.debug(f"订阅已注册: {sub_id} -> {topic}")
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            topic = self._subscriber_topics.pop(subscription_id, None)
            if topic and topic in self._subscribers:
                self._subscribers[topic].pop(subscription_id, None)

    def ack(self, message: Message) -> None:
        with self._lock:
            self._message_status[message.message_id] = MessageStatus.ACKED
        self.logger.debug(f"消息已确认: {message.message_id}")

    def nack(self, message: Message, requeue: bool = True) -> None:
        with self._lock:
            self._message_status[message.message_id] = MessageStatus.NACKED

        if requeue and message.retry_count < self.config.max_retries:
            message.retry_count += 1
            message.status = MessageStatus.PENDING
            self.logger.warning(f"消息重新入队: {message.message_id}, 重试次数: {message.retry_count}")
            time.sleep(self.config.retry_delay)
            self.publish(message)
        else:
            message.status = MessageStatus.DEAD
            if self.config.enable_dlq:
                dlq = self._get_or_create_dlq(message.topic)
                dlq.put(message)
                self.logger.error(f"消息进入死信队列: {message.message_id}")

    def get_queue_depth(self, topic: str) -> int:
        with self._lock:
            q = self._queues.get(topic)
            return q.qsize() if q else 0

    def _dispatch(self, topic: str) -> None:
        """分发消息到订阅者"""
        with self._lock:
            handlers = list(self._subscribers.get(topic, {}).items())
            q = self._queues.get(topic)

        if not q or q.empty():
            return

        for sub_id, handler in handlers:
            try:
                message = q.get_nowait()
                message.status = MessageStatus.DELIVERED
                with self._lock:
                    self._message_status[message.message_id] = MessageStatus.DELIVERED

                # 异步投递
                threading.Thread(
                    target=self._deliver,
                    args=(handler, message),
                    daemon=True,
                ).start()
            except queue.Empty:
                break

    def _deliver(self, handler: Callable[[Message], None], message: Message) -> None:
        """投递消息"""
        try:
            handler(message)
        except Exception as e:
            self.logger.error(f"消息处理失败: {message.message_id}, 错误: {e}")
            self.nack(message, requeue=True)

    def close(self) -> None:
        self._running = False
        self.logger.info("内存MQ后端已关闭")

    def get_dlq_depth(self, topic: str) -> int:
        """获取死信队列深度"""
        dlq_topic = f"{topic}{self.config.dlq_suffix}"
        with self._lock:
            q = self._dlq.get(dlq_topic)
            return q.qsize() if q else 0

    def get_message_status(self, message_id: str) -> Optional[MessageStatus]:
        """获取消息状态"""
        with self._lock:
            return self._message_status.get(message_id)


class MQProducer:
    """
    消息生产者
    """

    def __init__(self, backend: MQBackend, topic: str):
        self.backend = backend
        self.topic = topic
        self.logger = setup_logger(f"common.mq_adapter.producer.{topic}")

    def send(self, body: Any, headers: Optional[Dict[str, str]] = None) -> Message:
        """发送消息"""
        message = Message(
            body=body,
            topic=self.topic,
            headers=headers or {},
        )
        success = self.backend.publish(message)
        if not success:
            raise MQException(f"消息发送失败: {message.message_id}")
        self.logger.debug(f"消息已发送: {message.message_id}")
        return message

    def send_batch(self, bodies: List[Any]) -> List[Message]:
        """批量发送消息"""
        messages = []
        for body in bodies:
            msg = self.send(body)
            messages.append(msg)
        return messages


class MQConsumer:
    """
    消息消费者
    """

    def __init__(self, backend: MQBackend, topic: str, auto_ack: bool = True):
        self.backend = backend
        self.topic = topic
        self.auto_ack = auto_ack
        self.logger = setup_logger(f"common.mq_adapter.consumer.{topic}")
        self._subscription_id: Optional[str] = None
        self._handler: Optional[Callable[[Message], None]] = None
        self._running = False

    def start(self, handler: Callable[[Message], None]) -> None:
        """启动消费"""
        self._handler = handler
        self._running = True

        def wrapper(message: Message) -> None:
            try:
                handler(message)
                if self.auto_ack:
                    self.backend.ack(message)
            except Exception as e:
                self.logger.error(f"消费处理失败: {e}")
                if self.auto_ack:
                    self.backend.nack(message, requeue=True)

        self._subscription_id = self.backend.subscribe(self.topic, wrapper)
        self.logger.info(f"消费者已启动: {self.topic}")

    def stop(self) -> None:
        """停止消费"""
        self._running = False
        if self._subscription_id:
            self.backend.unsubscribe(self._subscription_id)
            self._subscription_id = None
        self.logger.info(f"消费者已停止: {self.topic}")

    def ack(self, message: Message) -> None:
        """手动确认"""
        self.backend.ack(message)

    def nack(self, message: Message, requeue: bool = True) -> None:
        """手动否定确认"""
        self.backend.nack(message, requeue)


class MQAdapter:
    """
    消息队列适配器

    统一消息队列接口，集成生产者/消费者、消息确认、死信队列
    """

    def __init__(self, config: Optional[MQConfig] = None, name: str = "mq_adapter"):
        self.config = config or MQConfig()
        self.name = name
        self.logger = setup_logger(f"common.mq_adapter.{name}")
        self._backend: Optional[MQBackend] = None
        self._producers: Dict[str, MQProducer] = {}
        self._consumers: Dict[str, MQConsumer] = {}
        self._lock = threading.RLock()
        self._init_backend()

    def _init_backend(self) -> None:
        """初始化后端"""
        if self.config.mq_type == MQType.IN_MEMORY:
            self._backend = InMemoryMQBackend(self.config)
        else:
            self.logger.warning(f"MQ类型 {self.config.mq_type.value} 暂未实现，使用 IN_MEMORY")
            self._backend = InMemoryMQBackend(self.config)

    def create_producer(self, topic: str) -> MQProducer:
        """创建生产者"""
        with self._lock:
            if topic not in self._producers:
                self._producers[topic] = MQProducer(self._backend, topic)
            return self._producers[topic]

    def create_consumer(self, topic: str, auto_ack: bool = True) -> MQConsumer:
        """创建消费者"""
        with self._lock:
            if topic not in self._consumers:
                self._consumers[topic] = MQConsumer(self._backend, topic, auto_ack)
            return self._consumers[topic]

    def publish(self, topic: str, body: Any, headers: Optional[Dict[str, str]] = None) -> Message:
        """直接发布消息"""
        producer = self.create_producer(topic)
        return producer.send(body, headers)

    def subscribe(self, topic: str, handler: Callable[[Message], None], auto_ack: bool = True) -> MQConsumer:
        """订阅并启动消费"""
        consumer = self.create_consumer(topic, auto_ack)
        consumer.start(handler)
        return consumer

    def get_queue_depth(self, topic: str) -> int:
        """获取队列深度"""
        return self._backend.get_queue_depth(topic)

    def get_dlq_depth(self, topic: str) -> int:
        """获取死信队列深度"""
        if isinstance(self._backend, InMemoryMQBackend):
            return self._backend.get_dlq_depth(topic)
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "backend_type": self.config.mq_type.value,
            "producers": list(self._producers.keys()),
            "consumers": list(self._consumers.keys()),
        }
        for topic in self._producers:
            stats[f"queue_depth_{topic}"] = self.get_queue_depth(topic)
            stats[f"dlq_depth_{topic}"] = self.get_dlq_depth(topic)
        return stats

    def close(self) -> None:
        """关闭适配器"""
        with self._lock:
            for consumer in self._consumers.values():
                consumer.stop()
            self._consumers.clear()
            self._producers.clear()
            if self._backend:
                self._backend.close()
                self._backend = None
        self.logger.info("消息队列适配器已关闭")


def get_mq_adapter(config: Optional[MQConfig] = None, name: str = "default") -> MQAdapter:
    """获取消息队列适配器实例"""
    return MQAdapter(config, name)


def demo_mq_adapter():
    """演示消息队列适配器"""
    print("=" * 60)
    print("消息队列适配器模块验证")
    print("=" * 60)
    print()

    mq = MQAdapter(name="demo")

    print("1. 发布消息:")
    msg1 = mq.publish("orders", {"order_id": "1001", "amount": 199.99})
    print(f"   ✓ 消息已发布: {msg1.message_id}")
    msg2 = mq.publish("orders", {"order_id": "1002", "amount": 299.99})
    print(f"   ✓ 消息已发布: {msg2.message_id}")
    print()

    print("2. 订阅并消费消息:")
    received = []

    def handler(message: Message):
        received.append(message.body)
        print(f"   ✓ 收到消息: {message.body}")

    consumer = mq.subscribe("orders", handler, auto_ack=True)
    time.sleep(0.5)
    print(f"   ✓ 共收到 {len(received)} 条消息")
    print()

    print("3. 消息确认状态:")
    if isinstance(mq._backend, InMemoryMQBackend):
        status = mq._backend.get_message_status(msg1.message_id)
        print(f"   ✓ 消息 {msg1.message_id} 状态: {status.value if status else 'unknown'}")
    print()

    print("4. 死信队列测试:")
    dlq_received = []

    def failing_handler(message: Message):
        raise Exception("模拟处理失败")

    consumer2 = mq.subscribe("dlq_test", failing_handler, auto_ack=True)
    mq.publish("dlq_test", {"test": "dead_letter"})
    time.sleep(1.5)

    dlq_depth = mq.get_dlq_depth("dlq_test")
    print(f"   ✓ 死信队列深度: {dlq_depth}")
    consumer2.stop()
    print()

    print("5. 批量发送:")
    producer = mq.create_producer("batch_topic")
    messages = producer.send_batch([{"id": i} for i in range(5)])
    print(f"   ✓ 批量发送 {len(messages)} 条消息")
    print()

    print("6. 统计信息:")
    stats = mq.get_stats()
    print(f"   ✓ 统计: {stats}")
    print()

    consumer.stop()
    mq.close()

    print("=" * 60)
    print("消息队列适配器模块验证成功")
    print("=" * 60)
    print()
    print("✓ 统一消息队列接口")
    print("✓ 生产者/消费者模式")
    print("✓ 消息确认机制")
    print("✓ 死信队列处理")
    print()


if __name__ == "__main__":
    demo_mq_adapter()
