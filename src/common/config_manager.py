"""
配置管理增强模块
遵循第一性原理：配置分层与热加载

核心功能：
1. 配置分层（系统/用户/项目）
2. 配置热加载
3. 配置验证
4. 配置变更监听
"""

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class ConfigLayer(Enum):
    """配置分层"""
    SYSTEM = "system"
    USER = "user"
    PROJECT = "project"
    RUNTIME = "runtime"


class ConfigError(Exception):
    """配置异常"""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class ConfigValidationError(ConfigError):
    """配置验证异常"""
    pass


@dataclass
class ConfigSchema:
    """配置项 schema"""
    key: str
    type: type
    required: bool = True
    default: Any = None
    choices: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    description: str = ""

    def validate(self, value: Any) -> List[str]:
        """验证配置值"""
        errors = []
        if value is None:
            if self.required:
                errors.append(f"配置项 '{self.key}' 为必填项")
            return errors
        if not isinstance(value, self.type):
            errors.append(f"配置项 '{self.key}' 类型错误，期望 {self.type.__name__}，实际 {type(value).__name__}")
            return errors
        if self.choices is not None and value not in self.choices:
            errors.append(f"配置项 '{self.key}' 值 '{value}' 不在可选范围 {self.choices} 内")
        if isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                errors.append(f"配置项 '{self.key}' 值 {value} 小于最小值 {self.min_value}")
            if self.max_value is not None and value > self.max_value:
                errors.append(f"配置项 '{self.key}' 值 {value} 大于最大值 {self.max_value}")
        return errors


class ConfigValidator:
    """配置验证器"""

    def __init__(self):
        self.schemas: Dict[str, ConfigSchema] = {}

    def add_schema(self, schema: ConfigSchema) -> None:
        """添加配置 schema"""
        self.schemas[schema.key] = schema

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """验证整个配置"""
        errors = []
        for schema in self.schemas.values():
            value = config.get(schema.key, schema.default)
            errors.extend(schema.validate(value))
        for key in config:
            if key not in self.schemas:
                errors.append(f"配置项 '{key}' 未在 schema 中定义")
        return errors

    def validate_value(self, key: str, value: Any) -> List[str]:
        """验证单个配置值"""
        schema = self.schemas.get(key)
        if schema is None:
            return [f"配置项 '{key}' 未在 schema 中定义"]
        return schema.validate(value)


class ConfigSource(ABC):
    """配置源基类"""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """加载配置"""
        pass

    @abstractmethod
    def save(self, config: Dict[str, Any]) -> None:
        """保存配置"""
        pass

    @abstractmethod
    def exists(self) -> bool:
        """配置源是否存在"""
        pass

    @abstractmethod
    def last_modified(self) -> float:
        """最后修改时间戳"""
        pass


class FileConfigSource(ConfigSource):
    """文件配置源"""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                if self.path.suffix in (".yaml", ".yml"):
                    import yaml
                    return yaml.safe_load(f) or {}
                elif self.path.suffix == ".json":
                    return json.load(f)
                else:
                    raise ConfigError(f"不支持的配置文件格式: {self.path.suffix}")
        except Exception as e:
            logger.error(f"加载配置文件失败 {self.path}: {e}")
            return {}

    def save(self, config: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            if self.path.suffix in (".yaml", ".yml"):
                import yaml
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            elif self.path.suffix == ".json":
                json.dump(config, f, ensure_ascii=False, indent=2)
            else:
                raise ConfigError(f"不支持的配置文件格式: {self.path.suffix}")

    def exists(self) -> bool:
        return self.path.exists()

    def last_modified(self) -> float:
        if not self.path.exists():
            return 0.0
        return self.path.stat().st_mtime


class DictConfigSource(ConfigSource):
    """字典配置源（运行时）"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or {}
        self._modified = time.time()

    def load(self) -> Dict[str, Any]:
        return self._data.copy()

    def save(self, config: Dict[str, Any]) -> None:
        self._data = config.copy()
        self._modified = time.time()

    def exists(self) -> bool:
        return True

    def last_modified(self) -> float:
        return self._modified

    def update(self, data: Dict[str, Any]) -> None:
        self._data.update(data)
        self._modified = time.time()


class ConfigManager:
    """
    配置管理器

    核心功能：
    - 配置分层（系统/用户/项目/运行时）
    - 配置热加载
    - 配置验证
    - 配置变更监听
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

        self._sources: Dict[ConfigLayer, ConfigSource] = {}
        self._configs: Dict[ConfigLayer, Dict[str, Any]] = {}
        self._merged: Dict[str, Any] = {}
        self._validator = ConfigValidator()
        self._listeners: List[Callable[[str, Any, Any], None]] = []
        self._hot_reload = False
        self._reload_interval = 5.0
        self._reload_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self._initialized = True
        logger.info("配置管理器初始化完成")

    def register_source(self, layer: ConfigLayer, source: ConfigSource) -> None:
        """注册配置源"""
        with self._lock:
            self._sources[layer] = source
            if source.exists():
                self._configs[layer] = source.load()
            else:
                self._configs[layer] = {}
            self._merge()
        logger.info(f"注册配置源: {layer.value}")

    def set_source_path(self, layer: ConfigLayer, path: Union[str, Path]) -> None:
        """设置配置文件路径"""
        self.register_source(layer, FileConfigSource(path))

    def add_schema(self, schema: ConfigSchema) -> None:
        """添加配置 schema"""
        self._validator.add_schema(schema)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            return self._merged.get(key, default)

    def set(self, key: str, value: Any, layer: ConfigLayer = ConfigLayer.RUNTIME) -> None:
        """设置配置值（默认运行时层）"""
        with self._lock:
            if layer not in self._configs:
                self._configs[layer] = {}
            old_value = self._merged.get(key)
            self._configs[layer][key] = value
            self._merge()
            if layer in self._sources:
                self._sources[layer].save(self._configs[layer])
        for listener in self._listeners:
            try:
                listener(key, old_value, value)
            except Exception as e:
                logger.error(f"配置变更监听器执行失败: {e}")
        logger.debug(f"设置配置: {key} = {value} (layer={layer.value})")

    def get_layer(self, layer: ConfigLayer) -> Dict[str, Any]:
        """获取指定层配置"""
        with self._lock:
            return self._configs.get(layer, {}).copy()

    def get_all(self) -> Dict[str, Any]:
        """获取合并后的全部配置"""
        with self._lock:
            return self._merged.copy()

    def validate(self) -> List[str]:
        """验证当前配置"""
        with self._lock:
            return self._validator.validate(self._merged)

    def validate_key(self, key: str) -> List[str]:
        """验证单个配置项"""
        with self._lock:
            return self._validator.validate_value(key, self._merged.get(key))

    def add_listener(self, callback: Callable[[str, Any, Any], None]) -> None:
        """添加配置变更监听器"""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Any, Any], None]) -> None:
        """移除配置变更监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def enable_hot_reload(self, interval: float = 5.0) -> None:
        """启用配置热加载"""
        if self._hot_reload:
            return
        self._hot_reload = True
        self._reload_interval = interval
        self._stop_event.clear()
        self._reload_thread = threading.Thread(target=self._reload_loop, daemon=True)
        self._reload_thread.start()
        logger.info(f"配置热加载已启用，间隔 {interval}s")

    def disable_hot_reload(self) -> None:
        """禁用配置热加载"""
        if not self._hot_reload:
            return
        self._hot_reload = False
        self._stop_event.set()
        if self._reload_thread:
            self._reload_thread.join(timeout=self._reload_interval + 1)
        logger.info("配置热加载已禁用")

    def _reload_loop(self) -> None:
        """热加载循环"""
        while not self._stop_event.is_set():
            self._check_and_reload()
            self._stop_event.wait(self._reload_interval)

    def _check_and_reload(self) -> None:
        """检查并重新加载变更的配置"""
        with self._lock:
            for layer, source in self._sources.items():
                if not source.exists():
                    continue
                last_modified = source.last_modified()
                current = self._configs.get(layer, {})
                if getattr(source, "_last_checked_modified", 0) != last_modified:
                    new_config = source.load()
                    if new_config != current:
                        self._configs[layer] = new_config
                        self._merge()
                        logger.info(f"配置热加载: {layer.value} 层配置已更新")
                    source._last_checked_modified = last_modified

    def _merge(self) -> None:
        """合并各层配置（优先级：runtime > project > user > system）"""
        merged: Dict[str, Any] = {}
        for layer in [
            ConfigLayer.SYSTEM,
            ConfigLayer.USER,
            ConfigLayer.PROJECT,
            ConfigLayer.RUNTIME,
        ]:
            if layer in self._configs:
                merged.update(self._configs[layer])
        self._merged = merged

    def reload(self) -> None:
        """手动重新加载所有配置源"""
        with self._lock:
            for layer, source in self._sources.items():
                if source.exists():
                    self._configs[layer] = source.load()
            self._merge()
        logger.info("配置手动重载完成")

    def save_layer(self, layer: ConfigLayer) -> None:
        """保存指定层配置到源"""
        with self._lock:
            if layer in self._sources and layer in self._configs:
                self._sources[layer].save(self._configs[layer])
                logger.info(f"配置层已保存: {layer.value}")

    def get_status(self) -> Dict[str, Any]:
        """获取配置管理器状态"""
        with self._lock:
            return {
                "layers": [l.value for l in self._sources.keys()],
                "hot_reload": self._hot_reload,
                "reload_interval": self._reload_interval,
                "listeners_count": len(self._listeners),
                "schema_count": len(self._validator.schemas),
                "merged_keys": list(self._merged.keys()),
            }


def demo_config_manager():
    """演示配置管理器"""
    print("=" * 60)
    print("配置管理增强演示")
    print("=" * 60)
    print()

    manager = ConfigManager()

    print("1. 注册分层配置源:")
    manager.register_source(ConfigLayer.SYSTEM, DictConfigSource({"log_level": "INFO", "max_workers": 4}))
    manager.register_source(ConfigLayer.USER, DictConfigSource({"theme": "dark"}))
    manager.register_source(ConfigLayer.PROJECT, DictConfigSource({"project_name": "Demo"}))
    print("   ✓ 系统层、用户层、项目层配置源已注册")
    print()

    print("2. 配置分层合并:")
    all_config = manager.get_all()
    print(f"   ✓ 合并后配置: {all_config}")
    print()

    print("3. 配置验证:")
    manager.add_schema(ConfigSchema("log_level", str, required=True, choices=["DEBUG", "INFO", "WARNING", "ERROR"]))
    manager.add_schema(ConfigSchema("max_workers", int, required=True, min_value=1, max_value=64))
    errors = manager.validate()
    print(f"   ✓ 验证结果: {errors if errors else '通过'}")
    print()

    print("4. 运行时配置覆盖:")
    manager.set("log_level", "DEBUG", ConfigLayer.RUNTIME)
    print(f"   ✓ 运行时覆盖后 log_level = {manager.get('log_level')}")
    print()

    print("5. 配置变更监听:")
    changes = []
    def on_change(key, old, new):
        changes.append((key, old, new))
    manager.add_listener(on_change)
    manager.set("theme", "light", ConfigLayer.RUNTIME)
    print(f"   ✓ 变更记录: {changes}")
    print()

    print("6. 配置管理器状态:")
    status = manager.get_status()
    print(f"   ✓ 状态: {status}")
    print()

    print("=" * 60)
    print("配置管理增强演示完成")
    print("=" * 60)
    print()
    print("✓ 配置分层管理")
    print("✓ 配置验证")
    print("✓ 配置热加载支持")
    print("✓ 配置变更监听")
    print()


if __name__ == "__main__":
    demo_config_manager()
