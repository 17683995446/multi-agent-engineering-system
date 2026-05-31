"""
公共层 - 限流器模块
职责：提供令牌桶/漏桶算法、请求限流、并发限流
依赖规则：仅依赖公共层 utils
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from enum import Enum
from typing import Any, Callable, Optional

from common.utils import setup_logger


class RateLimitStrategy(Enum):
    """限流策略枚举"""
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"


class RateLimitExceeded(Exception):
    """限流异常"""
    def __init__(self, message: str = "Rate limit exceeded", wait_time: float = 0.0):
        self.wait_time = wait_time
        super().__init__(message)


class BaseRateLimiter(ABC):
    """限流器抽象基类"""

    def __init__(self, name: str = "rate_limiter"):
        self.name = name
        self.logger = setup_logger(f"common.rate_limiter.{name}")
        self._lock = threading.Lock()
        self._total_requests = 0
        self._rejected_requests = 0

    @abstractmethod
    def allow(self, tokens: int = 1) -> bool:
        """判断是否允许通过，返回True/False"""

    @abstractmethod
    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """获取令牌/许可，支持阻塞等待"""

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "rejected_requests": self._rejected_requests,
                "rejection_rate": round(self._rejected_requests / max(self._total_requests, 1) * 100, 2),
            }

    def reset_stats(self):
        """重置统计"""
        with self._lock:
            self._total_requests = 0
            self._rejected_requests = 0

    def _record_request(self, allowed: bool):
        self._total_requests += 1
        if not allowed:
            self._rejected_requests += 1


class TokenBucketLimiter(BaseRateLimiter):
    """
    令牌桶限流器

    原理：以固定速率向桶中添加令牌，请求消耗令牌，桶满则丢弃新令牌
    特点：允许一定程度的突发流量
    """

    def __init__(
        self,
        rate: float,
        capacity: float,
        name: str = "token_bucket",
    ):
        """
        Args:
            rate: 令牌产生速率（每秒）
            capacity: 桶容量（最大令牌数）
        """
        super().__init__(name)
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last_update = time.monotonic()

    def _add_tokens(self):
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_update = now

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            self._add_tokens()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._record_request(True)
                return True
            self._record_request(False)
            return False

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        if not blocking:
            return self.allow(tokens)

        start = time.monotonic()
        while True:
            with self._lock:
                self._add_tokens()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    self._record_request(True)
                    return True
                needed = tokens - self._tokens
                wait_time = needed / self.rate if self.rate > 0 else 1.0

            if timeout is not None:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    self._record_request(False)
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            time.sleep(wait_time)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        with self._lock:
            stats.update({
                "strategy": RateLimitStrategy.TOKEN_BUCKET.value,
                "rate": self.rate,
                "capacity": self.capacity,
                "current_tokens": round(self._tokens, 4),
            })
        return stats


class LeakyBucketLimiter(BaseRateLimiter):
    """
    漏桶限流器

    原理：请求进入桶中，以固定速率流出处理，桶满则拒绝新请求
    特点：平滑流量，不允许突发
    """

    def __init__(
        self,
        rate: float,
        capacity: int,
        name: str = "leaky_bucket",
    ):
        """
        Args:
            rate: 漏出速率（每秒处理请求数）
            capacity: 桶容量（最大排队请求数）
        """
        super().__init__(name)
        self.rate = rate
        self.capacity = capacity
        self._bucket: deque[float] = deque()
        self._last_leak = time.monotonic()

    def _leak(self):
        now = time.monotonic()
        elapsed = now - self._last_leak
        leaked = int(elapsed * self.rate)
        for _ in range(min(leaked, len(self._bucket))):
            self._bucket.popleft()
        if leaked > 0:
            self._last_leak = now

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            self._leak()
            if len(self._bucket) + tokens <= self.capacity:
                for _ in range(tokens):
                    self._bucket.append(time.monotonic())
                self._record_request(True)
                return True
            self._record_request(False)
            return False

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        if not blocking:
            return self.allow(tokens)

        start = time.monotonic()
        while True:
            with self._lock:
                self._leak()
                if len(self._bucket) + tokens <= self.capacity:
                    for _ in range(tokens):
                        self._bucket.append(time.monotonic())
                    self._record_request(True)
                    return True
                # 计算需要等待的时间
                if self.rate > 0 and len(self._bucket) > 0:
                    wait_time = 1.0 / self.rate
                else:
                    wait_time = 0.1

            if timeout is not None:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    self._record_request(False)
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            time.sleep(wait_time)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        with self._lock:
            self._leak()
            stats.update({
                "strategy": RateLimitStrategy.LEAKY_BUCKET.value,
                "rate": self.rate,
                "capacity": self.capacity,
                "current_queued": len(self._bucket),
            })
        return stats


class FixedWindowLimiter(BaseRateLimiter):
    """
    固定窗口限流器

    原理：在固定时间窗口内计数，超过阈值则拒绝
    特点：简单高效，但窗口边界可能有突发
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        name: str = "fixed_window",
    ):
        super().__init__(name)
        self.limit = limit
        self.window_seconds = window_seconds
        self._count = 0
        self._window_start = time.monotonic()

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._window_start = now
                self._count = 0

            if self._count + tokens <= self.limit:
                self._count += tokens
                self._record_request(True)
                return True
            self._record_request(False)
            return False

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        if not blocking:
            return self.allow(tokens)

        start = time.monotonic()
        while True:
            with self._lock:
                now = time.monotonic()
                if now - self._window_start >= self.window_seconds:
                    self._window_start = now
                    self._count = 0

                if self._count + tokens <= self.limit:
                    self._count += tokens
                    self._record_request(True)
                    return True

                wait_time = self.window_seconds - (now - self._window_start)

            if timeout is not None:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    self._record_request(False)
                    return False
                wait_time = min(wait_time, timeout - elapsed)
                if wait_time <= 0:
                    continue

            time.sleep(wait_time)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        with self._lock:
            stats.update({
                "strategy": RateLimitStrategy.FIXED_WINDOW.value,
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": self._count,
                "window_remaining": round(max(0, self.window_seconds - (time.monotonic() - self._window_start)), 2),
            })
        return stats


class SlidingWindowLimiter(BaseRateLimiter):
    """
    滑动窗口限流器

    原理：记录每个请求的时间戳，滑动统计窗口内的请求数
    特点：比固定窗口更平滑，精确控制
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        name: str = "sliding_window",
    ):
        super().__init__(name)
        self.limit = limit
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def _clean_old(self):
        now = time.monotonic()
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            self._clean_old()
            if len(self._timestamps) + tokens <= self.limit:
                for _ in range(tokens):
                    self._timestamps.append(time.monotonic())
                self._record_request(True)
                return True
            self._record_request(False)
            return False

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        if not blocking:
            return self.allow(tokens)

        start = time.monotonic()
        while True:
            with self._lock:
                self._clean_old()
                if len(self._timestamps) + tokens <= self.limit:
                    for _ in range(tokens):
                        self._timestamps.append(time.monotonic())
                    self._record_request(True)
                    return True

                if self._timestamps:
                    wait_time = self.window_seconds - (time.monotonic() - self._timestamps[0])
                    wait_time = max(wait_time, 0.01)
                else:
                    wait_time = 0.01

            if timeout is not None:
                elapsed = time.monotonic() - start
                if elapsed >= timeout:
                    self._record_request(False)
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            time.sleep(wait_time)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        with self._lock:
            self._clean_old()
            stats.update({
                "strategy": RateLimitStrategy.SLIDING_WINDOW.value,
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": len(self._timestamps),
            })
        return stats


class ConcurrencyLimiter(BaseRateLimiter):
    """
    并发限流器

    限制同时执行的并发数量，使用信号量机制
    """

    def __init__(
        self,
        max_concurrency: int,
        name: str = "concurrency",
    ):
        super().__init__(name)
        self.max_concurrency = max_concurrency
        self._semaphore = threading.Semaphore(max_concurrency)
        self._active_count = 0
        self._peak_count = 0

    def allow(self, tokens: int = 1) -> bool:
        # 对于并发限流，allow语义为是否能立即获取
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._lock:
                self._active_count += 1
                self._peak_count = max(self._peak_count, self._active_count)
                self._record_request(True)
        else:
            self._record_request(False)
        return acquired

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        acquired = self._semaphore.acquire(blocking=blocking, timeout=timeout or -1)
        if acquired:
            with self._lock:
                self._active_count += 1
                self._peak_count = max(self._peak_count, self._active_count)
                self._record_request(True)
        else:
            self._record_request(False)
        return acquired

    def release(self):
        """释放并发许可"""
        with self._lock:
            self._active_count = max(0, self._active_count - 1)
        self._semaphore.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        with self._lock:
            stats.update({
                "strategy": "concurrency",
                "max_concurrency": self.max_concurrency,
                "active_count": self._active_count,
                "peak_count": self._peak_count,
                "available": self.max_concurrency - self._active_count,
            })
        return stats


class RateLimiterFactory:
    """限流器工厂"""

    @staticmethod
    def create(
        strategy: RateLimitStrategy | str,
        **kwargs: Any,
    ) -> BaseRateLimiter:
        """
        创建限流器实例

        Args:
            strategy: 限流策略
            **kwargs: 策略参数
        """
        if isinstance(strategy, str):
            strategy = RateLimitStrategy(strategy)

        if strategy == RateLimitStrategy.TOKEN_BUCKET:
            return TokenBucketLimiter(
                rate=kwargs.get("rate", 10.0),
                capacity=kwargs.get("capacity", 100.0),
                name=kwargs.get("name", "token_bucket"),
            )
        elif strategy == RateLimitStrategy.LEAKY_BUCKET:
            return LeakyBucketLimiter(
                rate=kwargs.get("rate", 10.0),
                capacity=kwargs.get("capacity", 100),
                name=kwargs.get("name", "leaky_bucket"),
            )
        elif strategy == RateLimitStrategy.FIXED_WINDOW:
            return FixedWindowLimiter(
                limit=kwargs.get("limit", 100),
                window_seconds=kwargs.get("window_seconds", 60.0),
                name=kwargs.get("name", "fixed_window"),
            )
        elif strategy == RateLimitStrategy.SLIDING_WINDOW:
            return SlidingWindowLimiter(
                limit=kwargs.get("limit", 100),
                window_seconds=kwargs.get("window_seconds", 60.0),
                name=kwargs.get("name", "sliding_window"),
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")


def rate_limit(
    limiter: BaseRateLimiter,
    tokens: int = 1,
    raise_on_limit: bool = True,
) -> Callable:
    """
    限流装饰器

    Args:
        limiter: 限流器实例
        tokens: 每次调用消耗的令牌数
        raise_on_limit: 限流时是否抛出异常
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not limiter.allow(tokens):
                if raise_on_limit:
                    raise RateLimitExceeded(f"Function {func.__name__} rate limited")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


def demo_rate_limiter():
    """演示限流器功能"""
    print("=" * 60)
    print("限流器模块验证")
    print("=" * 60)
    print()

    # 1. 令牌桶
    print("1. 令牌桶限流器:")
    tb = TokenBucketLimiter(rate=10, capacity=5)
    for i in range(8):
        result = tb.allow()
        print(f"   请求{i+1}: {'通过' if result else '拒绝'}")
    print(f"   统计: {tb.get_stats()}")
    print()

    # 2. 漏桶
    print("2. 漏桶限流器:")
    lb = LeakyBucketLimiter(rate=5, capacity=3)
    for i in range(6):
        result = lb.allow()
        print(f"   请求{i+1}: {'通过' if result else '拒绝'}")
    print(f"   统计: {lb.get_stats()}")
    print()

    # 3. 固定窗口
    print("3. 固定窗口限流器:")
    fw = FixedWindowLimiter(limit=3, window_seconds=1.0)
    for i in range(5):
        result = fw.allow()
        print(f"   请求{i+1}: {'通过' if result else '拒绝'}")
    print(f"   统计: {fw.get_stats()}")
    print()

    # 4. 并发限流
    print("4. 并发限流器:")
    cl = ConcurrencyLimiter(max_concurrency=2)
    print(f"   初始状态: {cl.get_stats()}")
    cl.allow()
    cl.allow()
    print(f"   获取2个后: {cl.get_stats()}")
    result = cl.allow()
    print(f"   第3个请求: {'通过' if result else '拒绝'}")
    cl.release()
    print(f"   释放1个后: {cl.get_stats()}")
    print()

    # 5. 装饰器
    print("5. 限流装饰器:")
    limiter = TokenBucketLimiter(rate=2, capacity=2)

    @rate_limit(limiter, tokens=1)
    def hello():
        return "Hello"

    for i in range(4):
        try:
            result = hello()
            print(f"   调用{i+1}: {result}")
        except RateLimitExceeded as e:
            print(f"   调用{i+1}: 被限流 - {e}")
    print()

    print("=" * 60)
    print("限流器模块验证成功")
    print("=" * 60)


if __name__ == "__main__":
    demo_rate_limiter()
