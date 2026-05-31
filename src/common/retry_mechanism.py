"""
公共层 - 重试机制模块
职责：提供指数退避、固定间隔、随机抖动、最大重试次数等重试策略
依赖规则：仅依赖公共层 utils
"""

from __future__ import annotations

import functools
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Type, Union

from common.utils import setup_logger


class RetryStrategy(Enum):
    """重试策略枚举"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_INTERVAL = "fixed_interval"
    RANDOM_JITTER = "random_jitter"
    LINEAR_BACKOFF = "linear_backoff"


class RetryExhausted(Exception):
    """重试耗尽异常"""
    def __init__(self, message: str, last_exception: Optional[Exception] = None, attempts: int = 0):
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(message)


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    jitter_max: float = 0.5
    retryable_exceptions: tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
    on_success: Optional[Callable[[Any, int], None]] = None


class BaseRetryPolicy(ABC):
    """重试策略抽象基类"""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = setup_logger("common.retry_mechanism")

    @abstractmethod
    def calculate_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的等待时间（秒）"""

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries:
            return False
        return isinstance(exception, self.config.retryable_exceptions)

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """执行带重试的函数"""
        attempt = 0
        last_exception: Optional[Exception] = None

        while True:
            try:
                result = func(*args, **kwargs)
                if self.config.on_success:
                    self.config.on_success(result, attempt)
                return result
            except Exception as e:
                last_exception = e
                if not self.should_retry(e, attempt):
                    raise

                attempt += 1
                delay = self.calculate_delay(attempt)

                if self.config.on_retry:
                    self.config.on_retry(e, attempt, delay)
                else:
                    self.logger.warning(
                        f"Retry {attempt}/{self.config.max_retries} after {delay:.3f}s: {e}"
                    )

                time.sleep(delay)

                if attempt >= self.config.max_retries:
                    raise RetryExhausted(
                        f"Failed after {attempt} attempts: {e}",
                        last_exception=last_exception,
                        attempts=attempt,
                    ) from e


class ExponentialBackoffPolicy(BaseRetryPolicy):
    """
    指数退避策略

    delay = min(max_delay, base_delay * 2^(attempt-1))
    """

    def calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * (2 ** (attempt - 1))
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            delay += random.uniform(0, self.config.jitter_max)
        return delay


class FixedIntervalPolicy(BaseRetryPolicy):
    """
    固定间隔策略

    delay = base_delay (+ jitter)
    """

    def calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay
        if self.config.jitter:
            delay += random.uniform(0, self.config.jitter_max)
        return delay


class RandomJitterPolicy(BaseRetryPolicy):
    """
    随机抖动策略

    delay = random(base_delay, max_delay)
    """

    def calculate_delay(self, attempt: int) -> float:
        delay = random.uniform(self.config.base_delay, self.config.max_delay)
        if self.config.jitter:
            delay += random.uniform(0, self.config.jitter_max)
        return delay


class LinearBackoffPolicy(BaseRetryPolicy):
    """
    线性退避策略

    delay = base_delay * attempt
    """

    def calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * attempt
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            delay += random.uniform(0, self.config.jitter_max)
        return delay


class RetryPolicyFactory:
    """重试策略工厂"""

    @staticmethod
    def create(config: RetryConfig) -> BaseRetryPolicy:
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return ExponentialBackoffPolicy(config)
        elif config.strategy == RetryStrategy.FIXED_INTERVAL:
            return FixedIntervalPolicy(config)
        elif config.strategy == RetryStrategy.RANDOM_JITTER:
            return RandomJitterPolicy(config)
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            return LinearBackoffPolicy(config)
        else:
            raise ValueError(f"Unknown strategy: {config.strategy}")


class RetryExecutor:
    """
    重试执行器

    提供高级重试功能：
    - 条件重试
    - 回调通知
    - 统计收集
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.policy = RetryPolicyFactory.create(self.config)
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
        }

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """执行函数，带重试"""
        self._stats["total_calls"] += 1
        try:
            result = self.policy.execute(func, *args, **kwargs)
            self._stats["successful_calls"] += 1
            return result
        except RetryExhausted:
            self._stats["failed_calls"] += 1
            raise
        except Exception:
            self._stats["failed_calls"] += 1
            raise

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计"""
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
        }


def retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy | str = RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter: bool = True,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        strategy: 重试策略
        jitter: 是否启用抖动
        retryable_exceptions: 可重试的异常类型
    """
    if isinstance(strategy, str):
        strategy = RetryStrategy(strategy)

    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=strategy,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func: Callable) -> Callable:
        executor = RetryExecutor(config)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return executor.execute(func, *args, **kwargs)

        wrapper._retry_executor = executor
        wrapper.get_retry_stats = executor.get_stats
        return wrapper

    return decorator


def retry_with_fallback(
    fallback: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy | str = RetryStrategy.EXPONENTIAL_BACKOFF,
) -> Callable:
    """
    带降级策略的重试装饰器

    当所有重试都失败时，执行 fallback 函数
    """
    if isinstance(strategy, str):
        strategy = RetryStrategy(strategy)

    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        strategy=strategy,
    )

    def decorator(func: Callable) -> Callable:
        policy = RetryPolicyFactory.create(config)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return policy.execute(func, *args, **kwargs)
            except RetryExhausted:
                return fallback(*args, **kwargs)

        return wrapper

    return decorator


def demo_retry_mechanism():
    """演示重试机制"""
    print("=" * 60)
    print("重试机制模块验证")
    print("=" * 60)
    print()

    # 1. 指数退避
    print("1. 指数退避策略:")
    config = RetryConfig(max_retries=3, base_delay=0.1, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
    policy = ExponentialBackoffPolicy(config)
    for i in range(1, 4):
        print(f"   第{i}次延迟: {policy.calculate_delay(i):.3f}s")
    print()

    # 2. 固定间隔
    print("2. 固定间隔策略:")
    config2 = RetryConfig(max_retries=3, base_delay=0.2, strategy=RetryStrategy.FIXED_INTERVAL, jitter=False)
    policy2 = FixedIntervalPolicy(config2)
    for i in range(1, 4):
        print(f"   第{i}次延迟: {policy2.calculate_delay(i):.3f}s")
    print()

    # 3. 线性退避
    print("3. 线性退避策略:")
    config3 = RetryConfig(max_retries=3, base_delay=0.1, strategy=RetryStrategy.LINEAR_BACKOFF, jitter=False)
    policy3 = LinearBackoffPolicy(config3)
    for i in range(1, 4):
        print(f"   第{i}次延迟: {policy3.calculate_delay(i):.3f}s")
    print()

    # 4. 装饰器
    print("4. 重试装饰器:")
    call_count = 0

    @retry(max_retries=3, base_delay=0.05, retryable_exceptions=(ValueError,))
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError(f"失败第{call_count}次")
        return "成功"

    result = flaky_function()
    print(f"   结果: {result}, 调用次数: {call_count}")
    print()

    # 5. 带降级
    print("5. 降级策略:")

    @retry_with_fallback(fallback=lambda: "降级结果", max_retries=2, base_delay=0.05)
    def always_fail():
        raise RuntimeError("总是失败")

    result = always_fail()
    print(f"   结果: {result}")
    print()

    print("=" * 60)
    print("重试机制模块验证成功")
    print("=" * 60)


if __name__ == "__main__":
    demo_retry_mechanism()
