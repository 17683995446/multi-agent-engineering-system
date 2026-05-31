"""
兼容性层模块
遵循第一性原理：版本演进与平滑过渡

核心功能：
1. 版本兼容
2. API兼容
3. 数据迁移
4. 废弃警告
"""

from __future__ import annotations

import functools
import inspect
import threading
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from common.utils import setup_logger

logger = setup_logger(__name__)


class CompatibilityError(Exception):
    """兼容性异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@dataclass
class VersionInfo:
    """版本信息"""
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version: str) -> VersionInfo:
        """解析版本字符串"""
        parts = version.split(".")
        return cls(
            major=int(parts[0]) if len(parts) > 0 else 0,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0,
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: VersionInfo) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: VersionInfo) -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: VersionInfo) -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: VersionInfo) -> bool:
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)


@dataclass
class DeprecationRecord:
    """废弃记录"""
    name: str
    deprecated_since: str
    removal_version: Optional[str] = None
    replacement: Optional[str] = None
    message: str = ""


class DeprecationManager:
    """
    废弃管理器

    管理废弃API的警告与追踪
    """

    def __init__(self):
        self._records: Dict[str, DeprecationRecord] = {}
        self._lock = threading.RLock()

    def register(self, record: DeprecationRecord) -> None:
        """注册废弃记录"""
        with self._lock:
            self._records[record.name] = record
        logger.info(f"注册废弃记录: {record.name} (since {record.deprecated_since})")

    def warn(self, name: str, stacklevel: int = 3) -> None:
        """发出废弃警告"""
        record = self._records.get(name)
        if not record:
            warnings.warn(f"{name} 已废弃", DeprecationWarning, stacklevel=stacklevel)
            return

        msg = f"{name} 自 {record.deprecated_since} 起已废弃"
        if record.removal_version:
            msg += f"，将在 {record.removal_version} 移除"
        if record.replacement:
            msg += f"，请使用 {record.replacement} 替代"
        if record.message:
            msg += f" ({record.message})"

        warnings.warn(msg, DeprecationWarning, stacklevel=stacklevel)
        logger.warning(msg)

    def is_deprecated(self, name: str) -> bool:
        """检查是否已废弃"""
        return name in self._records

    def get_records(self) -> List[DeprecationRecord]:
        """获取所有废弃记录"""
        with self._lock:
            return list(self._records.values())

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "deprecated_count": len(self._records),
                "deprecated_names": list(self._records.keys()),
            }


def deprecated(since: str, removal: Optional[str] = None, replacement: Optional[str] = None, message: str = ""):
    """废弃装饰器"""
    def decorator(func: Callable) -> Callable:
        name = func.__qualname__
        DeprecationManager().register(DeprecationRecord(
            name=name,
            deprecated_since=since,
            removal_version=removal,
            replacement=replacement,
            message=message,
        ))

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            DeprecationManager().warn(name, stacklevel=3)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DataMigration(ABC):
    """数据迁移基类"""

    def __init__(self, from_version: str, to_version: str):
        self.from_version = VersionInfo.parse(from_version)
        self.to_version = VersionInfo.parse(to_version)

    @abstractmethod
    def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """执行迁移"""
        pass

    def can_migrate(self, current_version: str) -> bool:
        """检查是否可以迁移"""
        v = VersionInfo.parse(current_version)
        return self.from_version <= v < self.to_version


class RenameFieldMigration(DataMigration):
    """字段重命名迁移"""

    def __init__(self, from_version: str, to_version: str, renames: Dict[str, str]):
        super().__init__(from_version, to_version)
        self.renames = renames

    def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(data)
        for old_name, new_name in self.renames.items():
            if old_name in result:
                result[new_name] = result.pop(old_name)
        return result


class RemoveFieldMigration(DataMigration):
    """字段移除迁移"""

    def __init__(self, from_version: str, to_version: str, fields: List[str]):
        super().__init__(from_version, to_version)
        self.fields = fields

    def migrate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(data)
        for field in self.fields:
            result.pop(field, None)
        return result


class MigrationEngine:
    """
    迁移引擎

    管理数据迁移流程
    """

    def __init__(self):
        self._migrations: List[DataMigration] = []
        self._lock = threading.RLock()

    def register(self, migration: DataMigration) -> None:
        """注册迁移"""
        with self._lock:
            self._migrations.append(migration)
            self._migrations.sort(key=lambda m: m.to_version)
        logger.info(f"注册迁移: {migration.from_version} -> {migration.to_version}")

    def migrate(self, data: Dict[str, Any], current_version: str, target_version: str) -> Dict[str, Any]:
        """执行迁移"""
        current = VersionInfo.parse(current_version)
        target = VersionInfo.parse(target_version)

        if current == target:
            return dict(data)

        if current > target:
            raise CompatibilityError(f"不支持降级: {current_version} -> {target_version}")

        result = dict(data)
        applied = []
        for migration in self._migrations:
            if migration.can_migrate(current_version):
                result = migration.migrate(result)
                applied.append(str(migration.to_version))
                current_version = str(migration.to_version)
                current = VersionInfo.parse(current_version)
                if current >= target:
                    break

        logger.info(f"迁移完成: {current_version} -> {target_version}，应用 {len(applied)} 个迁移")
        return result

    def get_migrations(self) -> List[DataMigration]:
        """获取所有迁移"""
        with self._lock:
            return self._migrations.copy()


class APICompatibility:
    """
    API兼容性层

    提供API版本适配
    """

    def __init__(self):
        self._adapters: Dict[str, Dict[str, Callable]] = {}
        self._lock = threading.RLock()

    def register_adapter(self, version: str, name: str, adapter: Callable) -> None:
        """注册API适配器"""
        with self._lock:
            if version not in self._adapters:
                self._adapters[version] = {}
            self._adapters[version][name] = adapter
        logger.info(f"注册API适配器: {name} (v{version})")

    def call(self, version: str, name: str, *args, **kwargs) -> Any:
        """调用适配的API"""
        with self._lock:
            adapters = self._adapters.get(version, {})
            adapter = adapters.get(name)
        if not adapter:
            raise CompatibilityError(f"未找到适配器: {name} (v{version})")
        return adapter(*args, **kwargs)

    def get_versions(self) -> List[str]:
        """获取所有版本"""
        with self._lock:
            return list(self._adapters.keys())


class CompatibilityLayer:
    """
    兼容性层主类

    整合版本兼容、API兼容、数据迁移、废弃警告
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
        self.deprecation = DeprecationManager()
        self.migration = MigrationEngine()
        self.api_compat = APICompatibility()
        self._current_version = "1.0.0"
        self._initialized = True
        logger.info("兼容性层初始化完成")

    def set_version(self, version: str) -> None:
        """设置当前版本"""
        self._current_version = version

    def get_version(self) -> str:
        """获取当前版本"""
        return self._current_version

    def check_version(self, required: str) -> bool:
        """检查版本兼容性"""
        current = VersionInfo.parse(self._current_version)
        req = VersionInfo.parse(required)
        return current >= req

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_version": self._current_version,
            "deprecated_count": len(self.deprecation.get_records()),
            "migration_count": len(self.migration.get_migrations()),
            "api_versions": self.api_compat.get_versions(),
        }


def demo_compatibility():
    """演示兼容性层"""
    print("=" * 60)
    print("兼容性层演示")
    print("=" * 60)
    print()

    layer = CompatibilityLayer()
    layer.set_version("2.0.0")

    print("1. 版本比较:")
    v1 = VersionInfo.parse("1.5.0")
    v2 = VersionInfo.parse("2.0.0")
    print(f"   ✓ 1.5.0 < 2.0.0: {v1 < v2}")
    print(f"   ✓ 当前版本: {layer.get_version()}")
    print(f"   ✓ 兼容 1.0.0: {layer.check_version('1.0.0')}")
    print()

    print("2. 废弃警告:")
    @deprecated(since="1.5.0", removal="3.0.0", replacement="new_function")
    def old_function():
        return "旧功能"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        old_function()
        if w:
            print(f"   ✓ 捕获警告: {w[0].message}")
    print()

    print("3. 数据迁移:")
    engine = MigrationEngine()
    engine.register(RenameFieldMigration("1.0.0", "1.1.0", {"old_name": "new_name"}))
    engine.register(RemoveFieldMigration("1.1.0", "2.0.0", ["deprecated_field"]))

    data = {"old_name": "Alice", "deprecated_field": "xxx", "keep": "yes"}
    migrated = engine.migrate(data, "1.0.0", "2.0.0")
    print(f"   ✓ 原始数据: {data}")
    print(f"   ✓ 迁移后: {migrated}")
    print()

    print("4. API兼容性:")
    compat = APICompatibility()
    compat.register_adapter("v1", "get_user", lambda uid: {"id": uid, "name": "User"})
    compat.register_adapter("v2", "get_user", lambda uid: {"id": uid, "name": "User", "version": 2})

    v1_result = compat.call("v1", "get_user", 1)
    v2_result = compat.call("v2", "get_user", 1)
    print(f"   ✓ v1 API: {v1_result}")
    print(f"   ✓ v2 API: {v2_result}")
    print()

    print("5. 兼容性层状态:")
    status = layer.get_status()
    print(f"   ✓ {status}")
    print()

    print("=" * 60)
    print("兼容性层演示完成")
    print("=" * 60)
    print()
    print("✓ 版本兼容")
    print("✓ API兼容")
    print("✓ 数据迁移")
    print("✓ 废弃警告")
    print()


if __name__ == "__main__":
    demo_compatibility()
