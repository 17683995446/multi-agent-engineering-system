"""
观察者模式增强模块
遵循第一性原理：状态变化传播公理

核心功能：
1. 主题订阅 - 观察者注册与注销
2. 事件过滤 - 基于条件的事件分发
3. 优先级通知 - 按优先级顺序通知观察者
4. 异步通知 - 非阻塞的事件通知
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from common.utils import setup_logger

logger = setup_logger(__name__)


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class Event:
    """事件对象"""
    name: str
    data: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class EventFilter(ABC):
    """事件过滤器抽象基类"""

    @abstractmethod
    def match(self, event: Event) -> bool:
        """判断事件是否匹配"""
        pass


class NameFilter(EventFilter):
    """名称过滤器"""

    def __init__(self, event_names: List[str]):
        self.event_names = set(event_names)

    def match(self, event: Event) -> bool:
        return event.name in self.event_names


class SourceFilter(EventFilter):
    """来源过滤器"""

    def __init__(self, sources: List[str]):
        self.sources = set(sources)

    def match(self, event: Event) -> bool:
        return event.source in self.sources


class DataFilter(EventFilter):
    """数据字段过滤器"""

    def __init__(self, field: str, value: Any):
        self.field = field
        self.value = value

    def match(self, event: Event) -> bool:
        if isinstance(event.data, dict):
            return event.data.get(self.field) == self.value
        return False


class CustomFilter(EventFilter):
    """自定义过滤器"""

    def __init__(self, predicate: Callable[[Event], bool]):
        self.predicate = predicate

    def match(self, event: Event) -> bool:
        return self.predicate(event)


class Observer(ABC):
    """观察者抽象基类"""

    @abstractmethod
    def on_event(self, event: Event) -> None:
        pass


class CallableObserver(Observer):
    """可调用对象观察者"""

    def __init__(self, callback: Callable[[Event], None]):
        self.callback = callback

    def on_event(self, event: Event) -> None:
        self.callback(event)


@dataclass
class Subscription:
    """订阅信息"""
    observer: Observer
    priority: EventPriority = EventPriority.NORMAL
    filters: List[EventFilter] = field(default_factory=list)
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    active: bool = True

    def should_notify(self, event: Event) -> bool:
        """判断是否应该通知此订阅"""
        if not self.active:
            return False
        if not self.filters:
            return True
        return all(f.match(event) for f in self.filters)


class Subject:
    """
    主题（被观察者）

    增强功能：
    - 支持优先级通知
    - 支持事件过滤
    - 支持异步通知
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._subscriptions: List[Subscription] = []
        self._lock = threading.RLock()
        self._async_enabled = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_async(self, enabled: bool, max_workers: int = 4) -> None:
        """设置异步模式"""
        self._async_enabled = enabled
        if enabled and self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=max_workers)
            try:
                self._event_loop = asyncio.get_event_loop()
            except RuntimeError:
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)

    def subscribe(
        self,
        observer: Observer,
        priority: EventPriority = EventPriority.NORMAL,
        filters: Optional[List[EventFilter]] = None,
    ) -> str:
        """订阅事件"""
        subscription = Subscription(
            observer=observer,
            priority=priority,
            filters=filters or [],
        )
        with self._lock:
            self._subscriptions.append(subscription)
            # 按优先级排序
            self._subscriptions.sort(key=lambda s: s.priority.value)
        logger.info(f"订阅注册: {subscription.subscription_id} (priority={priority.name})")
        return subscription.subscription_id

    def subscribe_callback(
        self,
        callback: Callable[[Event], None],
        priority: EventPriority = EventPriority.NORMAL,
        filters: Optional[List[EventFilter]] = None,
    ) -> str:
        """使用回调函数订阅"""
        return self.subscribe(CallableObserver(callback), priority, filters)

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        with self._lock:
            for i, sub in enumerate(self._subscriptions):
                if sub.subscription_id == subscription_id:
                    sub.active = False
                    self._subscriptions.pop(i)
                    logger.info(f"订阅注销: {subscription_id}")
                    return True
        return False

    def notify(self, event: Event) -> int:
        """通知所有匹配的观察者，返回通知数量"""
        notified = 0
        with self._lock:
            subscriptions = self._subscriptions.copy()

        for sub in subscriptions:
            if sub.should_notify(event):
                try:
                    if self._async_enabled and self._executor:
                        self._executor.submit(self._notify_observer, sub, event)
                    else:
                        self._notify_observer(sub, event)
                    notified += 1
                except Exception as e:
                    logger.error(f"通知观察者失败: {e}\n{traceback.format_exc()}")

        return notified

    def _notify_observer(self, subscription: Subscription, event: Event) -> None:
        """通知单个观察者"""
        try:
            subscription.observer.on_event(event)
        except Exception as e:
            logger.error(f"观察者处理事件失败 [{subscription.subscription_id}]: {e}")

    def emit(self, name: str, data: Any = None, source: str = "") -> int:
        """发送事件"""
        event = Event(name=name, data=data, source=source)
        return self.notify(event)

    def get_subscriber_count(self) -> int:
        """获取订阅者数量"""
        with self._lock:
            return len(self._subscriptions)

    def clear(self) -> None:
        """清除所有订阅"""
        with self._lock:
            self._subscriptions.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.clear()
        if self._executor:
            self._executor.shutdown(wait=False)


class EventBus:
    """
    事件总线

    管理多个主题，支持跨主题事件路由
    """

    def __init__(self):
        self._subjects: Dict[str, Subject] = {}
        self._lock = threading.Lock()

    def get_subject(self, name: str) -> Subject:
        """获取或创建主题"""
        with self._lock:
            if name not in self._subjects:
                self._subjects[name] = Subject(name)
            return self._subjects[name]

    def subscribe(
        self,
        subject_name: str,
        observer: Observer,
        priority: EventPriority = EventPriority.NORMAL,
        filters: Optional[List[EventFilter]] = None,
    ) -> str:
        """订阅指定主题"""
        subject = self.get_subject(subject_name)
        return subject.subscribe(observer, priority, filters)

    def subscribe_callback(
        self,
        subject_name: str,
        callback: Callable[[Event], None],
        priority: EventPriority = EventPriority.NORMAL,
        filters: Optional[List[EventFilter]] = None,
    ) -> str:
        """使用回调订阅指定主题"""
        subject = self.get_subject(subject_name)
        return subject.subscribe_callback(callback, priority, filters)

    def emit(self, subject_name: str, event_name: str, data: Any = None, source: str = "") -> int:
        """向指定主题发送事件"""
        subject = self._subjects.get(subject_name)
        if subject is None:
            return 0
        return subject.emit(event_name, data, source)

    def broadcast(self, event_name: str, data: Any = None, source: str = "") -> int:
        """向所有主题广播事件"""
        total = 0
        with self._lock:
            subjects = list(self._subjects.values())
        for subject in subjects:
            total += subject.emit(event_name, data, source)
        return total

    def get_subject_names(self) -> List[str]:
        """获取所有主题名称"""
        with self._lock:
            return list(self._subjects.keys())

    def clear(self) -> None:
        """清除所有主题"""
        with self._lock:
            for subject in self._subjects.values():
                subject.clear()
            self._subjects.clear()


def demo_observer_enhanced():
    """演示观察者模式增强"""
    print("=" * 60)
    print("观察者模式增强演示")
    print("=" * 60)
    print()

    # 1. 基础订阅
    print("1. 基础订阅:")
    subject = Subject("demo")

    received = []
    class PrintObserver(Observer):
        def on_event(self, event: Event):
            received.append(event.name)
            print(f"   收到: {event.name} = {event.data}")

    obs = PrintObserver()
    sub_id = subject.subscribe(obs)
    subject.emit("test", "hello")
    print(f"   订阅ID: {sub_id}")
    print()

    # 2. 优先级通知
    print("2. 优先级通知:")
    subject2 = Subject("priority_demo")
    order = []

    def make_observer(name):
        class O(Observer):
            def on_event(self, event):
                order.append(name)
        return O()

    subject2.subscribe(make_observer("low"), EventPriority.LOW)
    subject2.subscribe(make_observer("high"), EventPriority.HIGH)
    subject2.subscribe(make_observer("normal"), EventPriority.NORMAL)
    subject2.subscribe(make_observer("critical"), EventPriority.CRITICAL)

    subject2.emit("priority_test")
    print(f"   通知顺序: {order}")
    print()

    # 3. 事件过滤
    print("3. 事件过滤:")
    subject3 = Subject("filter_demo")
    filtered_events = []

    def on_filtered(event):
        filtered_events.append(event.name)

    # 只接收特定名称的事件
    name_filter = NameFilter(["important", "urgent"])
    subject3.subscribe_callback(on_filtered, filters=[name_filter])

    subject3.emit("normal", "data")
    subject3.emit("important", "data")
    subject3.emit("urgent", "data")
    print(f"   过滤后收到: {filtered_events}")
    print()

    # 4. 异步通知
    print("4. 异步通知:")
    subject4 = Subject("async_demo")
    async_received = []

    def slow_observer(event):
        time.sleep(0.05)
        async_received.append(event.name)

    subject4.subscribe_callback(slow_observer)
    subject4.set_async(True, max_workers=2)

    start = time.time()
    subject4.emit("async1")
    subject4.emit("async2")
    subject4.emit("async3")
    elapsed = time.time() - start
    time.sleep(0.2)  # 等待异步完成
    print(f"   异步发送耗时: {elapsed:.3f}s")
    print(f"   收到事件: {async_received}")
    print()

    # 5. 事件总线
    print("5. 事件总线:")
    bus = EventBus()
    bus_events = []

    bus.subscribe_callback("topic1", lambda e: bus_events.append(f"t1:{e.name}"))
    bus.subscribe_callback("topic2", lambda e: bus_events.append(f"t2:{e.name}"))

    bus.emit("topic1", "event_a")
    bus.emit("topic2", "event_b")
    print(f"   收到: {bus_events}")
    print()

    print("=" * 60)
    print("观察者模式增强演示完成")
    print("=" * 60)
    print()
    print("✓ 主题订阅")
    print("✓ 事件过滤")
    print("✓ 优先级通知")
    print("✓ 异步通知")
    print()


if __name__ == "__main__":
    demo_observer_enhanced()
