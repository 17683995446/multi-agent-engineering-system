#!/usr/bin/env python3
"""
阶段61验证脚本：事件驱动架构
"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.event_bus import (
    EventBus,
    Event,
    EventPriority,
    NameFilter,
    PatternFilter,
    PriorityFilter,
    SourceFilter,
    CompositeFilter,
    create_event,
    get_event_bus,
)


def test_event_creation():
    """测试事件创建"""
    event = create_event("test.event", data={"key": "value"}, source="test")
    assert event.name == "test.event"
    assert event.data == {"key": "value"}
    assert event.source == "test"
    assert event.priority == EventPriority.NORMAL
    assert event.event_id is not None
    print("[PASS] Event Creation")


def test_event_bus_singleton():
    """测试事件总线单例"""
    bus1 = EventBus()
    bus2 = EventBus()
    assert bus1 is bus2
    bus1.reset()
    print("[PASS] EventBus Singleton")


def test_subscribe_and_publish():
    """测试订阅与发布"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.data)

    handler_id = bus.subscribe("user.login", handler)
    event = create_event("user.login", data={"user_id": 123})
    bus.publish(event)

    assert len(received) == 1
    assert received[0]["user_id"] == 123
    bus.unsubscribe(handler_id)
    print("[PASS] Subscribe and Publish")


def test_global_subscription():
    """测试全局订阅"""
    bus = EventBus()
    bus.reset()

    received = []

    def global_handler(event):
        received.append(event.name)

    handler_id = bus.subscribe_all(global_handler)
    bus.publish(create_event("event.a", data=1))
    bus.publish(create_event("event.b", data=2))

    assert len(received) == 2
    assert "event.a" in received
    assert "event.b" in received
    bus.unsubscribe(handler_id)
    print("[PASS] Global Subscription")


def test_name_filter():
    """测试名称过滤器"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.name)

    filter = NameFilter("target.event")
    handler_id = bus.subscribe_all(handler, filter=filter)

    bus.publish(create_event("other.event"))
    bus.publish(create_event("target.event"))

    assert len(received) == 1
    assert received[0] == "target.event"
    bus.unsubscribe(handler_id)
    print("[PASS] Name Filter")


def test_pattern_filter():
    """测试模式过滤器"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.name)

    filter = PatternFilter("user.*")
    handler_id = bus.subscribe_all(handler, filter=filter)

    bus.publish(create_event("user.login"))
    bus.publish(create_event("user.logout"))
    bus.publish(create_event("order.create"))

    assert len(received) == 2
    bus.unsubscribe(handler_id)
    print("[PASS] Pattern Filter")


def test_priority_filter():
    """测试优先级过滤器"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.name)

    filter = PriorityFilter(EventPriority.HIGH)
    handler_id = bus.subscribe_all(handler, filter=filter)

    bus.publish(create_event("low", priority=EventPriority.LOW))
    bus.publish(create_event("normal", priority=EventPriority.NORMAL))
    bus.publish(create_event("high", priority=EventPriority.HIGH))
    bus.publish(create_event("critical", priority=EventPriority.CRITICAL))

    assert len(received) == 2
    assert "high" in received
    assert "critical" in received
    bus.unsubscribe(handler_id)
    print("[PASS] Priority Filter")


def test_source_filter():
    """测试来源过滤器"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.name)

    filter = SourceFilter("module_a")
    handler_id = bus.subscribe_all(handler, filter=filter)

    bus.publish(create_event("event1", source="module_a"))
    bus.publish(create_event("event2", source="module_b"))

    assert len(received) == 1
    assert received[0] == "event1"
    bus.unsubscribe(handler_id)
    print("[PASS] Source Filter")


def test_composite_filter():
    """测试组合过滤器"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.name)

    filter = CompositeFilter([NameFilter("target"), PriorityFilter(EventPriority.HIGH)])
    handler_id = bus.subscribe_all(handler, filter=filter)

    bus.publish(create_event("target", priority=EventPriority.NORMAL))
    bus.publish(create_event("target", priority=EventPriority.HIGH))
    bus.publish(create_event("other", priority=EventPriority.HIGH))

    assert len(received) == 1
    assert received[0] == "target"
    bus.unsubscribe(handler_id)
    print("[PASS] Composite Filter")


def test_async_handler():
    """测试异步处理器"""
    bus = EventBus()
    bus.reset()

    received = []
    lock = threading.Lock()

    def handler(event):
        with lock:
            received.append(event.data)

    handler_id = bus.subscribe("async.event", handler, async_handler=True)
    bus.publish(create_event("async.event", data="async_data"))
    time.sleep(0.3)

    with lock:
        assert len(received) == 1
        assert received[0] == "async_data"
    bus.unsubscribe(handler_id)
    print("[PASS] Async Handler")


def test_event_history():
    """测试事件历史"""
    bus = EventBus()
    bus.reset()

    bus.publish(create_event("event.a", data=1))
    bus.publish(create_event("event.b", data=2))
    bus.publish(create_event("event.a", data=3))

    history = bus.get_history(event_name="event.a")
    assert len(history) == 2

    all_history = bus.get_history()
    assert len(all_history) == 3

    bus.clear_history()
    assert len(bus.get_history()) == 0
    print("[PASS] Event History")


def test_handler_stats():
    """测试处理器统计"""
    bus = EventBus()
    bus.reset()

    def handler(event):
        pass

    handler_id = bus.subscribe("stats.event", handler)
    bus.publish(create_event("stats.event"))
    bus.publish(create_event("stats.event"))

    stats = bus.get_handler_stats()
    assert "stats.event" in stats
    assert len(stats["stats.event"]) == 1
    assert stats["stats.event"][0]["call_count"] == 2
    bus.unsubscribe(handler_id)
    print("[PASS] Handler Stats")


def test_unsubscribe():
    """测试取消订阅"""
    bus = EventBus()
    bus.reset()

    received = []

    def handler(event):
        received.append(event.data)

    handler_id = bus.subscribe("unsub.event", handler)
    bus.publish(create_event("unsub.event", data=1))
    assert len(received) == 1

    result = bus.unsubscribe(handler_id)
    assert result is True
    bus.publish(create_event("unsub.event", data=2))
    assert len(received) == 1
    print("[PASS] Unsubscribe")


def test_priority_order():
    """测试处理器优先级排序"""
    bus = EventBus()
    bus.reset()

    order = []

    def handler_low(event):
        order.append("low")

    def handler_high(event):
        order.append("high")

    bus.subscribe("order.event", handler_low, priority=0)
    bus.subscribe("order.event", handler_high, priority=10)

    bus.publish(create_event("order.event"))
    assert order[0] == "high"
    assert order[1] == "low"
    print("[PASS] Priority Order")


def test_thread_safety():
    """测试线程安全"""
    bus = EventBus()
    bus.reset()

    received = []
    lock = threading.Lock()

    def handler(event):
        with lock:
            received.append(event.data)

    bus.subscribe("thread.event", handler)

    threads = []
    for i in range(10):
        t = threading.Thread(target=lambda idx=i: bus.publish(create_event("thread.event", data=idx)))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(received) == 10
    print("[PASS] Thread Safety")


def run_all_tests():
    print("=" * 50)
    print("阶段61验证：事件驱动架构")
    print("=" * 50)

    tests = [
        test_event_creation,
        test_event_bus_singleton,
        test_subscribe_and_publish,
        test_global_subscription,
        test_name_filter,
        test_pattern_filter,
        test_priority_filter,
        test_source_filter,
        test_composite_filter,
        test_async_handler,
        test_event_history,
        test_handler_stats,
        test_unsubscribe,
        test_priority_order,
        test_thread_safety,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 50)
    print(f"结果：通过 {passed} / 失败 {failed} / 总计 {len(tests)}")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
