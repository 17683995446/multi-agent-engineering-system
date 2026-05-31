#!/usr/bin/env python3
"""
阶段59验证脚本：连接池管理

测试内容：
1. 连接池初始化
2. 连接获取与归还
3. 连接池上限
4. 连接超时
5. 连接验证
6. 连接池关闭
7. 连接池调整大小
8. 连接池装饰器
9. 线程安全
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.connection_pool import (
    ConnectionPool,
    ConnectionTimeout,
    MockConnection,
    MockConnectionPool,
    PoolConfig,
    PoolExhausted,
    pooled,
)


def test_pool_init() -> bool:
    print("[Test] 连接池初始化")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=5, min_size=2),
            name="test_init"
        )
        stats = pool.get_stats()
        assert stats["max_size"] == 5
        assert stats["pool_size"] == 2  # min_size
        assert stats["total_created"] == 2
        print(f"  ✓ 初始化统计: {stats}")

        pool.shutdown()
        print("[Pass] Pool Init\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Init: {e}\n")
        return False


def test_acquire_release() -> bool:
    print("[Test] 连接获取与归还")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=3, min_size=1),
            name="test_ar"
        )

        conn1 = pool.acquire()
        assert conn1 is not None
        assert conn1.active
        print(f"  ✓ 获取连接: {conn1}")

        stats = pool.get_stats()
        assert stats["in_use"] == 1
        assert stats["total_borrowed"] == 1
        print(f"  ✓ 获取后统计: {stats}")

        pool.release(conn1)
        stats = pool.get_stats()
        assert stats["in_use"] == 0
        assert stats["total_returned"] == 1
        assert stats["pool_size"] == 1
        print(f"  ✓ 归还后统计: {stats}")

        pool.shutdown()
        print("[Pass] Acquire/Release\n")
        return True
    except Exception as e:
        print(f"[Fail] Acquire/Release: {e}\n")
        return False


def test_pool_limit() -> bool:
    print("[Test] 连接池上限")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=2, min_size=0),
            name="test_limit"
        )

        conn1 = pool.acquire()
        conn2 = pool.acquire()
        print(f"  ✓ 获取2个连接")

        # 第3个应该超时
        try:
            pool.acquire(timeout=0.1)
            assert False, "应抛出ConnectionTimeout"
        except ConnectionTimeout:
            print("  ✓ 超出上限时超时")

        pool.release(conn1)
        conn3 = pool.acquire(timeout=0.5)
        assert conn3 is not None
        print(f"  ✓ 释放后可再获取")

        pool.release(conn2)
        pool.release(conn3)
        pool.shutdown()
        print("[Pass] Pool Limit\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Limit: {e}\n")
        return False


def test_connection_reuse() -> bool:
    print("[Test] 连接复用")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=2, min_size=1),
            name="test_reuse"
        )

        conn1 = pool.acquire()
        conn_id = conn1.id
        pool.release(conn1)

        conn2 = pool.acquire()
        assert conn2.id == conn_id  # 复用同一个连接
        print(f"  ✓ 连接复用: id={conn_id}")

        pool.release(conn2)
        pool.shutdown()
        print("[Pass] Connection Reuse\n")
        return True
    except Exception as e:
        print(f"[Fail] Connection Reuse: {e}\n")
        return False


def test_connection_validation() -> bool:
    print("[Test] 连接验证")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=2, min_size=1, validate_on_borrow=True),
            name="test_validate"
        )

        conn = pool.acquire()
        conn.active = False  # 模拟连接失效
        pool.release(conn)

        # 再次获取应该创建新连接（旧连接被验证失败销毁）
        conn2 = pool.acquire()
        assert conn2.active
        assert conn2.id != conn.id
        print(f"  ✓ 失效连接被替换: 旧id={conn.id}, 新id={conn2.id}")

        pool.release(conn2)
        pool.shutdown()
        print("[Pass] Connection Validation\n")
        return True
    except Exception as e:
        print(f"[Fail] Connection Validation: {e}\n")
        return False


def test_pool_shutdown() -> bool:
    print("[Test] 连接池关闭")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=3, min_size=2),
            name="test_shutdown"
        )

        conn1 = pool.acquire()
        conn2 = pool.acquire()
        pool.release(conn1)

        pool.shutdown()
        stats = pool.get_stats()
        assert stats["pool_size"] == 0
        assert stats["in_use"] == 0
        print(f"  ✓ 关闭后统计: {stats}")

        # 关闭后不能获取
        try:
            pool.acquire()
            assert False, "应抛出PoolExhausted"
        except PoolExhausted:
            print("  ✓ 关闭后获取抛出异常")

        print("[Pass] Pool Shutdown\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Shutdown: {e}\n")
        return False


def test_pool_resize() -> bool:
    print("[Test] 连接池调整大小")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=5, min_size=3),
            name="test_resize"
        )

        stats = pool.get_stats()
        assert stats["pool_size"] == 3
        print(f"  ✓ 初始大小: {stats['pool_size']}")

        pool.resize(2)
        stats = pool.get_stats()
        assert stats["max_size"] == 2
        # 空闲连接可能被销毁
        print(f"  ✓ 调整后统计: {stats}")

        pool.shutdown()
        print("[Pass] Pool Resize\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Resize: {e}\n")
        return False


def test_pool_decorator() -> bool:
    print("[Test] 连接池装饰器")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=2, min_size=1),
            name="test_decorator"
        )

        @pooled(pool)
        def do_work(conn, value):
            return f"Connection({conn.id}) processed {value}"

        result = do_work(42)
        assert "Connection(" in result
        assert "42" in result
        print(f"  ✓ 装饰器结果: {result}")

        stats = pool.get_stats()
        assert stats["total_borrowed"] == 1
        assert stats["total_returned"] == 1
        print(f"  ✓ 装饰器自动归还: {stats}")

        pool.shutdown()
        print("[Pass] Pool Decorator\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Decorator: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] 线程安全")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=5, min_size=2),
            name="test_thread"
        )
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    conn = pool.acquire(timeout=2.0)
                    time.sleep(0.01)
                    results.append(conn.id)
                    pool.release(conn)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        assert len(results) == 100
        print(f"  ✓ 100次并发获取/归还完成")

        stats = pool.get_stats()
        print(f"  ✓ 最终统计: {stats}")

        pool.shutdown()
        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def test_idle_timeout() -> bool:
    print("[Test] 空闲超时")
    try:
        pool = MockConnectionPool(
            config=PoolConfig(max_size=2, min_size=1, max_idle_time=0.1),
            name="test_idle"
        )

        conn = pool.acquire()
        pool.release(conn)

        # 等待空闲超时
        time.sleep(0.15)

        conn2 = pool.acquire()
        # 旧连接应该被销毁，新连接ID不同
        assert conn2.id != conn.id
        print(f"  ✓ 空闲连接被销毁，新连接id={conn2.id}")

        pool.release(conn2)
        pool.shutdown()
        print("[Pass] Idle Timeout\n")
        return True
    except Exception as e:
        print(f"[Fail] Idle Timeout: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段59验证脚本：连接池管理")
    print("=" * 60 + "\n")

    results = []
    results.append(("Pool Init", test_pool_init()))
    results.append(("Acquire/Release", test_acquire_release()))
    results.append(("Pool Limit", test_pool_limit()))
    results.append(("Connection Reuse", test_connection_reuse()))
    results.append(("Connection Validation", test_connection_validation()))
    results.append(("Pool Shutdown", test_pool_shutdown()))
    results.append(("Pool Resize", test_pool_resize()))
    results.append(("Pool Decorator", test_pool_decorator()))
    results.append(("Thread Safety", test_thread_safety()))
    results.append(("Idle Timeout", test_idle_timeout()))

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
        print("🎉 所有测试通过！阶段59验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
