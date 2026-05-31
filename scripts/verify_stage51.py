#!/usr/bin/env python3
"""
阶段51验证脚本：配置管理增强

测试内容：
1. 配置分层管理
2. 配置验证
3. 配置热加载
4. 配置变更监听
5. 文件配置源
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.config_manager import (
    ConfigError,
    ConfigLayer,
    ConfigManager,
    ConfigSchema,
    DictConfigSource,
    FileConfigSource,
)


def test_config_layer_merge() -> bool:
    print("[Test] 配置分层合并")
    try:
        # 重置单例状态
        ConfigManager._instance = None
        manager = ConfigManager()

        manager.register_source(ConfigLayer.SYSTEM, DictConfigSource({"log_level": "INFO", "max_workers": 4}))
        manager.register_source(ConfigLayer.USER, DictConfigSource({"theme": "dark", "max_workers": 8}))
        manager.register_source(ConfigLayer.PROJECT, DictConfigSource({"project_name": "Demo"}))

        all_config = manager.get_all()
        assert all_config["log_level"] == "INFO"
        assert all_config["theme"] == "dark"
        assert all_config["project_name"] == "Demo"
        # 用户层覆盖系统层
        assert all_config["max_workers"] == 8
        print("  ✓ 分层合并正确")

        manager.set("log_level", "DEBUG", ConfigLayer.RUNTIME)
        assert manager.get("log_level") == "DEBUG"
        print("  ✓ 运行时层覆盖正确")

        print("[Pass] 配置分层合并\n")
        return True
    except Exception as e:
        print(f"[Fail] 配置分层合并: {e}\n")
        return False


def test_config_validation() -> bool:
    print("[Test] 配置验证")
    try:
        ConfigManager._instance = None
        manager = ConfigManager()
        manager.register_source(ConfigLayer.SYSTEM, DictConfigSource({"log_level": "INFO", "max_workers": 4}))

        manager.add_schema(ConfigSchema("log_level", str, required=True, choices=["DEBUG", "INFO", "WARNING", "ERROR"]))
        manager.add_schema(ConfigSchema("max_workers", int, required=True, min_value=1, max_value=64))

        errors = manager.validate()
        assert len(errors) == 0
        print("  ✓ 有效配置验证通过")

        manager.set("max_workers", 0, ConfigLayer.RUNTIME)
        errors = manager.validate()
        assert any("小于最小值" in e for e in errors)
        print("  ✓ 无效值检测正确")

        manager.set("log_level", "INVALID", ConfigLayer.RUNTIME)
        errors = manager.validate()
        assert any("不在可选范围" in e for e in errors)
        print("  ✓ 非法枚举值检测正确")

        print("[Pass] 配置验证\n")
        return True
    except Exception as e:
        print(f"[Fail] 配置验证: {e}\n")
        return False


def test_config_listener() -> bool:
    print("[Test] 配置变更监听")
    try:
        ConfigManager._instance = None
        manager = ConfigManager()
        manager.register_source(ConfigLayer.SYSTEM, DictConfigSource({"key1": "val1"}))

        changes = []
        def on_change(key, old, new):
            changes.append((key, old, new))

        manager.add_listener(on_change)
        manager.set("key1", "val2", ConfigLayer.RUNTIME)
        assert len(changes) == 1
        assert changes[0] == ("key1", "val1", "val2")
        print("  ✓ 变更监听触发正确")

        manager.remove_listener(on_change)
        manager.set("key1", "val3", ConfigLayer.RUNTIME)
        assert len(changes) == 1
        print("  ✓ 移除监听器后不再触发")

        print("[Pass] 配置变更监听\n")
        return True
    except Exception as e:
        print(f"[Fail] 配置变更监听: {e}\n")
        return False


def test_file_config_source() -> bool:
    print("[Test] 文件配置源")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "config.json")
            source = FileConfigSource(json_path)
            assert not source.exists()
            print("  ✓ 文件不存在检测正确")

            source.save({"name": "test", "value": 42})
            assert source.exists()
            print("  ✓ 文件保存成功")

            loaded = source.load()
            assert loaded["name"] == "test"
            assert loaded["value"] == 42
            print("  ✓ 文件加载正确")

            # 测试 JSON 配置在 manager 中的使用
            ConfigManager._instance = None
            manager = ConfigManager()
            manager.set_source_path(ConfigLayer.PROJECT, json_path)
            assert manager.get("name") == "test"
            print("  ✓ Manager 加载文件配置正确")

        print("[Pass] 文件配置源\n")
        return True
    except Exception as e:
        print(f"[Fail] 文件配置源: {e}\n")
        return False


def test_hot_reload() -> bool:
    print("[Test] 配置热加载")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "hot.json")
            with open(json_path, "w", encoding="utf-8") as f:
                f.write('{"version": 1}')

            ConfigManager._instance = None
            manager = ConfigManager()
            manager.set_source_path(ConfigLayer.PROJECT, json_path)
            assert manager.get("version") == 1
            print("  ✓ 初始加载正确")

            manager.enable_hot_reload(interval=0.5)
            print("  ✓ 热加载已启用")

            # 修改文件
            time.sleep(0.1)
            with open(json_path, "w", encoding="utf-8") as f:
                f.write('{"version": 2}')

            time.sleep(1.0)
            assert manager.get("version") == 2
            print("  ✓ 热加载检测到变更")

            manager.disable_hot_reload()
            print("  ✓ 热加载已禁用")

        print("[Pass] 配置热加载\n")
        return True
    except Exception as e:
        print(f"[Fail] 配置热加载: {e}\n")
        return False


def test_config_status() -> bool:
    print("[Test] 配置管理器状态")
    try:
        ConfigManager._instance = None
        manager = ConfigManager()
        manager.register_source(ConfigLayer.SYSTEM, DictConfigSource({"a": 1}))
        manager.add_schema(ConfigSchema("a", int))

        status = manager.get_status()
        assert "system" in status["layers"]
        assert status["schema_count"] == 1
        assert "a" in status["merged_keys"]
        print(f"  ✓ 状态信息正确: {status}")

        print("[Pass] 配置管理器状态\n")
        return True
    except Exception as e:
        print(f"[Fail] 配置管理器状态: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段51验证脚本：配置管理增强")
    print("=" * 60 + "\n")

    results = []
    results.append(("配置分层合并", test_config_layer_merge()))
    results.append(("配置验证", test_config_validation()))
    results.append(("配置变更监听", test_config_listener()))
    results.append(("文件配置源", test_file_config_source()))
    results.append(("配置热加载", test_hot_reload()))
    results.append(("配置管理器状态", test_config_status()))

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
        print("🎉 所有测试通过！阶段51验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
