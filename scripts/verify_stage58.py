#!/usr/bin/env python3
"""
阶段58验证脚本：缓存系统

测试内容：
1. LRU缓存
2. TTL缓存
3. 内存缓存
4. 缓存管理器
5. 缓存装饰器
6. 缓存淘汰
7. 过期清理
8. 统计信息
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.cache_system import (
    BaseCache,
    CacheEntry,
    CacheManager,
    LRUCache,
    MemoryCache,
    TTLCache,
    cached,
)


def test_lru_cache() -> bool:
    print("[Test] LRUCache - LRU缓存")
    try:
        cache = LRUCache[str, str](capacity=3, name="test_lru")

        cache.set("a", "A")
        cache.set("b", "B")
        cache.set("c", "C")
        assert cache.size() == 3
        print("  ✓ 设置3个项，容量正确")

        # 访问a，使其成为最新
        assert cache.get("a") == "A"
        cache.set("d", "D")
        # b应该被淘汰
        assert cache.get("b") is None
        assert cache.get("a") == "A"
        assert cache.get("c") == "C"
        assert cache.get("d") == "D"
        print("  ✓ LRU淘汰正确（b被淘汰）")

        # 删除
        assert cache.delete("a")
        assert cache.get("a") is None
        assert not cache.delete("x")
        print("  ✓ 删除功能正常")

        # 清空
        cache.clear()
        assert cache.size() == 0
        print("  ✓ 清空功能正常")

        # 统计（新建缓存避免前面操作影响）
        cache2 = LRUCache[str, str](capacity=3, name="test_lru2")
        cache2.set("x", "X")
        cache2.get("x")
        cache2.get("y")  # miss
        stats = cache2.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0
        print(f"  ✓ 统计正确: {stats}")

        print("[Pass] LRUCache\n")
        return True
    except Exception as e:
        print(f"[Fail] LRUCache: {e}\n")
        return False


def test_ttl_cache() -> bool:
    print("[Test] TTLCache - TTL缓存")
    try:
        cache = TTLCache[str, str](default_ttl=0.2, max_size=10, name="test_ttl")

        cache.set("a", "A")
        assert cache.get("a") == "A"
        print("  ✓ 设置并获取正常")

        # 等待过期
        time.sleep(0.25)
        assert cache.get("a") is None
        print("  ✓ TTL过期后获取为None")

        # 自定义TTL
        cache.set("b", "B", ttl=0.5)
        assert cache.get("b") == "B"
        time.sleep(0.25)
        assert cache.get("b") == "B"  # 还未过期
        print("  ✓ 自定义TTL正常")

        time.sleep(0.3)
        assert cache.get("b") is None
        print("  ✓ 自定义TTL过期正常")

        # ttl方法
        cache.set("c", "C", ttl=1.0)
        remaining = cache.ttl("c")
        assert remaining is not None and remaining > 0.9
        print(f"  ✓ 剩余TTL查询正常: {remaining:.3f}s")

        # 过期清理
        cache.set("d", "D", ttl=0.1)
        time.sleep(0.15)
        keys = cache.keys()  # 触发清理
        assert "d" not in keys
        print("  ✓ 过期清理正常")

        print("[Pass] TTLCache\n")
        return True
    except Exception as e:
        print(f"[Fail] TTLCache: {e}\n")
        return False


def test_memory_cache() -> bool:
    print("[Test] MemoryCache - 内存缓存")
    try:
        cache = MemoryCache[str, int](max_size=5, default_ttl=0.3, name="test_mem")

        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        print("  ✓ 基本存取正常")

        # 默认TTL
        time.sleep(0.35)
        assert cache.get("a") is None
        print("  ✓ 默认TTL过期正常")

        # 覆盖默认TTL
        cache.set("c", 3, ttl=1.0)
        time.sleep(0.35)
        assert cache.get("c") == 3
        print("  ✓ 覆盖默认TTL正常")

        # 容量限制
        cache.clear()
        cache.set("1", 1)
        cache.set("2", 2)
        cache.set("3", 3)
        cache.set("4", 4)
        cache.set("5", 5)
        cache.set("6", 6)  # 应淘汰1
        assert cache.get("1") is None
        assert cache.get("6") == 6
        print("  ✓ 容量限制淘汰正常")

        # get_or_set
        cache.clear()
        value = cache.get_or_set("key", lambda: 42)
        assert value == 42
        value2 = cache.get_or_set("key", lambda: 99)
        assert value2 == 42  # 缓存命中
        print("  ✓ get_or_set正常")

        print("[Pass] MemoryCache\n")
        return True
    except Exception as e:
        print(f"[Fail] MemoryCache: {e}\n")
        return False


def test_cache_manager() -> bool:
    print("[Test] CacheManager - 缓存管理器")
    try:
        manager = CacheManager()

        lru = manager.create_lru("users", 100)
        ttl = manager.create_ttl("sessions", 3600)
        mem = manager.create_memory("data", 50)

        lru.set("u1", "Alice")
        ttl.set("s1", "session1")
        mem.set("d1", "data1")

        assert manager.get("users") is lru
        assert manager.get("sessions") is ttl
        assert manager.get("data") is mem
        print("  ✓ 缓存创建和获取正常")

        stats = manager.get_all_stats()
        assert "users" in stats
        assert "sessions" in stats
        assert "data" in stats
        print(f"  ✓ 全局统计正常: {list(stats.keys())}")

        manager.clear_all()
        assert lru.size() == 0
        assert ttl.size() == 0
        assert mem.size() == 0
        print("  ✓ 全局清空正常")

        assert manager.remove("users")
        assert manager.get("users") is None
        print("  ✓ 移除缓存正常")

        print("[Pass] CacheManager\n")
        return True
    except Exception as e:
        print(f"[Fail] CacheManager: {e}\n")
        return False


def test_cache_decorator() -> bool:
    print("[Test] cached - 缓存装饰器")
    try:
        cache = MemoryCache[str, int]()
        call_count = 0

        @cached(cache)
        def slow_add(a: int, b: int) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        result = slow_add(1, 2)
        assert result == 3
        assert call_count == 1
        print("  ✓ 首次调用执行函数")

        result2 = slow_add(1, 2)
        assert result2 == 3
        assert call_count == 1  # 缓存命中，未再执行
        print("  ✓ 缓存命中，未重复执行")

        # 不同参数
        result3 = slow_add(2, 3)
        assert result3 == 5
        assert call_count == 2
        print("  ✓ 不同参数正确区分")

        # 自定义key_func
        cache2 = MemoryCache[str, str]()

        @cached(cache2, key_func=lambda x: f"prefix_{x}")
        def greet(name: str) -> str:
            return f"Hello {name}"

        greet("Alice")
        assert cache2.get("prefix_Alice") == "Hello Alice"
        print("  ✓ 自定义key_func正常")

        print("[Pass] cached decorator\n")
        return True
    except Exception as e:
        print(f"[Fail] cached decorator: {e}\n")
        return False


def test_cache_entry() -> bool:
    print("[Test] CacheEntry - 缓存条目")
    try:
        entry = CacheEntry("value")
        assert entry.value == "value"
        assert not entry.is_expired()
        print("  ✓ 基本条目正常")

        entry2 = CacheEntry("value", expires_at=time.monotonic() + 0.1)
        assert not entry2.is_expired()
        time.sleep(0.15)
        assert entry2.is_expired()
        print("  ✓ 过期判断正常")

        print("[Pass] CacheEntry\n")
        return True
    except Exception as e:
        print(f"[Fail] CacheEntry: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] 线程安全")
    try:
        import threading

        cache = MemoryCache[int, int](max_size=100)
        errors = []

        def writer():
            try:
                for i in range(50):
                    cache.set(i, i * 2)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    cache.get(i)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        print(f"  ✓ 10线程并发读写无错误，缓存大小: {cache.size()}")

        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def test_stats_reset() -> bool:
    print("[Test] 统计重置")
    try:
        cache = LRUCache[str, str](capacity=10)
        cache.set("a", "A")
        cache.get("a")
        cache.get("b")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

        cache.reset_stats()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        print("  ✓ 统计重置正常")

        print("[Pass] Stats Reset\n")
        return True
    except Exception as e:
        print(f"[Fail] Stats Reset: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段58验证脚本：缓存系统")
    print("=" * 60 + "\n")

    results = []
    results.append(("CacheEntry", test_cache_entry()))
    results.append(("LRUCache", test_lru_cache()))
    results.append(("TTLCache", test_ttl_cache()))
    results.append(("MemoryCache", test_memory_cache()))
    results.append(("CacheManager", test_cache_manager()))
    results.append(("cached decorator", test_cache_decorator()))
    results.append(("Thread Safety", test_thread_safety()))
    results.append(("Stats Reset", test_stats_reset()))

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
        print("🎉 所有测试通过！阶段58验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
