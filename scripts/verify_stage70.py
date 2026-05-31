#!/usr/bin/env python3
"""
阶段70验证脚本：观察者模式增强

测试内容：
1. 主题订阅与注销
2. 事件过滤（名称、来源、数据、自定义）
3. 优先级通知
4. 异步通知
5. 事件总线
6. 上下文管理
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.observer_enhanced import (
    CallableObserver,
    CustomFilter,
    DataFilter,
    Event,
    EventBus,
    EventFilter,
    EventPriority,
    NameFilter,
    Observer,
    SourceFilter,
    Subject,
    Subscription,
)


def test_subscription() -> bool:
    print("[Test] 主题订阅与注销")
    try:
        subject = Subject("test")
        received = []

        class TestObserver(Observer):
            def on_event(self, event: Event):
                received.append(event.data)

        obs = TestObserver()
        sub_id = subject.subscribe(obs)
        assert len(sub_id) > 0
        print(f"  ✓ 订阅成功: {sub_id}")

        # 发送事件
        count = subject.emit("test_event", "hello")
        assert count == 1
        assert received == ["hello"]
        print("  ✓ 事件通知成功")

        # 注销
        result = subject.unsubscribe(sub_id)
        assert result
        assert subject.get_subscriber_count() == 0
        print("  ✓ 注销成功")

        # 再次发送无接收
        count = subject.emit("test_event", "world")
        assert count == 0
        assert received == ["hello"]
        print("  ✓ 注销后不再接收")

        # 回调订阅
        cb_received = []
        cb_id = subject.subscribe_callback(lambda e: cb_received.append(e.data))
        subject.emit("cb_event", "callback_data")
        assert cb_received == ["callback_data"]
        print("  ✓ 回调订阅成功")

        print("[Pass] 主题订阅与注销\n")
        return True
    except Exception as e:
        print(f"[Fail] 主题订阅与注销: {e}\n")
        return False


def test_event_filtering() -> bool:
    print("[Test] 事件过滤")
    try:
        subject = Subject("filter")
        received = []

        def handler(event):
            received.append(event.name)

        # 名称过滤
        name_filter = NameFilter(["allowed"])
        subject.subscribe_callback(handler, filters=[name_filter])

        subject.emit("blocked", "data")
        subject.emit("allowed", "data")
        assert received == ["allowed"]
        print("  ✓ 名称过滤正确")

        # 来源过滤
        subject2 = Subject("source_filter")
        src_received = []
        subject2.subscribe_callback(
            lambda e: src_received.append(e.name),
            filters=[SourceFilter(["module_a"])]
        )
        subject2.emit("event", "data", source="module_b")
        subject2.emit("event", "data", source="module_a")
        assert src_received == ["event"]
        print("  ✓ 来源过滤正确")

        # 数据过滤
        subject3 = Subject("data_filter")
        data_received = []
        subject3.subscribe_callback(
            lambda e: data_received.append(e.data),
            filters=[DataFilter("type", "important")]
        )
        subject3.emit("msg", {"type": "normal"})
        subject3.emit("msg", {"type": "important"})
        assert data_received == [{"type": "important"}]
        print("  ✓ 数据过滤正确")

        # 自定义过滤
        subject4 = Subject("custom_filter")
        custom_received = []
        subject4.subscribe_callback(
            lambda e: custom_received.append(e.name),
            filters=[CustomFilter(lambda e: e.name.startswith("prefix_"))]
        )
        subject4.emit("other", "data")
        subject4.emit("prefix_test", "data")
        assert custom_received == ["prefix_test"]
        print("  ✓ 自定义过滤正确")

        # 组合过滤
        subject5 = Subject("combined")
        combo_received = []
        subject5.subscribe_callback(
            lambda e: combo_received.append(e.name),
            filters=[NameFilter(["event"]), SourceFilter(["app"])]
        )
        subject5.emit("event", "data", source="other")
        subject5.emit("other", "data", source="app")
        subject5.emit("event", "data", source="app")
        assert combo_received == ["event"]
        print("  ✓ 组合过滤正确")

        print("[Pass] 事件过滤\n")
        return True
    except Exception as e:
        print(f"[Fail] 事件过滤: {e}\n")
        return False


def test_priority_notification() -> bool:
    print("[Test] 优先级通知")
    try:
        subject = Subject("priority")
        order = []

        def make_handler(name):
            return lambda e: order.append(name)

        # 按乱序添加
        subject.subscribe_callback(make_handler("normal"), EventPriority.NORMAL)
        subject.subscribe_callback(make_handler("low"), EventPriority.LOW)
        subject.subscribe_callback(make_handler("critical"), EventPriority.CRITICAL)
        subject.subscribe_callback(make_handler("high"), EventPriority.HIGH)
        subject.subscribe_callback(make_handler("background"), EventPriority.BACKGROUND)

        subject.emit("test")
        expected = ["critical", "high", "normal", "low", "background"]
        assert order == expected, f"实际顺序: {order}"
        print(f"  ✓ 优先级顺序正确: {order}")

        # 相同优先级保持添加顺序
        subject2 = Subject("same_priority")
        order2 = []
        subject2.subscribe_callback(lambda e: order2.append("first"), EventPriority.NORMAL)
        subject2.subscribe_callback(lambda e: order2.append("second"), EventPriority.NORMAL)
        subject2.emit("test")
        assert order2 == ["first", "second"]
        print("  ✓ 相同优先级保持顺序")

        print("[Pass] 优先级通知\n")
        return True
    except Exception as e:
        print(f"[Fail] 优先级通知: {e}\n")
        return False


def test_async_notification() -> bool:
    print("[Test] 异步通知")
    try:
        subject = Subject("async")
        received = []

        def slow_handler(event):
            time.sleep(0.05)
            received.append(event.name)

        subject.subscribe_callback(slow_handler)
        subject.set_async(True, max_workers=2)

        start = time.time()
        count = subject.emit("async1")
        count += subject.emit("async2")
        elapsed = time.time() - start

        # 异步发送应该很快返回
        assert elapsed < 0.05, f"异步发送耗时过长: {elapsed}"
        print(f"  ✓ 异步发送耗时: {elapsed:.3f}s")

        # 等待异步完成
        time.sleep(0.2)
        assert len(received) == 2
        assert "async1" in received
        assert "async2" in received
        print(f"  ✓ 异步事件全部收到: {received}")

        # 切换回同步
        subject.set_async(False)
        received.clear()
        start = time.time()
        subject.emit("sync")
        elapsed = time.time() - start
        assert elapsed >= 0.05, f"同步发送应该等待: {elapsed}"
        print(f"  ✓ 同步发送耗时: {elapsed:.3f}s")

        print("[Pass] 异步通知\n")
        return True
    except Exception as e:
        print(f"[Fail] 异步通知: {e}\n")
        return False


def test_event_bus() -> bool:
    print("[Test] 事件总线")
    try:
        bus = EventBus()
        events = []

        # 订阅多个主题
        bus.subscribe_callback("topic1", lambda e: events.append(f"t1:{e.name}"))
        bus.subscribe_callback("topic2", lambda e: events.append(f"t2:{e.name}"))

        bus.emit("topic1", "event_a")
        bus.emit("topic2", "event_b")
        assert "t1:event_a" in events
        assert "t2:event_b" in events
        print("  ✓ 多主题订阅与发送")

        # 广播
        events.clear()
        bus.subscribe_callback("topic3", lambda e: events.append(f"t3:{e.name}"))
        bus.broadcast("broadcast_event")
        assert any("broadcast_event" in e for e in events)
        print(f"  ✓ 广播成功: {events}")

        # 不存在的主题
        count = bus.emit("not_exist", "event")
        assert count == 0
        print("  ✓ 不存在的主题返回0")

        # 主题列表
        names = bus.get_subject_names()
        assert "topic1" in names
        assert "topic2" in names
        print(f"  ✓ 主题列表: {names}")

        # 清除
        bus.clear()
        assert len(bus.get_subject_names()) == 0
        print("  ✓ 清除所有主题")

        print("[Pass] 事件总线\n")
        return True
    except Exception as e:
        print(f"[Fail] 事件总线: {e}\n")
        return False


def test_context_manager() -> bool:
    print("[Test] 上下文管理")
    try:
        received = []

        with Subject("ctx") as subject:
            subject.subscribe_callback(lambda e: received.append(e.name))
            subject.emit("in_context")
            assert "in_context" in received
            print("  ✓ 上下文内正常接收")

        # 退出后自动清理
        subject.emit("after_context")
        assert "after_context" not in received
        print("  ✓ 退出上下文后自动清理")

        print("[Pass] 上下文管理\n")
        return True
    except Exception as e:
        print(f"[Fail] 上下文管理: {e}\n")
        return False


def test_event_object() -> bool:
    print("[Test] 事件对象")
    try:
        event = Event(name="test", data={"key": "value"}, source="app")
        assert event.name == "test"
        assert event.data == {"key": "value"}
        assert event.source == "app"
        assert event.timestamp > 0
        assert len(event.event_id) > 0
        print("  ✓ 事件属性正确")

        d = event.to_dict()
        assert d["name"] == "test"
        assert "event_id" in d
        assert "timestamp" in d
        print("  ✓ to_dict正确")

        print("[Pass] 事件对象\n")
        return True
    except Exception as e:
        print(f"[Fail] 事件对象: {e}\n")
        return False


def test_multiple_observers() -> bool:
    print("[Test] 多观察者")
    try:
        subject = Subject("multi")
        results = []

        for i in range(5):
            subject.subscribe_callback(lambda e, idx=i: results.append(idx))

        subject.emit("test")
        assert len(results) == 5
        assert set(results) == {0, 1, 2, 3, 4}
        print("  ✓ 5个观察者都收到通知")

        # 部分注销
        sub_ids = []
        subject2 = Subject("partial")
        for i in range(3):
            sub_ids.append(subject2.subscribe_callback(lambda e, idx=i: results.append(f"keep_{idx}")))

        subject2.unsubscribe(sub_ids[1])
        results.clear()
        subject2.emit("test")
        assert "keep_1" not in results
        assert "keep_0" in results
        assert "keep_2" in results
        print("  ✓ 部分注销后正确")

        print("[Pass] 多观察者\n")
        return True
    except Exception as e:
        print(f"[Fail] 多观察者: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段70验证脚本：观察者模式增强")
    print("=" * 60 + "\n")

    results = []
    results.append(("主题订阅与注销", test_subscription()))
    results.append(("事件过滤", test_event_filtering()))
    results.append(("优先级通知", test_priority_notification()))
    results.append(("异步通知", test_async_notification()))
    results.append(("事件总线", test_event_bus()))
    results.append(("上下文管理", test_context_manager()))
    results.append(("事件对象", test_event_object()))
    results.append(("多观察者", test_multiple_observers()))

    print("=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("🎉 所有测试通过！阶段70验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
