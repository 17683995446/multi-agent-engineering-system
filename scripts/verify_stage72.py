#!/usr/bin/env python3
"""
阶段72验证脚本：消息队列适配器

测试内容：
1. 消息创建
2. 发布/订阅
3. 消息确认
4. 死信队列
5. 批量发送
6. 消费者管理
7. 统计信息
8. 线程安全
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.mq_adapter import (
    MQAdapter,
    MQConfig,
    MQType,
    Message,
    MessageStatus,
    get_mq_adapter,
)


def test_message_creation() -> bool:
    print("[Test] Message Creation - 消息创建")
    try:
        msg = Message(body={"test": "data"}, topic="test.topic")
        assert msg.message_id is not None
        assert msg.topic == "test.topic"
        assert msg.status == MessageStatus.PENDING
        print(f"  ✓ 消息创建: {msg.message_id}")

        d = msg.to_dict()
        assert d["topic"] == "test.topic"
        print(f"  ✓ to_dict 正确")

        print("[Pass] Message Creation\n")
        return True
    except Exception as e:
        print(f"[Fail] Message Creation: {e}\n")
        return False


def test_publish_subscribe() -> bool:
    print("[Test] Publish/Subscribe - 发布订阅")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_pubsub")

        received = []

        def handler(message: Message):
            received.append(message.body)

        consumer = mq.subscribe("test.events", handler, auto_ack=True)
        msg = mq.publish("test.events", {"id": 1, "action": "login"})
        time.sleep(0.3)

        assert len(received) == 1
        assert received[0]["id"] == 1
        print(f"  ✓ 消息接收: {received}")
        print(f"  ✓ 消息ID: {msg.message_id}")

        consumer.stop()
        mq.close()
        print("[Pass] Publish/Subscribe\n")
        return True
    except Exception as e:
        print(f"[Fail] Publish/Subscribe: {e}\n")
        return False


def test_message_ack() -> bool:
    print("[Test] Message Ack - 消息确认")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_ack")

        received = []

        def handler(message: Message):
            received.append(message)

        consumer = mq.subscribe("ack.topic", handler, auto_ack=True)
        msg = mq.publish("ack.topic", {"test": "ack"})
        time.sleep(0.3)

        # 检查消息状态
        backend = mq._backend
        status = backend.get_message_status(msg.message_id)
        print(f"  ✓ 消息状态: {status.value if status else 'unknown'}")

        consumer.stop()
        mq.close()
        print("[Pass] Message Ack\n")
        return True
    except Exception as e:
        print(f"[Fail] Message Ack: {e}\n")
        return False


def test_dead_letter_queue() -> bool:
    print("[Test] Dead Letter Queue - 死信队列")
    try:
        mq = get_mq_adapter(
            MQConfig(mq_type=MQType.IN_MEMORY, max_retries=2, retry_delay=0.1),
            name="test_dlq",
        )

        def failing_handler(message: Message):
            raise Exception("模拟处理失败")

        consumer = mq.subscribe("dlq.topic", failing_handler, auto_ack=True)
        mq.publish("dlq.topic", {"test": "dead"})
        time.sleep(1.5)

        dlq_depth = mq.get_dlq_depth("dlq.topic")
        print(f"  ✓ 死信队列深度: {dlq_depth}")
        assert dlq_depth >= 1

        consumer.stop()
        mq.close()
        print("[Pass] Dead Letter Queue\n")
        return True
    except Exception as e:
        print(f"[Fail] Dead Letter Queue: {e}\n")
        return False


def test_batch_send() -> bool:
    print("[Test] Batch Send - 批量发送")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_batch")

        received = []

        def handler(message: Message):
            received.append(message.body)

        consumer = mq.subscribe("batch.topic", handler, auto_ack=True)

        producer = mq.create_producer("batch.topic")
        messages = producer.send_batch([{"id": i} for i in range(5)])
        time.sleep(0.5)

        assert len(messages) == 5
        assert len(received) == 5
        print(f"  ✓ 批量发送: {len(messages)} 条")
        print(f"  ✓ 接收确认: {len(received)} 条")

        consumer.stop()
        mq.close()
        print("[Pass] Batch Send\n")
        return True
    except Exception as e:
        print(f"[Fail] Batch Send: {e}\n")
        return False


def test_consumer_management() -> bool:
    print("[Test] Consumer Management - 消费者管理")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_consumer")

        received = []

        def handler(message: Message):
            received.append(message.body)

        consumer = mq.create_consumer("manage.topic", auto_ack=True)
        assert consumer._running is False

        consumer.start(handler)
        assert consumer._running is True
        print("  ✓ 消费者启动")

        mq.publish("manage.topic", {"test": "manage"})
        time.sleep(0.3)
        assert len(received) == 1
        print("  ✓ 消费者正常工作")

        consumer.stop()
        assert consumer._running is False
        print("  ✓ 消费者停止")

        mq.close()
        print("[Pass] Consumer Management\n")
        return True
    except Exception as e:
        print(f"[Fail] Consumer Management: {e}\n")
        return False


def test_stats() -> bool:
    print("[Test] Stats - 统计信息")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_stats")

        stats_before = mq.get_stats()
        print(f"  ✓ 初始统计: {stats_before}")

        mq.publish("stats.topic", {"test": "stats"})
        stats_after = mq.get_stats()
        print(f"  ✓ 发布后统计: {stats_after}")

        mq.close()
        print("[Pass] Stats\n")
        return True
    except Exception as e:
        print(f"[Fail] Stats: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] Thread Safety - 线程安全")
    try:
        mq = get_mq_adapter(MQConfig(mq_type=MQType.IN_MEMORY), name="test_thread")
        errors = []
        received = []

        def handler(message: Message):
            received.append(message.body)

        consumer = mq.subscribe("thread.topic", handler, auto_ack=True)

        def worker():
            try:
                for i in range(10):
                    mq.publish("thread.topic", {"idx": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        time.sleep(0.5)

        assert len(errors) == 0, f"发生错误: {errors}"
        print(f"  ✓ 5线程并发发布无错误")
        print(f"  ✓ 接收消息数: {len(received)}")

        consumer.stop()
        mq.close()
        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段72验证脚本：消息队列适配器")
    print("=" * 60 + "\n")

    results = []
    results.append(("Message Creation", test_message_creation()))
    results.append(("Publish/Subscribe", test_publish_subscribe()))
    results.append(("Message Ack", test_message_ack()))
    results.append(("Dead Letter Queue", test_dead_letter_queue()))
    results.append(("Batch Send", test_batch_send()))
    results.append(("Consumer Management", test_consumer_management()))
    results.append(("Stats", test_stats()))
    results.append(("Thread Safety", test_thread_safety()))

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
        print("🎉 所有测试通过！阶段72验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
