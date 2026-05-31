"""
公共层 - 缓存系统模块
职责：提供LRU缓存、TTL缓存、内存缓存、缓存淘汰策略
依赖规则：仅依赖公共层 utils
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

from common.utils import setup_logger

K = TypeVar("K")
V = TypeVar("V")


class CacheException(Exception):
    """缓存异常"""
    pass


@dataclass
class CacheEntry(Generic[V]):
    """缓存条目"""
    value: V
    created_at: float = field(default_factory=time.monotonic)
    expires_at: Optional[float] = None
    access_count: int = 0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() >= self.expires_at


class BaseCache(ABC, Generic[K, V]):
    """缓存抽象基类"""

    def __init__(self, name: str = "cache"):
        self.name = name
        self.logger = setup_logger(f"common.cache_system.{name}")
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @abstractmethod
    def get(self, key: K) -> Optional[V]:
        """获取缓存值"""

    @abstractmethod
    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        """设置缓存值"""

    @abstractmethod
    def delete(self, key: K) -> bool:
        """删除缓存项"""

    @abstractmethod
    def clear(self) -> None:
        """清空缓存"""

    @abstractmethod
    def keys(self) -> list[K]:
        """获取所有键"""

    @abstractmethod
    def size(self) -> int:
        """获取缓存大小"""

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / max(total, 1) * 100, 2),
                "size": len(self._cache) if hasattr(self, '_cache') else 0,
            }

    def reset_stats(self) -> None:
        """重置统计"""
        with self._lock:
            self._hits = 0
            self._misses = 0

    def _record_hit(self):
        self._hits += 1

    def _record_miss(self):
        self._misses += 1


class LRUCache(BaseCache[K, V]):
    """
    LRU（最近最少使用）缓存

    基于OrderedDict实现，容量满时淘汰最久未访问的项
    """

    def __init__(self, capacity: int, name: str = "lru_cache"):
        super().__init__(name)
        self.capacity = capacity
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()

    def get(self, key: K) -> Optional[V]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._record_miss()
                return None
            if entry.is_expired():
                del self._cache[key]
                self._record_miss()
                return None
            entry.access_count += 1
            self._cache.move_to_end(key)
            self._record_hit()
            return entry.value

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        with self._lock:
            expires_at = time.monotonic() + ttl if ttl is not None else None
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = CacheEntry(value, expires_at=expires_at)
            else:
                self._cache[key] = CacheEntry(value, expires_at=expires_at)
                if len(self._cache) > self.capacity:
                    self._cache.popitem(last=False)

    def delete(self, key: K) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def keys(self) -> list[K]:
        with self._lock:
            return list(self._cache.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_ordered_keys(self) -> list[K]:
        """按访问顺序返回键（从旧到新）"""
        with self._lock:
            return list(self._cache.keys())


class TTLCache(BaseCache[K, V]):
    """
    TTL（生存时间）缓存

    每个条目有过期时间，过期后自动失效
    支持后台清理（惰性清理）
    """

    def __init__(self, default_ttl: float, max_size: int = 1000, name: str = "ttl_cache"):
        super().__init__(name)
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: dict[K, CacheEntry[V]] = {}

    def _cleanup_expired(self):
        """清理过期条目"""
        now = time.monotonic()
        expired = [k for k, v in self._cache.items() if v.expires_at is not None and v.expires_at <= now]
        for k in expired:
            del self._cache[k]
        return len(expired)

    def get(self, key: K) -> Optional[V]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._record_miss()
                return None
            if entry.is_expired():
                del self._cache[key]
                self._record_miss()
                return None
            entry.access_count += 1
            self._record_hit()
            return entry.value

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        with self._lock:
            effective_ttl = ttl if ttl is not None else self.default_ttl
            expires_at = time.monotonic() + effective_ttl
            self._cache[key] = CacheEntry(value, expires_at=expires_at)
            if len(self._cache) > self.max_size:
                self._cleanup_expired()
            if len(self._cache) > self.max_size:
                # 如果清理后仍超出，删除最老的
                oldest = min(self._cache.items(), key=lambda x: x[1].created_at)
                del self._cache[oldest[0]]

    def delete(self, key: K) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def keys(self) -> list[K]:
        with self._lock:
            self._cleanup_expired()
            return list(self._cache.keys())

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def ttl(self, key: K) -> Optional[float]:
        """获取剩余生存时间（秒）"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.expires_at is None:
                return None
            remaining = entry.expires_at - time.monotonic()
            return max(0.0, remaining)


class MemoryCache(BaseCache[K, V]):
    """
    通用内存缓存

    结合LRU和TTL特性，支持最大容量和默认TTL
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        name: str = "memory_cache",
    ):
        super().__init__(name)
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()

    def get(self, key: K) -> Optional[V]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._record_miss()
                return None
            if entry.is_expired():
                del self._cache[key]
                self._record_miss()
                return None
            entry.access_count += 1
            self._cache.move_to_end(key)
            self._record_hit()
            return entry.value

    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        with self._lock:
            effective_ttl = ttl if ttl is not None else self.default_ttl
            expires_at = time.monotonic() + effective_ttl if effective_ttl is not None else None
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = CacheEntry(value, expires_at=expires_at)
            else:
                self._cache[key] = CacheEntry(value, expires_at=expires_at)
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)

    def delete(self, key: K) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def keys(self) -> list[K]:
        with self._lock:
            return [k for k, v in self._cache.items() if not v.is_expired()]

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_or_set(self, key: K, default: Callable[[], V], ttl: Optional[float] = None) -> V:
        """获取或设置缓存值"""
        value = self.get(key)
        if value is not None:
            return value
        value = default()
        self.set(key, value, ttl)
        return value


class CacheManager:
    """
    缓存管理器

    统一管理多个命名缓存实例
    """

    def __init__(self):
        self.logger = setup_logger("common.cache_system.manager")
        self._caches: dict[str, BaseCache] = {}
        self._lock = threading.Lock()

    def create_lru(self, name: str, capacity: int) -> LRUCache:
        """创建LRU缓存"""
        with self._lock:
            cache = LRUCache(capacity, name=name)
            self._caches[name] = cache
            return cache

    def create_ttl(self, name: str, default_ttl: float, max_size: int = 1000) -> TTLCache:
        """创建TTL缓存"""
        with self._lock:
            cache = TTLCache(default_ttl, max_size=max_size, name=name)
            self._caches[name] = cache
            return cache

    def create_memory(self, name: str, max_size: int = 1000, default_ttl: Optional[float] = None) -> MemoryCache:
        """创建内存缓存"""
        with self._lock:
            cache = MemoryCache(max_size=max_size, default_ttl=default_ttl, name=name)
            self._caches[name] = cache
            return cache

    def get(self, name: str) -> Optional[BaseCache]:
        """获取缓存实例"""
        with self._lock:
            return self._caches.get(name)

    def remove(self, name: str) -> bool:
        """移除缓存实例"""
        with self._lock:
            if name in self._caches:
                del self._caches[name]
                return True
            return False

    def clear_all(self) -> None:
        """清空所有缓存"""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有缓存统计"""
        with self._lock:
            return {name: cache.get_stats() for name, cache in self._caches.items()}


def cached(
    cache: BaseCache,
    key_func: Optional[Callable] = None,
    ttl: Optional[float] = None,
):
    """
    缓存装饰器

    Args:
        cache: 缓存实例
        key_func: 自定义缓存键生成函数
        ttl: 缓存生存时间
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = (func.__name__, args, tuple(sorted(kwargs.items())))

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator


def demo_cache_system():
    """演示缓存系统"""
    print("=" * 60)
    print("缓存系统模块验证")
    print("=" * 60)
    print()

    # 1. LRU缓存
    print("1. LRU缓存:")
    lru = LRUCache[str, str](capacity=3)
    lru.set("a", "A")
    lru.set("b", "B")
    lru.set("c", "C")
    lru.get("a")  # 访问a
    lru.set("d", "D")  # 应淘汰b
    print(f"   键列表: {lru.keys()}")
    print(f"   b是否存在: {lru.get('b') is not None}")
    print()

    # 2. TTL缓存
    print("2. TTL缓存:")
    ttl_cache = TTLCache[str, str](default_ttl=0.2)
    ttl_cache.set("x", "X")
    print(f"   设置后获取: {ttl_cache.get('x')}")
    time.sleep(0.25)
    print(f"   过期后获取: {ttl_cache.get('x')}")
    print()

    # 3. 内存缓存
    print("3. 内存缓存:")
    mem = MemoryCache[str, int](max_size=100, default_ttl=1.0)
    mem.set("count", 42)
    print(f"   获取: {mem.get('count')}")
    print(f"   统计: {mem.get_stats()}")
    print()

    # 4. 缓存管理器
    print("4. 缓存管理器:")
    manager = CacheManager()
    c1 = manager.create_lru("users", 100)
    c2 = manager.create_ttl("sessions", 3600)
    c1.set("u1", "Alice")
    c2.set("s1", "session_data")
    print(f"   所有统计: {manager.get_all_stats()}")
    print()

    # 5. 装饰器
    print("5. 缓存装饰器:")
    calc_cache = MemoryCache[str, int]()

    @cached(calc_cache)
    def fib(n: int) -> int:
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)

    result = fib(10)
    print(f"   fib(10) = {result}")
    print(f"   缓存统计: {calc_cache.get_stats()}")
    print()

    print("=" * 60)
    print("缓存系统模块验证成功")
    print("=" * 60)


if __name__ == "__main__":
    demo_cache_system()
