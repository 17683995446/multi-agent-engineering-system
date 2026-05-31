#!/usr/bin/env python3
"""
阶段57验证脚本：重试机制

测试内容：
1. 指数退避策略
2. 固定间隔策略
3. 随机抖动策略
4. 线性退避策略
5. 重试执行器
6. 重试装饰器
7. 降级策略
8. 异常过滤
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.retry_mechanism import (
    BaseRetryPolicy,
    ExponentialBackoffPolicy,
    FixedIntervalPolicy,
    LinearBackoffPolicy,
    RandomJitterPolicy,
    RetryConfig,
    RetryExhausted,
    RetryExecutor,
    RetryPolicyFactory,
    RetryStrategy,
    retry,
    retry_with_fallback,
)


def test_exponential_backoff() -> bool:
    print("[Test] ExponentialBackoffPolicy - 指数退避策略")
    try:
        config = RetryConfig(max_retries=5, base_delay=1.0, max_delay=10.0, jitter=False)
        policy = ExponentialBackoffPolicy(config)

        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(3) == 4.0
        assert policy.calculate_delay(4) == 8.0
        assert policy.calculate_delay(5) == 10.0  # 被max_delay限制
        print("  ✓ 延迟计算正确: 1.0, 2.0, 4.0, 8.0, 10.0")

        # 带jitter
        config2 = RetryConfig(max_retries=3, base_delay=1.0, jitter=True, jitter_max=0.5)
        policy2 = ExponentialBackoffPolicy(config2)
        d = policy2.calculate_delay(1)
        assert 1.0 <= d <= 1.5
        print(f"  ✓ 抖动延迟范围正确: {d:.3f}s")

        print("[Pass] ExponentialBackoffPolicy\n")
        return True
    except Exception as e:
        print(f"[Fail] ExponentialBackoffPolicy: {e}\n")
        return False


def test_fixed_interval() -> bool:
    print("[Test] FixedIntervalPolicy - 固定间隔策略")
    try:
        config = RetryConfig(max_retries=3, base_delay=2.0, jitter=False)
        policy = FixedIntervalPolicy(config)

        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(3) == 2.0
        print("  ✓ 固定延迟正确: 2.0s")

        print("[Pass] FixedIntervalPolicy\n")
        return True
    except Exception as e:
        print(f"[Fail] FixedIntervalPolicy: {e}\n")
        return False


def test_random_jitter() -> bool:
    print("[Test] RandomJitterPolicy - 随机抖动策略")
    try:
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=False)
        policy = RandomJitterPolicy(config)

        for i in range(1, 4):
            d = policy.calculate_delay(i)
            assert 1.0 <= d <= 5.0
        print("  ✓ 随机延迟在范围内 [1.0, 5.0]")

        print("[Pass] RandomJitterPolicy\n")
        return True
    except Exception as e:
        print(f"[Fail] RandomJitterPolicy: {e}\n")
        return False


def test_linear_backoff() -> bool:
    print("[Test] LinearBackoffPolicy - 线性退避策略")
    try:
        config = RetryConfig(max_retries=5, base_delay=1.0, max_delay=10.0, jitter=False)
        policy = LinearBackoffPolicy(config)

        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(2) == 2.0
        assert policy.calculate_delay(3) == 3.0
        assert policy.calculate_delay(10) == 10.0  # 被max_delay限制
        print("  ✓ 线性延迟正确: 1.0, 2.0, 3.0, ..., 10.0")

        print("[Pass] LinearBackoffPolicy\n")
        return True
    except Exception as e:
        print(f"[Fail] LinearBackoffPolicy: {e}\n")
        return False


def test_factory() -> bool:
    print("[Test] RetryPolicyFactory - 重试策略工厂")
    try:
        c1 = RetryConfig(strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
        p1 = RetryPolicyFactory.create(c1)
        assert isinstance(p1, ExponentialBackoffPolicy)
        print("  ✓ 指数退避创建通过")

        c2 = RetryConfig(strategy=RetryStrategy.FIXED_INTERVAL)
        p2 = RetryPolicyFactory.create(c2)
        assert isinstance(p2, FixedIntervalPolicy)
        print("  ✓ 固定间隔创建通过")

        c3 = RetryConfig(strategy=RetryStrategy.RANDOM_JITTER)
        p3 = RetryPolicyFactory.create(c3)
        assert isinstance(p3, RandomJitterPolicy)
        print("  ✓ 随机抖动创建通过")

        c4 = RetryConfig(strategy=RetryStrategy.LINEAR_BACKOFF)
        p4 = RetryPolicyFactory.create(c4)
        assert isinstance(p4, LinearBackoffPolicy)
        print("  ✓ 线性退避创建通过")

        try:
            RetryPolicyFactory.create(RetryConfig(strategy="unknown"))  # type: ignore[arg-type]
            assert False, "应抛出ValueError"
        except ValueError:
            print("  ✓ 未知策略异常捕获")

        print("[Pass] RetryPolicyFactory\n")
        return True
    except Exception as e:
        print(f"[Fail] RetryPolicyFactory: {e}\n")
        return False


def test_retry_executor() -> bool:
    print("[Test] RetryExecutor - 重试执行器")
    try:
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"fail {call_count}")
            return "success"

        config = RetryConfig(
            max_retries=3,
            base_delay=0.05,
            strategy=RetryStrategy.FIXED_INTERVAL,
            jitter=False,
            retryable_exceptions=(ValueError,),
        )
        executor = RetryExecutor(config)
        result = executor.execute(flaky)
        assert result == "success"
        assert call_count == 3
        print(f"  ✓ 重试3次后成功")

        stats = executor.get_stats()
        assert stats["total_calls"] == 1
        assert stats["successful_calls"] == 1
        print(f"  ✓ 统计: {stats}")

        # 测试不可重试异常
        call_count = 0

        def not_retryable():
            raise RuntimeError("no retry")

        config2 = RetryConfig(
            max_retries=3,
            retryable_exceptions=(ValueError,),
        )
        executor2 = RetryExecutor(config2)
        try:
            executor2.execute(not_retryable)
            assert False, "应抛出RuntimeError"
        except RuntimeError:
            print("  ✓ 不可重试异常直接抛出")

        print("[Pass] RetryExecutor\n")
        return True
    except Exception as e:
        print(f"[Fail] RetryExecutor: {e}\n")
        return False


def test_retry_decorator() -> bool:
    print("[Test] retry - 重试装饰器")
    try:
        call_count = 0

        @retry(max_retries=3, base_delay=0.05, strategy="fixed_interval", jitter=False, retryable_exceptions=(ValueError,))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"fail {call_count}")
            return "ok"

        result = flaky_func()
        assert result == "ok"
        assert call_count == 3
        print(f"  ✓ 装饰器重试成功，调用次数: {call_count}")

        stats = flaky_func.get_retry_stats()
        assert stats["total_calls"] == 1
        print(f"  ✓ 装饰器统计: {stats}")

        # 测试重试耗尽
        call_count2 = 0

        @retry(max_retries=2, base_delay=0.01, strategy="fixed_interval", jitter=False)
        def always_fail():
            nonlocal call_count2
            call_count2 += 1
            raise ValueError("always fail")

        try:
            always_fail()
            assert False, "应抛出RetryExhausted"
        except RetryExhausted as e:
            assert e.attempts == 2
            print(f"  ✓ 重试耗尽异常: attempts={e.attempts}")

        print("[Pass] retry decorator\n")
        return True
    except Exception as e:
        print(f"[Fail] retry decorator: {e}\n")
        return False


def test_fallback() -> bool:
    print("[Test] retry_with_fallback - 降级策略")
    try:
        call_count = 0

        @retry_with_fallback(fallback=lambda: "fallback_result", max_retries=2, base_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        result = always_fail()
        assert result == "fallback_result"
        assert call_count == 2  # 初始1次 + 1次重试（第2次重试后attempt=2达到max_retries，抛出RetryExhausted）
        print(f"  ✓ 降级执行成功，原始调用{call_count}次")

        # 成功时不走降级
        @retry_with_fallback(fallback=lambda: "fallback", max_retries=2, base_delay=0.01)
        def always_success():
            return "success"

        result2 = always_success()
        assert result2 == "success"
        print("  ✓ 成功时不走降级")

        print("[Pass] retry_with_fallback\n")
        return True
    except Exception as e:
        print(f"[Fail] retry_with_fallback: {e}\n")
        return False


def test_exception_filtering() -> bool:
    print("[Test] 异常过滤")
    try:
        # ValueError可重试，RuntimeError不可重试
        config = RetryConfig(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        policy = RetryPolicyFactory.create(config)

        assert policy.should_retry(ValueError("test"), 0)
        assert not policy.should_retry(RuntimeError("test"), 0)
        print("  ✓ 异常类型过滤正确")

        # 超过max_retries不应重试
        assert not policy.should_retry(ValueError("test"), 3)
        print("  ✓ 超过最大重试次数不重试")

        print("[Pass] Exception Filtering\n")
        return True
    except Exception as e:
        print(f"[Fail] Exception Filtering: {e}\n")
        return False


def test_callbacks() -> bool:
    print("[Test] 回调通知")
    try:
        retry_events = []
        success_events = []

        def on_retry(exc, attempt, delay):
            retry_events.append((attempt, delay))

        def on_success(result, attempt):
            success_events.append((result, attempt))

        config = RetryConfig(
            max_retries=3,
            base_delay=0.05,
            strategy=RetryStrategy.FIXED_INTERVAL,
            jitter=False,
            retryable_exceptions=(ValueError,),
            on_retry=on_retry,
            on_success=on_success,
        )

        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "done"

        executor = RetryExecutor(config)
        result = executor.execute(flaky)

        assert len(retry_events) == 2
        assert retry_events[0][0] == 1
        assert retry_events[1][0] == 2
        print(f"  ✓ 重试回调触发2次: {retry_events}")

        assert len(success_events) == 1
        assert success_events[0] == ("done", 2)
        print(f"  ✓ 成功回调触发: {success_events}")

        print("[Pass] Callbacks\n")
        return True
    except Exception as e:
        print(f"[Fail] Callbacks: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段57验证脚本：重试机制")
    print("=" * 60 + "\n")

    results = []
    results.append(("ExponentialBackoffPolicy", test_exponential_backoff()))
    results.append(("FixedIntervalPolicy", test_fixed_interval()))
    results.append(("RandomJitterPolicy", test_random_jitter()))
    results.append(("LinearBackoffPolicy", test_linear_backoff()))
    results.append(("RetryPolicyFactory", test_factory()))
    results.append(("RetryExecutor", test_retry_executor()))
    results.append(("retry decorator", test_retry_decorator()))
    results.append(("retry_with_fallback", test_fallback()))
    results.append(("Exception Filtering", test_exception_filtering()))
    results.append(("Callbacks", test_callbacks()))

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
        print("🎉 所有测试通过！阶段57验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
