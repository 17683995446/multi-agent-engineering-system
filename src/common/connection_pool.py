"""
公共层 - 连接池管理模块
职责：提供通用连接池、最大连接数、连接超时、连接复用
依赖规则：仅依赖公共层 utils
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

from common.utils import setup_logger

C = TypeVar("C")


class PoolExhausted(Exception):
    """连接池耗尽异常"""
    pass


class ConnectionTimeout(Exception):
    """连接超时异常"""
    pass


@dataclass
class PoolConfig:
    """连接池配置"""
    max_size: int = 10
    min_size: int = 1
    max_idle_time: float = 300.0
    connection_timeout: float = 30.0
    acquire_timeout: float = 10.0
    validate_on_borrow: bool = True
    validate_on_return: bool = False


class PooledConnection(Generic[C]):
    """池化连接包装器"""

    def __init__(self, connection: C, pool: ConnectionPool):
        self.connection = connection
        self.pool = pool
        self.created_at = time.monotonic()
        self.last_used = time.monotonic()
        self.use_count = 0
        self._in_use = True

    def mark_used(self):
        self.last_used = time.monotonic()
        self.use_count += 1

    def is_expired(self, max_idle_time: float) -> bool:
        return time.monotonic() - self.last_used > max_idle_time

    def is_valid(self) -> bool:
        return self.pool.validate_connection(self.connection)


class ConnectionPool(ABC, Generic[C]):
    """
    通用连接池抽象基类

    提供连接的生命周期管理：
    - 创建
    - 借用
    - 归还
    - 销毁
    - 验证
    """

    def __init__(self, config: Optional[PoolConfig] = None, name: str = "connection_pool"):
        self.config = config or PoolConfig()
        self.name = name
        self.logger = setup_logger(f"common.connection_pool.{name}")
        self._pool: deque[PooledConnection[C]] = deque()
        self._in_use: set[PooledConnection[C]] = set()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._total_created = 0
        self._total_destroyed = 0
        self._total_borrowed = 0
        self._total_returned = 0
        self._shutdown = False

        # 初始化最小连接数
        for _ in range(self.config.min_size):
            conn = self._create_connection()
            if conn:
                self._pool.append(conn)

    @abstractmethod
    def create_connection(self) -> C:
        """创建新连接，子类实现"""

    @abstractmethod
    def destroy_connection(self, connection: C) -> None:
        """销毁连接，子类实现"""

    @abstractmethod
    def validate_connection(self, connection: C) -> bool:
        """验证连接是否有效，子类实现"""

    def _create_connection(self) -> Optional[PooledConnection[C]]:
        """内部创建连接"""
        try:
            raw = self.create_connection()
            self._total_created += 1
            return PooledConnection(raw, self)
        except Exception as e:
            self.logger.error(f"创建连接失败: {e}")
            return None

    def _destroy_pooled(self, pooled: PooledConnection[C]) -> None:
        """内部销毁连接"""
        try:
            self.destroy_connection(pooled.connection)
        except Exception as e:
            self.logger.error(f"销毁连接失败: {e}")
        self._total_destroyed += 1

    def acquire(self, timeout: Optional[float] = None) -> C:
        """
        从池中获取连接

        Args:
            timeout: 等待超时时间（秒），None表示使用配置默认值
        """
        if self._shutdown:
            raise PoolExhausted("连接池已关闭")

        timeout = timeout if timeout is not None else self.config.acquire_timeout
        deadline = time.monotonic() + timeout

        with self._condition:
            while True:
                # 尝试从池中获取可用连接
                while self._pool:
                    pooled = self._pool.popleft()

                    # 检查是否过期
                    if pooled.is_expired(self.config.max_idle_time):
                        self._destroy_pooled(pooled)
                        continue

                    # 验证连接有效性
                    if self.config.validate_on_borrow and not pooled.is_valid():
                        self._destroy_pooled(pooled)
                        continue

                    pooled.mark_used()
                    pooled._in_use = True
                    self._in_use.add(pooled)
                    self._total_borrowed += 1
                    return pooled.connection

                # 池为空，检查是否可创建新连接
                current_size = len(self._pool) + len(self._in_use)
                if current_size < self.config.max_size:
                    pooled = self._create_connection()
                    if pooled:
                        pooled.mark_used()
                        pooled._in_use = True
                        self._in_use.add(pooled)
                        self._total_borrowed += 1
                        return pooled.connection

                # 等待连接归还
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ConnectionTimeout(f"获取连接超时（{timeout}s）")

                self._condition.wait(timeout=remaining)

    def release(self, connection: C) -> None:
        """归还连接到池"""
        with self._condition:
            # 查找对应的PooledConnection
            pooled = None
            for p in self._in_use:
                if p.connection is connection:
                    pooled = p
                    break

            if pooled is None:
                self.logger.warning("归还的连接不属于当前池")
                return

            self._in_use.remove(pooled)
            self._total_returned += 1

            if self._shutdown:
                self._destroy_pooled(pooled)
                return

            if self.config.validate_on_return and not pooled.is_valid():
                self._destroy_pooled(pooled)
                self._condition.notify()
                return

            pooled._in_use = False
            pooled.last_used = time.monotonic()
            self._pool.append(pooled)
            self._condition.notify()

    def __enter__(self) -> C:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # 注意：这里需要知道获取的连接，因此上下文管理器用法稍有不同
        pass

    def get_stats(self) -> dict[str, Any]:
        """获取连接池统计"""
        with self._lock:
            return {
                "pool_size": len(self._pool),
                "in_use": len(self._in_use),
                "total_created": self._total_created,
                "total_destroyed": self._total_destroyed,
                "total_borrowed": self._total_borrowed,
                "total_returned": self._total_returned,
                "max_size": self.config.max_size,
            }

    def _clear_unlocked(self) -> None:
        """清空连接池（无锁版本，调用者需持有锁）"""
        while self._pool:
            pooled = self._pool.popleft()
            self._destroy_pooled(pooled)

    def clear(self) -> None:
        """清空连接池"""
        with self._condition:
            self._clear_unlocked()

    def shutdown(self) -> None:
        """关闭连接池"""
        with self._condition:
            self._shutdown = True
            self._clear_unlocked()
            for pooled in list(self._in_use):
                self._destroy_pooled(pooled)
            self._in_use.clear()
            self._condition.notify_all()

    def resize(self, max_size: int) -> None:
        """调整连接池大小"""
        with self._condition:
            self.config.max_size = max_size
            while len(self._pool) + len(self._in_use) > max_size and self._pool:
                pooled = self._pool.popleft()
                self._destroy_pooled(pooled)


class MockConnection:
    """模拟连接，用于测试和演示"""

    _counter = 0
    _lock = threading.Lock()

    def __init__(self):
        with MockConnection._lock:
            MockConnection._counter += 1
            self.id = MockConnection._counter
        self.active = True

    def close(self):
        self.active = False

    def is_valid(self) -> bool:
        return self.active

    def __repr__(self):
        return f"MockConnection({self.id}, active={self.active})"


class MockConnectionPool(ConnectionPool[MockConnection]):
    """模拟连接池实现"""

    def create_connection(self) -> MockConnection:
        return MockConnection()

    def destroy_connection(self, connection: MockConnection) -> None:
        connection.close()

    def validate_connection(self, connection: MockConnection) -> bool:
        return connection.is_valid()


def pooled(pool: ConnectionPool):
    """
    连接池装饰器

    自动获取和释放连接
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            conn = pool.acquire()
            try:
                return func(conn, *args, **kwargs)
            finally:
                pool.release(conn)
        return wrapper
    return decorator


def demo_connection_pool():
    """演示连接池"""
    print("=" * 60)
    print("连接池管理模块验证")
    print("=" * 60)
    print()

    pool = MockConnectionPool(
        config=PoolConfig(max_size=3, min_size=1),
        name="demo_pool"
    )

    print("1. 初始状态:")
    print(f"   {pool.get_stats()}")
    print()

    print("2. 获取连接:")
    conn1 = pool.acquire()
    conn2 = pool.acquire()
    print(f"   连接1: {conn1}")
    print(f"   连接2: {conn2}")
    print(f"   统计: {pool.get_stats()}")
    print()

    print("3. 归还连接:")
    pool.release(conn1)
    print(f"   统计: {pool.get_stats()}")
    print()

    print("4. 使用装饰器:")

    @pooled(pool)
    def do_work(conn):
        return f"使用{conn}工作"

    result = do_work()
    print(f"   结果: {result}")
    print()

    print("5. 关闭连接池:")
    pool.shutdown()
    print(f"   统计: {pool.get_stats()}")
    print()

    print("=" * 60)
    print("连接池管理模块验证成功")
    print("=" * 60)


if __name__ == "__main__":
    demo_connection_pool()
