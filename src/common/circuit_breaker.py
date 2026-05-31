"""
熔断器模式模块
遵循第一性原理：故障隔离与自动恢复

核心功能：
1. 熔断器状态管理（CLOSED / OPEN / HALF_OPEN）
2. 失败计数与阈值触发
3. 自动恢复（HALF_OPEN 探测）
4. 装饰器支持
"""

from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from common.utils import setup_logger

logger = setup_logger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    def __init__(self, message: str = "Circuit breaker is OPEN"):
        self.message = message
        super().__init__(self.message)


@dataclass
class CircuitBreakerMetrics:
    """熔断器指标"""
    total_calls: int = 0
    success_calls: int = 0
    failure_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: List[Dict[str, Any]] = field(default_factory=list)

    def record_success(self) -> None:
        self.total_calls += 1
        self.success_calls += 1
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        self.total_calls += 1
        self.failure_calls += 1
        self.last_failure_time = time.time()

    def record_rejected(self) -> None:
        self.total_calls += 1
        self.rejected_calls += 1

    def reset(self) -> None:
        self.total_calls = 0
        self.success_calls = 0
        self.failure_calls = 0
        self.rejected_calls = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "success_calls": self.success_calls,
            "failure_calls": self.failure_calls,
            "rejected_calls": self.rejected_calls,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "state_changes": self.state_changes,
        }


class CircuitBreaker:
    """
    熔断器

    状态流转：
    CLOSED -> OPEN: 失败次数达到阈值
    OPEN -> HALF_OPEN: 超时时间到达
    HALF_OPEN -> CLOSED: 探测成功次数达到阈值
    HALF_OPEN -> OPEN: 探测失败
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        expected_exception: Type[Exception] = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()

        logger.info(f"熔断器初始化: {name} (threshold={failure_threshold}, timeout={recovery_timeout})")

    @property
    def state(self) -> CircuitState:
        return self._state

    def _change_state(self, new_state: CircuitState) -> None:
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._metrics.state_changes.append({
                "from": old_state.value,
                "to": new_state.value,
                "timestamp": datetime.now().isoformat(),
            })
            logger.warning(f"熔断器状态变更: {self.name} {old_state.value} -> {new_state.value}")

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """通过熔断器调用函数"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._change_state(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info(f"熔断器进入半开状态: {self.name}")
                else:
                    self._metrics.record_rejected()
                    raise CircuitBreakerOpen(f"熔断器 {self.name} 处于 OPEN 状态，请求被拒绝")

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._metrics.record_rejected()
                    raise CircuitBreakerOpen(f"熔断器 {self.name} HALF_OPEN 探测次数已满")
                self._half_open_calls += 1

        # 执行业务逻辑
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            self._metrics.record_success()
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._change_state(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._metrics.reset()
                    logger.info(f"熔断器关闭: {self.name}")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._metrics.record_failure()
            if self._state == CircuitState.HALF_OPEN:
                self._change_state(CircuitState.OPEN)
                self._last_failure_time = time.time()
                logger.warning(f"半开状态探测失败，熔断器打开: {self.name}")
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._change_state(CircuitState.OPEN)
                    self._last_failure_time = time.time()
                    logger.warning(f"失败次数达到阈值，熔断器打开: {self.name}")

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def get_metrics(self) -> Dict[str, Any]:
        """获取熔断器指标"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_calls": self._half_open_calls,
                "last_failure_time": self._last_failure_time,
                "metrics": self._metrics.to_dict(),
            }

    def reset(self) -> None:
        """手动重置熔断器"""
        with self._lock:
            self._change_state(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            self._metrics.reset()
        logger.info(f"熔断器手动重置: {self.name}")


class CircuitBreakerRegistry:
    """熔断器注册表"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._initialized = True

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        expected_exception: Type[Exception] = Exception,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=half_open_max_calls,
                expected_exception=expected_exception,
            )
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def remove(self, name: str) -> None:
        if name in self._breakers:
            del self._breakers[name]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        return {name: cb.get_metrics() for name, cb in self._breakers.items()}


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    half_open_max_calls: int = 3,
    expected_exception: Type[Exception] = Exception,
):
    """熔断器装饰器"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        breaker_name = name or func.__name__
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create(
            breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            expected_exception=expected_exception,
        )

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def demo_circuit_breaker():
    """演示熔断器模式"""
    print("=" * 60)
    print("熔断器模式演示")
    print("=" * 60)
    print()

    print("1. 熔断器基本状态流转:")
    cb = CircuitBreaker("demo", failure_threshold=3, recovery_timeout=1.0, half_open_max_calls=2)

    fail_count = 0
    def unstable_func():
        nonlocal fail_count
        fail_count += 1
        if fail_count <= 4:
            raise RuntimeError("服务异常")
        return "success"

    # 触发熔断
    for i in range(3):
        try:
            cb.call(unstable_func)
        except (RuntimeError, CircuitBreakerOpen):
            pass
    print(f"   ✓ 失败3次后状态: {cb.state.value}")

    # 等待恢复超时
    time.sleep(1.1)
    try:
        cb.call(unstable_func)
    except (RuntimeError, CircuitBreakerOpen):
        pass
    print(f"   ✓ 超时后探测失败，状态: {cb.state.value}")

    # 再次等待后成功恢复
    time.sleep(1.1)
    fail_count = 10  # 让后续调用成功
    cb.call(unstable_func)
    cb.call(unstable_func)
    print(f"   ✓ 探测成功后状态: {cb.state.value}")
    print()

    print("2. 熔断器装饰器:")
    @circuit_breaker(name="decorated_svc", failure_threshold=2, recovery_timeout=0.5)
    def decorated_func(should_fail: bool = False):
        if should_fail:
            raise RuntimeError("fail")
        return "ok"

    try:
        decorated_func(should_fail=True)
    except Exception:
        pass
    try:
        decorated_func(should_fail=True)
    except Exception:
        pass
    try:
        decorated_func()
    except CircuitBreakerOpen:
        print("   ✓ 熔断器装饰器生效，请求被拒绝")
    print()

    print("3. 熔断器指标:")
    metrics = cb.get_metrics()
    print(f"   ✓ 指标: {metrics['metrics']}")
    print()

    print("=" * 60)
    print("熔断器模式演示完成")
    print("=" * 60)
    print()
    print("✓ 熔断器状态管理（CLOSED/OPEN/HALF_OPEN）")
    print("✓ 失败计数与阈值触发")
    print("✓ 自动恢复探测")
    print("✓ 装饰器支持")
    print()


if __name__ == "__main__":
    demo_circuit_breaker()
