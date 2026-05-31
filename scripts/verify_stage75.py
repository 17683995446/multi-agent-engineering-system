#!/usr/bin/env python3
"""
阶段75验证脚本：配置中心

测试内容：
1. 配置设置/获取
2. 批量设置
3. 配置版本管理
4. 配置回滚
5. 灰度发布
6. 配置监听
7. 导出/导入
8. 作用域管理
"""

from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.config_center import (
    ConfigCenter,
    ConfigScope,
    GrayRule,
    GrayStrategy,
    get_config_center,
)


def test_set_get() -> bool:
    print("[Test] Set/Get - 配置设置获取")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set("app.name", "TestApp")
        assert cc.get("app.name") == "TestApp"
        print(f"  ✓ 设置/获取: {cc.get('app.name')}")

        cc.set("app.version", "1.0.0", scope=ConfigScope.APPLICATION)
        assert cc.get("app.version") == "1.0.0"
        print(f"  ✓ 带作用域设置: {cc.get('app.version')}")

        # 默认值
        assert cc.get("not_exist", "default") == "default"
        print(f"  ✓ 默认值正确")

        print("[Pass] Set/Get\n")
        return True
    except Exception as e:
        print(f"[Fail] Set/Get: {e}\n")
        return False


def test_batch_set() -> bool:
    print("[Test] Batch Set - 批量设置")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set_batch({
            "db.host": "localhost",
            "db.port": 3306,
            "db.name": "testdb",
        })

        assert cc.get("db.host") == "localhost"
        assert cc.get("db.port") == 3306
        assert cc.get("db.name") == "testdb"
        print(f"  ✓ 批量设置成功: {len(cc.get_all())} 个配置")

        print("[Pass] Batch Set\n")
        return True
    except Exception as e:
        print(f"[Fail] Batch Set: {e}\n")
        return False


def test_version_management() -> bool:
    print("[Test] Version Management - 版本管理")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set("key1", "value1")
        v1 = cc.create_version(comment="v1")
        assert v1.version_id != ""
        assert v1.checksum != ""
        print(f"  ✓ 版本创建: {v1.version_id}")

        cc.set("key1", "value2")
        v2 = cc.create_version(comment="v2")
        print(f"  ✓ 版本创建: {v2.version_id}")

        versions = cc.get_versions()
        assert len(versions) >= 2
        print(f"  ✓ 版本历史: {len(versions)} 个")

        # 版本信息
        info = v1.to_dict()
        assert "version_id" in info
        assert "checksum" in info
        print(f"  ✓ 版本信息: {info}")

        print("[Pass] Version Management\n")
        return True
    except Exception as e:
        print(f"[Fail] Version Management: {e}\n")
        return False


def test_rollback() -> bool:
    print("[Test] Rollback - 配置回滚")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set("version_key", "original")
        v1 = cc.create_version(comment="before")

        cc.set("version_key", "changed")
        assert cc.get("version_key") == "changed"
        print(f"  ✓ 修改后: {cc.get('version_key')}")

        result = cc.rollback(v1.version_id)
        assert result is True
        assert cc.get("version_key") == "original"
        print(f"  ✓ 回滚后: {cc.get('version_key')}")

        # 回滚不存在的版本
        result = cc.rollback("non_exist")
        assert result is False
        print(f"  ✓ 回滚不存在版本返回 False")

        print("[Pass] Rollback\n")
        return True
    except Exception as e:
        print(f"[Fail] Rollback: {e}\n")
        return False


def test_gray_release() -> bool:
    print("[Test] Gray Release - 灰度发布")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set("feature_x", "disabled")
        cc.setup_gray(
            key="feature_x",
            base_value="disabled",
            gray_value="enabled",
            rules=[GrayRule(strategy=GrayStrategy.PERCENTAGE, value=50.0)],
            enabled=True,
        )

        # 统计灰度命中
        hits = 0
        for _ in range(100):
            if cc.get("feature_x") == "enabled":
                hits += 1

        print(f"  ✓ 灰度命中: {hits}/100 (预期约50)")
        assert 30 <= hits <= 70, f"灰度命中次数异常: {hits}"

        # 禁用灰度
        cc.disable_gray("feature_x")
        assert cc.get("feature_x") == "disabled"
        print(f"  ✓ 禁用灰度后: {cc.get('feature_x')}")

        # 重新启用
        cc.enable_gray("feature_x")
        hits2 = 0
        for _ in range(100):
            if cc.get("feature_x") == "enabled":
                hits2 += 1
        assert 30 <= hits2 <= 70
        print(f"  ✓ 启用灰度后命中: {hits2}/100")

        # USER_ID 灰度
        cc.setup_gray(
            key="user_feature",
            base_value="off",
            gray_value="on",
            rules=[GrayRule(strategy=GrayStrategy.USER_ID, value=["user1", "user2"])],
            enabled=True,
        )
        assert cc.get("user_feature", context={"user_id": "user1"}) == "on"
        assert cc.get("user_feature", context={"user_id": "user3"}) == "off"
        print(f"  ✓ USER_ID 灰度规则正确")

        print("[Pass] Gray Release\n")
        return True
    except Exception as e:
        print(f"[Fail] Gray Release: {e}\n")
        return False


def test_listeners() -> bool:
    print("[Test] Listeners - 配置监听")
    try:
        cc = ConfigCenter()
        cc.clear()

        changes = []

        def global_listener(key, old, new):
            changes.append(("global", key, old, new))

        def specific_listener(key, old, new):
            changes.append(("specific", key, old, new))

        cc.add_global_listener(global_listener)
        cc.add_listener("specific_key", specific_listener)

        cc.set("any_key", "value1")
        cc.set("specific_key", "value2")

        assert len(changes) >= 2
        print(f"  ✓ 变更通知: {len(changes)} 次")

        cc.remove_global_listener(global_listener)
        cc.remove_listener("specific_key", specific_listener)

        # 移除后不再收到通知
        changes.clear()
        cc.set("any_key", "value3")
        assert len(changes) == 0
        print(f"  ✓ 移除监听器后无通知")

        print("[Pass] Listeners\n")
        return True
    except Exception as e:
        print(f"[Fail] Listeners: {e}\n")
        return False


def test_export_import() -> bool:
    print("[Test] Export/Import - 导出导入")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set_batch({"a": 1, "b": 2, "c": 3})
        exported = cc.export_configs()
        assert "a" in exported
        assert "b" in exported
        print(f"  ✓ 导出长度: {len(exported)} 字符")

        cc2 = ConfigCenter()
        cc2.clear()
        cc2.import_configs(exported)
        assert cc2.get("a") == 1
        assert cc2.get("b") == 2
        assert cc2.get("c") == 3
        print(f"  ✓ 导入后配置数: {len(cc2.get_all())}")

        print("[Pass] Export/Import\n")
        return True
    except Exception as e:
        print(f"[Fail] Export/Import: {e}\n")
        return False


def test_scope_management() -> bool:
    print("[Test] Scope Management - 作用域管理")
    try:
        cc = ConfigCenter()
        cc.clear()

        cc.set("global_key", "global", scope=ConfigScope.GLOBAL)
        cc.set("app_key", "app", scope=ConfigScope.APPLICATION)
        cc.set("svc_key", "svc", scope=ConfigScope.SERVICE)

        all_configs = cc.get_all()
        assert len(all_configs) == 3
        print(f"  ✓ 全部配置: {len(all_configs)}")

        global_configs = cc.get_all(scope=ConfigScope.GLOBAL)
        assert "global_key" in global_configs
        assert "app_key" not in global_configs
        print(f"  ✓ 全局配置过滤正确")

        status = cc.get_status()
        assert status["scopes"]["global"] == 1
        assert status["scopes"]["application"] == 1
        assert status["scopes"]["service"] == 1
        print(f"  ✓ 作用域统计: {status['scopes']}")

        print("[Pass] Scope Management\n")
        return True
    except Exception as e:
        print(f"[Fail] Scope Management: {e}\n")
        return False


def test_push_control() -> bool:
    print("[Test] Push Control - 推送控制")
    try:
        cc = ConfigCenter()
        cc.clear()

        changes = []

        def listener(key, old, new):
            changes.append(key)

        cc.add_global_listener(listener)

        # 正常推送
        cc.set("push_key1", "v1", push=True)
        assert len(changes) == 1
        print(f"  ✓ 推送开启: {len(changes)} 次通知")

        # 禁用推送
        cc.disable_push()
        cc.set("push_key2", "v2", push=True)
        assert len(changes) == 1  # 没有新增
        print(f"  ✓ 推送禁用: {len(changes)} 次通知")

        # 重新启用
        cc.enable_push()
        cc.set("push_key3", "v3", push=True)
        assert len(changes) == 2
        print(f"  ✓ 推送启用: {len(changes)} 次通知")

        cc.remove_global_listener(listener)
        print("[Pass] Push Control\n")
        return True
    except Exception as e:
        print(f"[Fail] Push Control: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段75验证脚本：配置中心")
    print("=" * 60 + "\n")

    results = []
    results.append(("Set/Get", test_set_get()))
    results.append(("Batch Set", test_batch_set()))
    results.append(("Version Management", test_version_management()))
    results.append(("Rollback", test_rollback()))
    results.append(("Gray Release", test_gray_release()))
    results.append(("Listeners", test_listeners()))
    results.append(("Export/Import", test_export_import()))
    results.append(("Scope Management", test_scope_management()))
    results.append(("Push Control", test_push_control()))

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
        print("🎉 所有测试通过！阶段75验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
