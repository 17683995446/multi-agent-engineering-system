#!/usr/bin/env python3
"""
阶段56验证脚本：限流器

测试内容：
1. 令牌桶限流器
2. 漏桶限流器
3. 固定窗口限流器
4. 滑动窗口限流器
5. 并发限流器
6. 限流器工厂
7. 限流装饰器
8. 阻塞获取与超时
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.rate_limiter import (
    BaseRateLimiter,
    ConcurrencyLimiter,
    FixedWindowLimiter,
    LeakyBucketLimiter,
    RateLimitExceeded,
    RateLimiterFactory,
    RateLimitStrategy,
    SlidingWindowLimiter,
    TokenBucketLimiter,
    rate_limit,
)


def test_token_bucket() -> bool:
    print("[Test] TokenBucketLimiter - 令牌桶限流器")
    try:
        tb = TokenBucketLimiter(rate=10, capacity=5, name="test_tb")
        # 初始有5个令牌，前5个应通过
        for i in range(5):
            assert tb.allow(), f"请求{i+1}应通过"
        print("  ✓ 前5个请求通过（桶容量）")

        # 第6个应拒绝
        assert not tb.allow(), "第6个请求应拒绝"
        print("  ✓ 第6个请求拒绝（桶空）")

        # 等待补充令牌
        time.sleep(0.3)
        assert tb.allow(), "等待后应有新令牌"
        print("  ✓ 等待补充后请求通过")

        # 统计
        stats = tb.get_stats()
        assert stats["strategy"] == "token_bucket"
        assert stats["capacity"] == 5
        assert stats["rate"] == 10
        print(f"  ✓ 统计信息: {stats}")

        # 重置
        tb.reset_stats()
        stats = tb.get_stats()
        assert stats["total_requests"] == 0
        print("  ✓ 统计重置通过")

        print("[Pass] TokenBucketLimiter\n")
        return True
    except Exception as e:
        print(f"[Fail] TokenBucketLimiter: {e}\n")
        return False


def test_leaky_bucket() -> bool:
    print("[Test] LeakyBucketLimiter - 漏桶限流器")
    try:
        lb = LeakyBucketLimiter(rate=100, capacity=3, name="test_lb")
        # 前3个应通过
        for i in range(3):
            assert lb.allow(), f"请求{i+1}应通过"
        print("  ✓ 前3个请求通过（桶容量）")

        # 第4个应拒绝
        assert not lb.allow(), "第4个请求应拒绝"
        print("  ✓ 第4个请求拒绝（桶满）")

        # 等待漏出
        time.sleep(0.03)
        assert lb.allow(), "等待漏出后应通过"
        print("  ✓ 等待漏出后请求通过")

        stats = lb.get_stats()
        assert stats["strategy"] == "leaky_bucket"
        print(f"  ✓ 统计信息: {stats}")

        print("[Pass] LeakyBucketLimiter\n")
        return True
    except Exception as e:
        print(f"[Fail] LeakyBucketLimiter: {e}\n")
        return False


def test_fixed_window() -> bool:
    print("[Test] FixedWindowLimiter - 固定窗口限流器")
    try:
        fw = FixedWindowLimiter(limit=3, window_seconds=0.5, name="test_fw")
        for i in range(3):
            assert fw.allow(), f"请求{i+1}应通过"
        print("  ✓ 前3个请求通过（窗口限制）")

        assert not fw.allow(), "第4个请求应拒绝"
        print("  ✓ 第4个请求拒绝")

        # 等待窗口刷新
        time.sleep(0.55)
        assert fw.allow(), "窗口刷新后应通过"
        print("  ✓ 窗口刷新后请求通过")

        stats = fw.get_stats()
        assert stats["strategy"] == "fixed_window"
        print(f"  ✓ 统计信息: {stats}")

        print("[Pass] FixedWindowLimiter\n")
        return True
    except Exception as e:
        print(f"[Fail] FixedWindowLimiter: {e}\n")
        return False


def test_sliding_window() -> bool:
    print("[Test] SlidingWindowLimiter - 滑动窗口限流器")
    try:
        sw = SlidingWindowLimiter(limit=3, window_seconds=0.5, name="test_sw")
        for i in range(3):
            assert sw.allow(), f"请求{i+1}应通过"
        print("  ✓ 前3个请求通过")

        assert not sw.allow(), "第4个请求应拒绝"
        print("  ✓ 第4个请求拒绝")

        # 等待最老的请求滑出窗口
        time.sleep(0.55)
        assert sw.allow(), "滑出后应通过"
        print("  ✓ 滑动后请求通过")

        stats = sw.get_stats()
        assert stats["strategy"] == "sliding_window"
        print(f"  ✓ 统计信息: {stats}")

        print("[Pass] SlidingWindowLimiter\n")
        return True
    except Exception as e:
        print(f"[Fail] SlidingWindowLimiter: {e}\n")
        return False


def test_concurrency_limiter() -> bool:
    print("[Test] ConcurrencyLimiter - 并发限流器")
    try:
        cl = ConcurrencyLimiter(max_concurrency=2, name="test_cl")
        assert cl.allow()
        assert cl.allow()
        print("  ✓ 前2个并发获取通过")

        assert not cl.allow(), "第3个应拒绝"
        print("  ✓ 第3个并发获取拒绝")

        cl.release()
        assert cl.allow(), "释放后应能通过"
        print("  ✓ 释放后获取通过")

        # 上下文管理器
        with ConcurrencyLimiter(max_concurrency=1) as c:
            assert c.get_stats()["active_count"] == 1
        assert c.get_stats()["active_count"] == 0
        print("  ✓ 上下文管理器工作正常")

        # acquire阻塞超时
        cl2 = ConcurrencyLimiter(max_concurrency=1)
        cl2.acquire()
        start = time.monotonic()
        result = cl2.acquire(blocking=True, timeout=0.1)
        elapsed = time.monotonic() - start
        assert not result, "应超时失败"
        assert elapsed < 0.2, f"超时时间应接近0.1s，实际{elapsed}"
        print(f"  ✓ 阻塞超时正常 (elapsed={elapsed:.3f}s)")

        stats = cl.get_stats()
        assert stats["max_concurrency"] == 2
        print(f"  ✓ 统计信息: {stats}")

        print("[Pass] ConcurrencyLimiter\n")
        return True
    except Exception as e:
        print(f"[Fail] ConcurrencyLimiter: {e}\n")
        return False


def test_factory() -> bool:
    print("[Test] RateLimiterFactory - 限流器工厂")
    try:
        tb = RateLimiterFactory.create(RateLimitStrategy.TOKEN_BUCKET, rate=5, capacity=10)
        assert isinstance(tb, TokenBucketLimiter)
        print("  ✓ 令牌桶创建通过")

        lb = RateLimiterFactory.create("leaky_bucket", rate=5, capacity=10)
        assert isinstance(lb, LeakyBucketLimiter)
        print("  ✓ 漏桶创建通过（字符串策略）")

        fw = RateLimiterFactory.create("fixed_window", limit=10, window_seconds=60)
        assert isinstance(fw, FixedWindowLimiter)
        print("  ✓ 固定窗口创建通过")

        sw = RateLimiterFactory.create("sliding_window", limit=10, window_seconds=60)
        assert isinstance(sw, SlidingWindowLimiter)
        print("  ✓ 滑动窗口创建通过")

        try:
            RateLimiterFactory.create("unknown")
            assert False, "应抛出ValueError"
        except ValueError:
            print("  ✓ 未知策略异常捕获")

        print("[Pass] RateLimiterFactory\n")
        return True
    except Exception as e:
        print(f"[Fail] RateLimiterFactory: {e}\n")
        return False


def test_decorator() -> bool:
    print("[Test] rate_limit - 限流装饰器")
    try:
        limiter = TokenBucketLimiter(rate=100, capacity=2)

        @rate_limit(limiter, tokens=1, raise_on_limit=True)
        def api_call():
            return "ok"

        assert api_call() == "ok"
        assert api_call() == "ok"
        try:
            api_call()
            assert False, "应抛出RateLimitExceeded"
        except RateLimitExceeded:
            print("  ✓ 装饰器限流异常抛出正常")

        limiter2 = TokenBucketLimiter(rate=100, capacity=1)

        @rate_limit(limiter2, tokens=1, raise_on_limit=False)
        def api_call_no_raise():
            return "ok"

        assert api_call_no_raise() == "ok"
        result = api_call_no_raise()
        assert result is None
        print("  ✓ 装饰器不抛异常模式正常")

        print("[Pass] rate_limit decorator\n")
        return True
    except Exception as e:
        print(f"[Fail] rate_limit decorator: {e}\n")
        return False


def test_blocking_acquire() -> bool:
    print("[Test] acquire阻塞获取与超时")
    try:
        # 令牌桶阻塞
        tb = TokenBucketLimiter(rate=10, capacity=1)
        tb.allow()  # 消耗唯一令牌
        start = time.monotonic()
        result = tb.acquire(blocking=True, timeout=0.15)
        elapsed = time.monotonic() - start
        assert result, "应在超时前获取到令牌"
        assert elapsed >= 0.08, f"应等待一段时间补充令牌，实际{elapsed}"
        print(f"  ✓ 令牌桶阻塞获取通过 (elapsed={elapsed:.3f}s)")

        # 非阻塞
        tb2 = TokenBucketLimiter(rate=1, capacity=1)
        tb2.allow()
        result = tb2.acquire(blocking=False)
        assert not result, "非阻塞应直接返回False"
        print("  ✓ 非阻塞获取通过")

        # 固定窗口阻塞超时
        fw = FixedWindowLimiter(limit=1, window_seconds=1.0)
        fw.allow()
        start = time.monotonic()
        result = fw.acquire(blocking=True, timeout=0.1)
        elapsed = time.monotonic() - start
        assert not result, "应超时失败"
        assert elapsed < 0.2
        print(f"  ✓ 固定窗口超时正常 (elapsed={elapsed:.3f}s)")

        print("[Pass] Blocking Acquire\n")
        return True
    except Exception as e:
        print(f"[Fail] Blocking Acquire: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] 线程安全")
    try:
        tb = TokenBucketLimiter(rate=1000, capacity=100)
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    results.append(tb.allow())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        assert len(results) == 100
        # 通过的应不超过100
        passed = sum(results)
        assert passed <= 100, f"通过数{passed}超过容量"
        print(f"  ✓ 100次并发请求，通过{passed}次，拒绝{100-passed}次")

        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段56验证脚本：限流器")
    print("=" * 60 + "\n")

    results = []
    results.append(("TokenBucketLimiter", test_token_bucket()))
    results.append(("LeakyBucketLimiter", test_leaky_bucket()))
    results.append(("FixedWindowLimiter", test_fixed_window()))
    results.append(("SlidingWindowLimiter", test_sliding_window()))
    results.append(("ConcurrencyLimiter", test_concurrency_limiter()))
    results.append(("RateLimiterFactory", test_factory()))
    results.append(("rate_limit decorator", test_decorator()))
    results.append(("Blocking Acquire", test_blocking_acquire()))
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
        print("🎉 所有测试通过！阶段56验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
