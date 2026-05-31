"""
事件驱动架构模块
遵循第一性原理：解耦与异步通信

核心功能：
1. 事件总线（EventBus）- 中心化事件分发
2. 事件订阅/发布 - 松耦合通信
3. 事件过滤器 - 条件订阅
4. 异步事件处理 - 非阻塞事件消费
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class EventPriority(Enum):
    """事件优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """事件对象"""
    name: str
    data: Any = None
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "source": self.source,
            "timestamp": self.timestamp,
            "priority": self.priority.name,
            "data": self.data,
            "metadata": self.metadata,
        }


class EventFilter(ABC):
    """事件过滤器抽象基类"""

    @abstractmethod
    def match(self, event: Event) -> bool:
        """判断事件是否匹配过滤器"""
        pass


class NameFilter(EventFilter):
    """按事件名称过滤"""

    def __init__(self, name: str):
        self.name = name

    def match(self, event: Event) -> bool:
        return event.name == self.name


class PatternFilter(EventFilter):
    """按名称模式过滤（支持通配符 *）"""

    def __init__(self, pattern: str):
        self.pattern = pattern

    def match(self, event: Event) -> bool:
        import fnmatch
        return fnmatch.fnmatch(event.name, self.pattern)


class PriorityFilter(EventFilter):
    """按优先级过滤"""

    def __init__(self, min_priority: EventPriority):
        self.min_priority = min_priority

    def match(self, event: Event) -> bool:
        return event.priority.value >= self.min_priority.value


class SourceFilter(EventFilter):
    """按事件来源过滤"""

    def __init__(self, source: str):
        self.source = source

    def match(self, event: Event) -> bool:
        return event.source == self.source


class CompositeFilter(EventFilter):
    """组合过滤器（AND逻辑）"""

    def __init__(self, filters: List[EventFilter]):
        self.filters = filters

    def match(self, event: Event) -> bool:
        return all(f.match(event) for f in self.filters)


class EventHandler:
    """事件处理器包装器"""

    def __init__(
        self,
        callback: Callable[[Event], Any],
        filter: Optional[EventFilter] = None,
        async_handler: bool = False,
        priority: int = 0,
    ):
        self.callback = callback
        self.filter = filter
        self.async_handler = async_handler
        self.priority = priority
        self.handler_id = str(uuid.uuid4())
        self.call_count = 0
        self.last_called = 0.0

    def can_handle(self, event: Event) -> bool:
        if self.filter is None:
            return True
        return self.filter.match(event)

    def handle(self, event: Event) -> Any:
        try:
            self.call_count += 1
            self.last_called = time.time()
            return self.callback(event)
        except Exception as e:
            logger.error(f"事件处理异常 [{event.name}]: {e}\n{traceback.format_exc()}")
            raise


class EventBus:
    """事件总线 - 中心化事件分发系统"""

    _instance: Optional[EventBus] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 4, enable_async: bool = True):
        if self._initialized:
            return
        self._initialized = True

        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._global_handlers: List[EventHandler] = []
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="event_bus_")
        self._enable_async = enable_async
        self._event_queue: asyncio.Queue = None
        self._async_task: Optional[asyncio.Task] = None
        self._running = False
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(
        self,
        event_name: str,
        callback: Callable[[Event], Any],
        filter: Optional[EventFilter] = None,
        async_handler: bool = False,
        priority: int = 0,
    ) -> str:
        """订阅特定事件"""
        handler = EventHandler(callback, filter, async_handler, priority)
        with self._lock:
            self._handlers[event_name].append(handler)
            self._handlers[event_name].sort(key=lambda h: h.priority, reverse=True)
        logger.debug(f"订阅事件 [{event_name}], handler_id={handler.handler_id}")
        return handler.handler_id

    def subscribe_all(
        self,
        callback: Callable[[Event], Any],
        filter: Optional[EventFilter] = None,
        async_handler: bool = False,
        priority: int = 0,
    ) -> str:
        """订阅所有事件"""
        handler = EventHandler(callback, filter, async_handler, priority)
        with self._lock:
            self._global_handlers.append(handler)
            self._global_handlers.sort(key=lambda h: h.priority, reverse=True)
        logger.debug(f"全局订阅事件, handler_id={handler.handler_id}")
        return handler.handler_id

    def unsubscribe(self, handler_id: str) -> bool:
        """取消订阅"""
        with self._lock:
            for handlers in self._handlers.values():
                for i, h in enumerate(handlers):
                    if h.handler_id == handler_id:
                        handlers.pop(i)
                        logger.debug(f"取消订阅 handler_id={handler_id}")
                        return True
            for i, h in enumerate(self._global_handlers):
                if h.handler_id == handler_id:
                    self._global_handlers.pop(i)
                    logger.debug(f"取消全局订阅 handler_id={handler_id}")
                    return True
        return False

    def publish(self, event: Event) -> List[Any]:
        """发布事件（同步处理）"""
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

        results = []
        handlers = []

        with self._lock:
            handlers.extend(self._global_handlers)
            handlers.extend(self._handlers.get(event.name, []))

        for handler in handlers:
            if handler.can_handle(event):
                try:
                    if handler.async_handler and self._enable_async:
                        future = self._executor.submit(handler.handle, event)
                        results.append(future)
                    else:
                        result = handler.handle(event)
                        results.append(result)
                except Exception as e:
                    logger.error(f"处理事件失败 [{event.name}]: {e}")

        logger.debug(f"发布事件 [{event.name}], 触发 {len(handlers)} 个处理器")
        return results

    def publish_async(self, event: Event) -> None:
        """异步发布事件（放入后台线程池）"""
        self._executor.submit(self.publish, event)

    def start_async_loop(self) -> None:
        """启动异步事件处理循环"""
        if not self._enable_async:
            return
        self._running = True
        logger.info("事件总线异步处理循环已启动")

    def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        self._executor.shutdown(wait=True)
        logger.info("事件总线已停止")

    def get_history(self, event_name: Optional[str] = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        with self._lock:
            events = self._event_history
            if event_name:
                events = [e for e in events if e.name == event_name]
            return events[-limit:]

    def clear_history(self) -> None:
        """清空事件历史"""
        with self._lock:
            self._event_history.clear()

    def get_handler_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        stats = {}
        with self._lock:
            for name, handlers in self._handlers.items():
                stats[name] = [
                    {
                        "handler_id": h.handler_id,
                        "call_count": h.call_count,
                        "last_called": h.last_called,
                        "async": h.async_handler,
                    }
                    for h in handlers
                ]
        return stats

    def reset(self) -> None:
        """重置事件总线（清除所有处理器和历史）"""
        with self._lock:
            self._handlers.clear()
            self._global_handlers.clear()
            self._event_history.clear()
        logger.info("事件总线已重置")


class AsyncEventBus(EventBus):
    """支持asyncio的异步事件总线"""

    def __init__(self, max_workers: int = 4):
        super().__init__(max_workers=max_workers, enable_async=True)
        self._async_handlers: Dict[str, List[Callable[[Event], Any]]] = defaultdict(list)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def publish_async_await(self, event: Event) -> List[Any]:
        """异步发布事件并等待结果"""
        results = []
        handlers = []

        with self._lock:
            handlers.extend(self._global_handlers)
            handlers.extend(self._handlers.get(event.name, []))

        for handler in handlers:
            if handler.can_handle(event):
                try:
                    if asyncio.iscoroutinefunction(handler.callback):
                        result = await handler.callback(event)
                    else:
                        result = handler.handle(event)
                    results.append(result)
                except Exception as e:
                    logger.error(f"异步处理事件失败 [{event.name}]: {e}")

        return results

    def subscribe_async(
        self,
        event_name: str,
        callback: Callable[[Event], Any],
        filter: Optional[EventFilter] = None,
        priority: int = 0,
    ) -> str:
        """订阅异步事件处理器"""
        return self.subscribe(event_name, callback, filter, async_handler=True, priority=priority)


# 便捷函数
def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return EventBus()


def create_event(name: str, data: Any = None, source: str = "", priority: EventPriority = EventPriority.NORMAL) -> Event:
    """创建事件对象"""
    return Event(name=name, data=data, source=source, priority=priority)
