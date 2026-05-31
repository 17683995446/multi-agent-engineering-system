"""
健康检查系统模块
遵循第一性原理：系统可观测性

核心功能：
1. 组件健康检查
2. 依赖健康检查
3. 健康报告
4. 自动恢复
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from common.utils import setup_logger

logger = setup_logger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class HealthCheck(ABC):
    """健康检查基类"""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    def check(self) -> HealthCheckResult:
        """执行健康检查"""
        pass

    def run(self) -> HealthCheckResult:
        """运行检查并记录耗时"""
        start = time.time()
        try:
            result = self.check()
            result.response_time_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"检查异常: {e}",
                response_time_ms=(time.time() - start) * 1000,
            )


class CallableHealthCheck(HealthCheck):
    """基于可调用对象的健康检查"""

    def __init__(self, name: str, check_func: Callable[[], HealthCheckResult], timeout: float = 5.0):
        super().__init__(name, timeout)
        self.check_func = check_func

    def check(self) -> HealthCheckResult:
        return self.check_func()


class DependencyHealthCheck(HealthCheck):
    """依赖健康检查（外部服务/数据库等）"""

    def __init__(self, name: str, check_func: Callable[[], bool], timeout: float = 5.0):
        super().__init__(name, timeout)
        self.check_func = check_func

    def check(self) -> HealthCheckResult:
        start = time.time()
        try:
            healthy = self.check_func()
            elapsed = (time.time() - start) * 1000
            if healthy:
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="依赖正常",
                    response_time_ms=elapsed,
                )
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message="依赖不可用",
                response_time_ms=elapsed,
            )
        except Exception as e:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"依赖检查异常: {e}",
                response_time_ms=(time.time() - start) * 1000,
            )


class AutoRecovery:
    """自动恢复机制"""

    def __init__(self, name: str, recovery_action: Callable[[], bool], max_attempts: int = 3):
        self.name = name
        self.recovery_action = recovery_action
        self.max_attempts = max_attempts
        self.attempt_count = 0
        self.last_result = False

    def attempt(self) -> bool:
        """尝试恢复"""
        if self.attempt_count >= self.max_attempts:
            logger.warning(f"自动恢复已达最大尝试次数: {self.name}")
            return False
        self.attempt_count += 1
        try:
            self.last_result = self.recovery_action()
            if self.last_result:
                logger.info(f"自动恢复成功: {self.name}")
                self.attempt_count = 0
            else:
                logger.warning(f"自动恢复失败: {self.name} (尝试 {self.attempt_count}/{self.max_attempts})")
            return self.last_result
        except Exception as e:
            logger.error(f"自动恢复异常: {self.name} - {e}")
            self.last_result = False
            return False

    def reset(self) -> None:
        """重置尝试计数"""
        self.attempt_count = 0


class HealthCheckSystem:
    """
    健康检查系统

    核心功能：
    - 注册组件健康检查
    - 注册依赖健康检查
    - 执行批量健康检查
    - 生成健康报告
    - 自动恢复机制
    """

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
        self._checks: Dict[str, HealthCheck] = {}
        self._recoveries: Dict[str, AutoRecovery] = {}
        self._history: List[HealthCheckResult] = []
        self._lock = threading.RLock()
        self._initialized = True
        logger.info("健康检查系统初始化完成")

    def register(self, check: HealthCheck) -> None:
        """注册健康检查"""
        with self._lock:
            self._checks[check.name] = check
        logger.info(f"注册健康检查: {check.name}")

    def register_dependency(self, name: str, check_func: Callable[[], bool], timeout: float = 5.0) -> None:
        """注册依赖健康检查"""
        self.register(DependencyHealthCheck(name, check_func, timeout))

    def register_recovery(self, name: str, recovery_action: Callable[[], bool], max_attempts: int = 3) -> None:
        """注册自动恢复动作"""
        with self._lock:
            self._recoveries[name] = AutoRecovery(name, recovery_action, max_attempts)
        logger.info(f"注册自动恢复: {name}")

    def check(self, name: str) -> HealthCheckResult:
        """执行单个健康检查"""
        with self._lock:
            check = self._checks.get(name)
        if not check:
            return HealthCheckResult(
                component=name,
                status=HealthStatus.UNKNOWN,
                message="未找到该组件的健康检查",
                response_time_ms=0.0,
            )
        result = check.run()
        with self._lock:
            self._history.append(result)

        # 自动恢复
        if result.status != HealthStatus.HEALTHY:
            recovery = self._recoveries.get(name)
            if recovery:
                recovered = recovery.attempt()
                if recovered:
                    result.status = HealthStatus.DEGRADED
                    result.message += " (已自动恢复)"
                    result.metadata["recovered"] = True

        return result

    def check_all(self) -> Dict[str, HealthCheckResult]:
        """执行所有健康检查"""
        with self._lock:
            names = list(self._checks.keys())
        results = {}
        for name in names:
            results[name] = self.check(name)
        return results

    def get_report(self) -> Dict[str, Any]:
        """生成健康报告"""
        results = self.check_all()
        status_counts = {s.value: 0 for s in HealthStatus}
        for r in results.values():
            status_counts[r.status.value] += 1

        overall = HealthStatus.HEALTHY
        if status_counts[HealthStatus.UNHEALTHY.value] > 0:
            overall = HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.DEGRADED.value] > 0:
            overall = HealthStatus.DEGRADED

        return {
            "overall_status": overall.value,
            "timestamp": datetime.now().isoformat(),
            "component_count": len(results),
            "status_counts": status_counts,
            "components": {name: r.to_dict() for name, r in results.items()},
        }

    def get_history(self, component: Optional[str] = None, limit: Optional[int] = None) -> List[HealthCheckResult]:
        """获取检查历史"""
        with self._lock:
            history = self._history
            if component:
                history = [h for h in history if h.component == component]
            if limit:
                history = history[-limit:]
            return history

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self._lock:
            return {
                "checks_count": len(self._checks),
                "recoveries_count": len(self._recoveries),
                "history_count": len(self._history),
                "check_names": list(self._checks.keys()),
            }


def demo_health_check():
    """演示健康检查系统"""
    print("=" * 60)
    print("健康检查系统演示")
    print("=" * 60)
    print()

    HealthCheckSystem._instance = None
    system = HealthCheckSystem()

    print("1. 注册组件健康检查:")
    def check_database():
        return HealthCheckResult("database", HealthStatus.HEALTHY, "数据库连接正常", 12.5)

    def check_cache():
        return HealthCheckResult("cache", HealthStatus.DEGRADED, "缓存响应慢", 250.0)

    system.register(CallableHealthCheck("database", check_database))
    system.register(CallableHealthCheck("cache", check_cache))
    system.register_dependency("api_gateway", lambda: True)
    print("   ✓ 数据库、缓存、API网关检查已注册")
    print()

    print("2. 执行健康检查:")
    db_result = system.check("database")
    print(f"   ✓ {db_result.component}: {db_result.status.value} ({db_result.message})")
    cache_result = system.check("cache")
    print(f"   ✓ {cache_result.component}: {cache_result.status.value} ({cache_result.message})")
    print()

    print("3. 自动恢复机制:")
    recover_count = 0
    def recover_cache():
        nonlocal recover_count
        recover_count += 1
        return recover_count >= 2

    system.register_recovery("cache", recover_cache, max_attempts=3)
    # 第一次检查触发恢复（失败）
    r1 = system.check("cache")
    print(f"   ✓ 第一次恢复尝试: {r1.message}")
    # 第二次检查触发恢复（成功）
    r2 = system.check("cache")
    print(f"   ✓ 第二次恢复尝试: {r2.message}")
    print()

    print("4. 健康报告:")
    report = system.get_report()
    print(f"   ✓ 整体状态: {report['overall_status']}")
    print(f"   ✓ 组件数: {report['component_count']}")
    print(f"   ✓ 状态分布: {report['status_counts']}")
    print()

    print("5. 检查历史:")
    history = system.get_history(limit=5)
    print(f"   ✓ 最近 {len(history)} 条检查记录")
    print()

    print("=" * 60)
    print("健康检查系统演示完成")
    print("=" * 60)
    print()
    print("✓ 组件健康检查")
    print("✓ 依赖健康检查")
    print("✓ 健康报告生成")
    print("✓ 自动恢复机制")
    print()


if __name__ == "__main__":
    demo_health_check()
