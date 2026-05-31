"""
异常处理增强模块
遵循第一性原理：故障隔离与自动恢复

核心功能：
1. 全局异常捕获
2. 异常分类
3. 自动恢复
4. 降级策略
"""

from __future__ import annotations

import functools
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class ExceptionCategory(Enum):
    """异常分类"""
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """恢复策略"""
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAK = "circuit_break"
    IGNORE = "ignore"
    RAISE = "raise"


@dataclass
class ExceptionRecord:
    """异常记录"""
    exception_type: str
    message: str
    category: ExceptionCategory
    stack_trace: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovery_strategy: Optional[RecoveryStrategy] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exception_type": self.exception_type,
            "message": self.message,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "recovered": self.recovered,
            "recovery_strategy": self.recovery_strategy.value if self.recovery_strategy else None,
        }


class ExceptionClassifier:
    """异常分类器"""

    TRANSIENT_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    VALIDATION_EXCEPTIONS = (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
    )
    RESOURCE_EXCEPTIONS = (
        MemoryError,
        RecursionError,
    )

    @classmethod
    def classify(cls, exception: Exception) -> ExceptionCategory:
        """对异常进行分类"""
        if isinstance(exception, cls.TRANSIENT_EXCEPTIONS):
            return ExceptionCategory.TRANSIENT
        if isinstance(exception, cls.VALIDATION_EXCEPTIONS):
            return ExceptionCategory.VALIDATION
        if isinstance(exception, cls.RESOURCE_EXCEPTIONS):
            return ExceptionCategory.RESOURCE
        if isinstance(exception, TimeoutError):
            return ExceptionCategory.TIMEOUT
        return ExceptionCategory.UNKNOWN


class RecoveryAction(ABC):
    """恢复动作基类"""

    @abstractmethod
    def execute(self, exception: Exception, context: Dict[str, Any]) -> Any:
        """执行恢复动作"""
        pass


class RetryRecovery(RecoveryAction):
    """重试恢复"""

    def __init__(self, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff

    def execute(self, exception: Exception, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("RetryRecovery should be used via decorator")


class FallbackRecovery(RecoveryAction):
    """降级恢复"""

    def __init__(self, fallback_value: Any = None, fallback_func: Optional[Callable[..., Any]] = None):
        self.fallback_value = fallback_value
        self.fallback_func = fallback_func

    def execute(self, exception: Exception, context: Dict[str, Any]) -> Any:
        if self.fallback_func:
            return self.fallback_func(**context)
        return self.fallback_value


class ExceptionHandler:
    """
    异常处理增强器

    核心功能：
    - 全局异常捕获与分类
    - 自动恢复策略
    - 降级处理
    - 异常历史记录
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._records: List[ExceptionRecord] = []
        self._handlers: Dict[ExceptionCategory, List[Callable[[Exception], Any]]] = {
            cat: [] for cat in ExceptionCategory
        }
        self._fallbacks: Dict[str, Any] = {}
        self._initialized = True
        logger.info("异常处理增强器初始化完成")

    def classify(self, exception: Exception) -> ExceptionCategory:
        """分类异常"""
        return ExceptionClassifier.classify(exception)

    def record(self, exception: Exception, context: Optional[Dict[str, Any]] = None, recovered: bool = False,
               strategy: Optional[RecoveryStrategy] = None) -> ExceptionRecord:
        """记录异常"""
        record = ExceptionRecord(
            exception_type=type(exception).__name__,
            message=str(exception),
            category=self.classify(exception),
            stack_trace=traceback.format_exc(),
            context=context or {},
            recovered=recovered,
            recovery_strategy=strategy,
        )
        self._records.append(record)
        logger.warning(f"异常记录: {record.exception_type} - {record.message} (分类: {record.category.value})")
        return record

    def get_records(self, category: Optional[ExceptionCategory] = None, limit: Optional[int] = None) -> List[ExceptionRecord]:
        """获取异常记录"""
        records = self._records
        if category:
            records = [r for r in records if r.category == category]
        if limit:
            records = records[-limit:]
        return records

    def get_statistics(self) -> Dict[str, Any]:
        """获取异常统计"""
        stats = {cat.value: 0 for cat in ExceptionCategory}
        for record in self._records:
            stats[record.category.value] += 1
        return {
            "total": len(self._records),
            "by_category": stats,
            "recovered": sum(1 for r in self._records if r.recovered),
        }

    def register_handler(self, category: ExceptionCategory, handler: Callable[[Exception], Any]) -> None:
        """注册分类处理器"""
        self._handlers[category].append(handler)

    def handle(self, exception: Exception, context: Optional[Dict[str, Any]] = None) -> Any:
        """处理异常"""
        category = self.classify(exception)
        for handler in self._handlers.get(category, []):
            try:
                result = handler(exception)
                self.record(exception, context, recovered=True, strategy=RecoveryStrategy.FALLBACK)
                return result
            except Exception as e:
                logger.error(f"异常处理器失败: {e}")
        self.record(exception, context)
        raise

    def clear_records(self) -> None:
        """清空异常记录"""
        self._records.clear()


def safe_execute(
    fallback: Any = None,
    fallback_func: Optional[Callable[..., Any]] = None,
    default_on_error: Any = None,
    log_exception: bool = True,
):
    """安全执行装饰器"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_exception:
                    handler = ExceptionHandler()
                    handler.record(e, {"func": func.__name__, "args": str(args), "kwargs": str(kwargs)})
                if fallback_func:
                    return fallback_func(*args, **kwargs)
                if fallback is not None:
                    return fallback
                if default_on_error is not None:
                    return default_on_error
                raise
        return wrapper
    return decorator


def retry(
    max_retries: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """重试装饰器"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time
            current_delay = delay
            last_exception: Optional[Exception] = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        if on_retry:
                            on_retry(e, attempt + 1)
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        break
            raise last_exception  # type: ignore[misc]
        return wrapper
    return decorator


def with_fallback(fallback_func: Callable[..., Any]):
    """降级装饰器"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception:
                return fallback_func(*args, **kwargs)
        return wrapper
    return decorator


def global_exception_hook(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
    """全局未捕获异常钩子"""
    handler = ExceptionHandler()
    record = handler.record(
        exc_value,  # type: ignore[arg-type]
        context={"uncaught": True},
    )
    logger.critical(f"未捕获异常: {record.exception_type} - {record.message}")
    traceback.print_exception(exc_type, exc_value, exc_traceback)


def install_global_handler() -> None:
    """安装全局异常处理器"""
    import sys
    sys.excepthook = global_exception_hook
    logger.info("全局异常处理器已安装")


def demo_exception_handler():
    """演示异常处理增强"""
    print("=" * 60)
    print("异常处理增强演示")
    print("=" * 60)
    print()

    handler = ExceptionHandler()
    handler.clear_records()

    print("1. 异常分类:")
    try:
        raise ConnectionError("网络连接失败")
    except Exception as e:
        cat = handler.classify(e)
        print(f"   ✓ ConnectionError 分类为: {cat.value}")

    try:
        raise ValueError("参数错误")
    except Exception as e:
        cat = handler.classify(e)
        print(f"   ✓ ValueError 分类为: {cat.value}")
    print()

    print("2. 安全执行装饰器:")
    @safe_execute(fallback="default_value")
    def risky_func():
        raise RuntimeError("出错了")

    result = risky_func()
    print(f"   ✓ 异常被捕获，返回降级值: {result}")
    print()

    print("3. 重试装饰器:")
    attempt_count = 0

    @retry(max_retries=2, delay=0.1, exceptions=(RuntimeError,))
    def flaky_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise RuntimeError("暂时失败")
        return "success"

    result = flaky_func()
    print(f"   ✓ 重试后成功: {result} (尝试 {attempt_count} 次)")
    print()

    print("4. 降级装饰器:")
    def fallback_impl():
        return "fallback_result"

    @with_fallback(fallback_impl)
    def primary_func():
        raise Exception("主逻辑失败")

    result = primary_func()
    print(f"   ✓ 降级执行结果: {result}")
    print()

    print("5. 异常统计:")
    stats = handler.get_statistics()
    print(f"   ✓ 异常统计: {stats}")
    print()

    print("=" * 60)
    print("异常处理增强演示完成")
    print("=" * 60)
    print()
    print("✓ 异常自动分类")
    print("✓ 安全执行与降级")
    print("✓ 自动重试机制")
    print("✓ 全局异常捕获")
    print()


if __name__ == "__main__":
    demo_exception_handler()
