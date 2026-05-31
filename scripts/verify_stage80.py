"""
阶段80验证脚本：兼容性层模块
"""

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.compatibility import (
    APICompatibility,
    CompatibilityError,
    CompatibilityLayer,
    DeprecationManager,
    DeprecationRecord,
    MigrationEngine,
    RemoveFieldMigration,
    RenameFieldMigration,
    VersionInfo,
    deprecated,
)


def test_version_parse():
    """测试版本解析"""
    v = VersionInfo.parse("2.5.1")
    assert v.major == 2
    assert v.minor == 5
    assert v.patch == 1
    print("✓ 版本解析测试通过")


def test_version_compare():
    """测试版本比较"""
    v1 = VersionInfo.parse("1.0.0")
    v2 = VersionInfo.parse("2.0.0")
    v3 = VersionInfo.parse("1.5.0")
    assert v1 < v2
    assert v3 > v1
    assert v2 >= v2
    assert v1 <= v3
    print("✓ 版本比较测试通过")


def test_deprecation_manager():
    """测试废弃管理器"""
    mgr = DeprecationManager()
    mgr.register(DeprecationRecord("old_api", "1.0.0", removal_version="2.0.0", replacement="new_api"))
    assert mgr.is_deprecated("old_api") is True
    assert mgr.is_deprecated("new_api") is False
    records = mgr.get_records()
    assert len(records) == 1
    print("✓ 废弃管理器测试通过")


def test_deprecated_decorator():
    """测试废弃装饰器"""
    @deprecated(since="1.0.0", removal="2.0.0", replacement="new_func")
    def old_func():
        return 42

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = old_func()
        assert result == 42
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "old_func" in str(w[0].message)
    print("✓ 废弃装饰器测试通过")


def test_rename_migration():
    """测试字段重命名迁移"""
    migration = RenameFieldMigration("1.0.0", "1.1.0", {"old_name": "new_name"})
    data = {"old_name": "value", "keep": "yes"}
    result = migration.migrate(data)
    assert "new_name" in result
    assert "old_name" not in result
    assert result["new_name"] == "value"
    print("✓ 字段重命名迁移测试通过")


def test_remove_migration():
    """测试字段移除迁移"""
    migration = RemoveFieldMigration("1.0.0", "2.0.0", ["deprecated"])
    data = {"deprecated": "xxx", "keep": "yes"}
    result = migration.migrate(data)
    assert "deprecated" not in result
    assert result["keep"] == "yes"
    print("✓ 字段移除迁移测试通过")


def test_migration_engine():
    """测试迁移引擎"""
    engine = MigrationEngine()
    engine.register(RenameFieldMigration("1.0.0", "1.1.0", {"a": "b"}))
    engine.register(RemoveFieldMigration("1.1.0", "2.0.0", ["c"]))

    data = {"a": "1", "c": "2", "d": "3"}
    result = engine.migrate(data, "1.0.0", "2.0.0")
    assert "b" in result
    assert "c" not in result
    assert result["b"] == "1"
    print("✓ 迁移引擎测试通过")


def test_migration_no_downgrade():
    """测试不支持降级"""
    engine = MigrationEngine()
    try:
        engine.migrate({}, "2.0.0", "1.0.0")
        assert False, "应抛出异常"
    except CompatibilityError as e:
        assert "不支持降级" in e.message
    print("✓ 不支持降级测试通过")


def test_api_compatibility():
    """测试API兼容性"""
    compat = APICompatibility()
    compat.register_adapter("v1", "get", lambda: "v1_result")
    compat.register_adapter("v2", "get", lambda: "v2_result")

    assert compat.call("v1", "get") == "v1_result"
    assert compat.call("v2", "get") == "v2_result"
    assert "v1" in compat.get_versions()
    print("✓ API兼容性测试通过")


def test_compatibility_layer():
    """测试兼容性层主类"""
    layer = CompatibilityLayer()
    layer.set_version("2.0.0")
    assert layer.get_version() == "2.0.0"
    assert layer.check_version("1.0.0") is True
    assert layer.check_version("3.0.0") is False

    status = layer.get_status()
    assert "current_version" in status
    print("✓ 兼容性层主类测试通过")


def main():
    print("=" * 60)
    print("阶段80验证：兼容性层模块")
    print("=" * 60)

    test_version_parse()
    test_version_compare()
    test_deprecation_manager()
    test_deprecated_decorator()
    test_rename_migration()
    test_remove_migration()
    test_migration_engine()
    test_migration_no_downgrade()
    test_api_compatibility()
    test_compatibility_layer()

    print("=" * 60)
    print("阶段80验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
