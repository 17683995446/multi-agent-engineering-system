"""
公共层 - 配置中心模块
遵循第一性原理：集中管理、动态推送、版本控制、灰度发布

核心功能：
1. 集中配置管理
2. 配置推送（热更新）
3. 配置版本管理
4. 配置灰度发布
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from common.utils import setup_logger

logger = setup_logger(__name__)


class ConfigScope(Enum):
    """配置作用域"""
    GLOBAL = "global"
    APPLICATION = "application"
    SERVICE = "service"
    INSTANCE = "instance"


class GrayStrategy(Enum):
    """灰度策略"""
    PERCENTAGE = "percentage"
    USER_ID = "user_id"
    IP_RANGE = "ip_range"
    HEADER = "header"


class ConfigException(Exception):
    """配置异常"""
    pass


@dataclass
class ConfigVersion:
    """配置版本"""
    version_id: str = ""
    config_data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    created_by: str = ""
    comment: str = ""
    checksum: str = ""

    def __post_init__(self):
        if not self.version_id:
            self.version_id = self._generate_version_id()
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _generate_version_id(self) -> str:
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]

    def _compute_checksum(self) -> str:
        data_str = json.dumps(self.config_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "comment": self.comment,
            "checksum": self.checksum,
            "config_keys": list(self.config_data.keys()),
        }


@dataclass
class GrayRule:
    """灰度规则"""
    strategy: GrayStrategy = GrayStrategy.PERCENTAGE
    value: Any = None
    enabled: bool = True

    def match(self, context: Dict[str, Any]) -> bool:
        """判断是否匹配灰度规则"""
        if not self.enabled:
            return False

        if self.strategy == GrayStrategy.PERCENTAGE:
            # 按百分比灰度
            import random
            percent = float(self.value) if self.value is not None else 0
            return random.random() * 100 < percent

        elif self.strategy == GrayStrategy.USER_ID:
            user_id = context.get("user_id", "")
            if isinstance(self.value, (list, set)):
                return str(user_id) in [str(v) for v in self.value]
            return str(user_id) == str(self.value)

        elif self.strategy == GrayStrategy.IP_RANGE:
            ip = context.get("ip", "")
            if isinstance(self.value, list) and len(self.value) == 2:
                return self.value[0] <= ip <= self.value[1]
            return ip == self.value

        elif self.strategy == GrayStrategy.HEADER:
            header_name = self.value.get("name", "") if isinstance(self.value, dict) else ""
            header_value = self.value.get("value", "") if isinstance(self.value, dict) else ""
            return context.get("headers", {}).get(header_name) == header_value

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "value": self.value,
            "enabled": self.enabled,
        }


@dataclass
class GrayConfig:
    """灰度配置"""
    config_key: str = ""
    base_value: Any = None
    gray_value: Any = None
    rules: List[GrayRule] = field(default_factory=list)
    enabled: bool = False

    def get_value(self, context: Optional[Dict[str, Any]] = None) -> Any:
        """获取配置值（根据灰度规则）"""
        if not self.enabled or not self.rules:
            return self.base_value

        context = context or {}
        for rule in self.rules:
            if rule.match(context):
                return self.gray_value
        return self.base_value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_key": self.config_key,
            "base_value": self.base_value,
            "gray_value": self.gray_value,
            "rules": [r.to_dict() for r in self.rules],
            "enabled": self.enabled,
        }


class ConfigCenter:
    """
    配置中心

    集中配置管理、配置推送、配置版本、配置灰度
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

        self.logger = setup_logger("common.config_center")
        self._configs: Dict[str, Any] = {}
        self._versions: Dict[str, List[ConfigVersion]] = {}
        self._gray_configs: Dict[str, GrayConfig] = {}
        self._listeners: Dict[str, List[Callable[[str, Any, Any], None]]] = {}
        self._global_listeners: List[Callable[[str, Any, Any], None]] = []
        self._scopes: Dict[str, ConfigScope] = {}
        self._lock = threading.RLock()
        self._push_enabled = True
        self._initialized = True
        self.logger.info("配置中心初始化完成")

    def set(self, key: str, value: Any, scope: ConfigScope = ConfigScope.GLOBAL, push: bool = True) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            scope: 作用域
            push: 是否推送变更
        """
        with self._lock:
            old_value = self._configs.get(key)
            self._configs[key] = value
            self._scopes[key] = scope

        if push and old_value != value:
            self._notify_change(key, old_value, value)
            self.logger.debug(f"配置已更新: {key} = {value}")

    def get(self, key: str, default: Any = None, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值
            context: 灰度上下文
        """
        with self._lock:
            # 检查灰度配置
            gray = self._gray_configs.get(key)
            if gray and gray.enabled:
                return gray.get_value(context)
            return self._configs.get(key, default)

    def get_all(self, scope: Optional[ConfigScope] = None) -> Dict[str, Any]:
        """获取所有配置"""
        with self._lock:
            if scope is None:
                return copy.deepcopy(self._configs)
            return {k: v for k, v in self._configs.items() if self._scopes.get(k) == scope}

    def delete(self, key: str, push: bool = True) -> bool:
        """删除配置"""
        with self._lock:
            if key not in self._configs:
                return False
            old_value = self._configs.pop(key)
            self._scopes.pop(key, None)

        if push:
            self._notify_change(key, old_value, None)
        return True

    def set_batch(self, configs: Dict[str, Any], scope: ConfigScope = ConfigScope.GLOBAL) -> None:
        """批量设置配置"""
        for key, value in configs.items():
            self.set(key, value, scope)

    def create_version(self, comment: str = "", created_by: str = "system") -> ConfigVersion:
        """创建配置版本快照"""
        with self._lock:
            version = ConfigVersion(
                config_data=copy.deepcopy(self._configs),
                created_at=time.time(),
                created_by=created_by,
                comment=comment,
            )
            # 保存版本历史
            for key in self._configs:
                if key not in self._versions:
                    self._versions[key] = []
                self._versions[key].append(version)
                # 限制历史数量
                if len(self._versions[key]) > 50:
                    self._versions[key] = self._versions[key][-50:]
        self.logger.info(f"配置版本已创建: {version.version_id}")
        return version

    def get_versions(self, key: Optional[str] = None) -> List[ConfigVersion]:
        """获取版本历史"""
        with self._lock:
            if key:
                return list(self._versions.get(key, []))
            # 返回所有版本（去重）
            all_versions = []
            seen = set()
            for versions in self._versions.values():
                for v in versions:
                    if v.version_id not in seen:
                        seen.add(v.version_id)
                        all_versions.append(v)
            return sorted(all_versions, key=lambda x: x.created_at, reverse=True)

    def rollback(self, version_id: str) -> bool:
        """回滚到指定版本"""
        with self._lock:
            for versions in self._versions.values():
                for v in versions:
                    if v.version_id == version_id:
                        old_configs = copy.deepcopy(self._configs)
                        self._configs = copy.deepcopy(v.config_data)
                        # 通知变更
                        for key, new_value in self._configs.items():
                            old_value = old_configs.get(key)
                            if old_value != new_value:
                                self._notify_change(key, old_value, new_value)
                        self.logger.info(f"配置已回滚到版本: {version_id}")
                        return True
        return False

    def setup_gray(self, key: str, base_value: Any, gray_value: Any, rules: List[GrayRule], enabled: bool = True) -> None:
        """
        设置灰度配置

        Args:
            key: 配置键
            base_value: 基础值
            gray_value: 灰度值
            rules: 灰度规则列表
            enabled: 是否启用
        """
        with self._lock:
            self._gray_configs[key] = GrayConfig(
                config_key=key,
                base_value=base_value,
                gray_value=gray_value,
                rules=rules,
                enabled=enabled,
            )
        self.logger.info(f"灰度配置已设置: {key}, 规则数: {len(rules)}")

    def disable_gray(self, key: str) -> None:
        """禁用灰度配置"""
        with self._lock:
            if key in self._gray_configs:
                self._gray_configs[key].enabled = False

    def enable_gray(self, key: str) -> None:
        """启用灰度配置"""
        with self._lock:
            if key in self._gray_configs:
                self._gray_configs[key].enabled = True

    def get_gray_status(self, key: str) -> Optional[GrayConfig]:
        """获取灰度配置状态"""
        with self._lock:
            return self._gray_configs.get(key)

    def add_listener(self, key: str, callback: Callable[[str, Any, Any], None]) -> None:
        """添加配置变更监听器（指定key）"""
        with self._lock:
            if key not in self._listeners:
                self._listeners[key] = []
            self._listeners[key].append(callback)

    def remove_listener(self, key: str, callback: Callable[[str, Any, Any], None]) -> None:
        """移除配置变更监听器"""
        with self._lock:
            if key in self._listeners and callback in self._listeners[key]:
                self._listeners[key].remove(callback)

    def add_global_listener(self, callback: Callable[[str, Any, Any], None]) -> None:
        """添加全局配置变更监听器"""
        self._global_listeners.append(callback)

    def remove_global_listener(self, callback: Callable[[str, Any, Any], None]) -> None:
        """移除全局配置变更监听器"""
        if callback in self._global_listeners:
            self._global_listeners.remove(callback)

    def _notify_change(self, key: str, old_value: Any, new_value: Any) -> None:
        """通知配置变更"""
        if not self._push_enabled:
            return

        # 通知特定监听器
        listeners = self._listeners.get(key, [])
        for listener in listeners:
            try:
                listener(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"配置变更监听器执行失败: {e}")

        # 通知全局监听器
        for listener in self._global_listeners:
            try:
                listener(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"全局配置变更监听器执行失败: {e}")

    def enable_push(self) -> None:
        """启用配置推送"""
        self._push_enabled = True

    def disable_push(self) -> None:
        """禁用配置推送"""
        self._push_enabled = False

    def get_status(self) -> Dict[str, Any]:
        """获取配置中心状态"""
        with self._lock:
            return {
                "config_count": len(self._configs),
                "version_count": sum(len(v) for v in self._versions.values()),
                "gray_count": len(self._gray_configs),
                "listener_count": sum(len(v) for v in self._listeners.values()) + len(self._global_listeners),
                "push_enabled": self._push_enabled,
                "scopes": {s.value: sum(1 for sc in self._scopes.values() if sc == s) for s in ConfigScope},
            }

    def export_configs(self) -> str:
        """导出配置为JSON字符串"""
        with self._lock:
            return json.dumps(self._configs, ensure_ascii=False, indent=2)

    def import_configs(self, json_str: str, scope: ConfigScope = ConfigScope.GLOBAL) -> None:
        """从JSON字符串导入配置"""
        configs = json.loads(json_str)
        self.set_batch(configs, scope)

    def clear(self) -> None:
        """清空所有配置"""
        with self._lock:
            self._configs.clear()
            self._versions.clear()
            self._gray_configs.clear()
            self._listeners.clear()
            self._global_listeners.clear()
            self._scopes.clear()
        self.logger.info("配置中心已清空")


def get_config_center() -> ConfigCenter:
    """获取配置中心实例（单例）"""
    return ConfigCenter()


def demo_config_center():
    """演示配置中心"""
    print("=" * 60)
    print("配置中心模块验证")
    print("=" * 60)
    print()

    cc = ConfigCenter()
    cc.clear()

    print("1. 设置配置:")
    cc.set("app.name", "MyApp")
    cc.set("app.version", "1.0.0")
    cc.set("feature.flag", True, scope=ConfigScope.APPLICATION)
    print(f"   ✓ app.name = {cc.get('app.name')}")
    print(f"   ✓ app.version = {cc.get('app.version')}")
    print(f"   ✓ feature.flag = {cc.get('feature.flag')}")
    print()

    print("2. 批量设置:")
    cc.set_batch({"db.host": "localhost", "db.port": 3306, "db.name": "mydb"})
    print(f"   ✓ 批量设置完成，共 {len(cc.get_all())} 个配置")
    print()

    print("3. 配置版本管理:")
    v1 = cc.create_version(comment="初始版本")
    print(f"   ✓ 版本已创建: {v1.version_id}")
    cc.set("app.version", "1.1.0")
    v2 = cc.create_version(comment="更新版本")
    print(f"   ✓ 版本已创建: {v2.version_id}")

    versions = cc.get_versions()
    print(f"   ✓ 版本历史数: {len(versions)}")
    print()

    print("4. 配置回滚:")
    print(f"   回滚前 app.version = {cc.get('app.version')}")
    cc.rollback(v1.version_id)
    print(f"   回滚后 app.version = {cc.get('app.version')}")
    print()

    print("5. 灰度发布:")
    cc.set("new_feature", "disabled")
    cc.setup_gray(
        key="new_feature",
        base_value="disabled",
        gray_value="enabled",
        rules=[GrayRule(strategy=GrayStrategy.PERCENTAGE, value=50.0)],
        enabled=True,
    )

    # 模拟多次请求
    gray_hits = 0
    for i in range(100):
        value = cc.get("new_feature")
        if value == "enabled":
            gray_hits += 1
    print(f"   ✓ 灰度命中次数: {gray_hits}/100 (预期约50)")
    print()

    print("6. 配置变更监听:")
    changes = []
    def on_change(key, old, new):
        changes.append((key, old, new))

    cc.add_global_listener(on_change)
    cc.set("app.name", "NewApp")
    print(f"   ✓ 变更记录: {changes}")
    cc.remove_global_listener(on_change)
    print()

    print("7. 配置导出导入:")
    exported = cc.export_configs()
    print(f"   ✓ 导出配置长度: {len(exported)} 字符")

    cc2 = ConfigCenter()
    cc2.clear()
    cc2.import_configs(exported)
    print(f"   ✓ 导入后配置数: {len(cc2.get_all())}")
    print()

    print("8. 状态统计:")
    status = cc.get_status()
    print(f"   ✓ 状态: {status}")
    print()

    print("=" * 60)
    print("配置中心模块验证成功")
    print("=" * 60)
    print()
    print("✓ 集中配置管理")
    print("✓ 配置推送（热更新）")
    print("✓ 配置版本管理")
    print("✓ 配置灰度发布")
    print()


if __name__ == "__main__":
    demo_config_center()
