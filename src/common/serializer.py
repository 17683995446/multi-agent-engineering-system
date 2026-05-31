"""
数据序列化模块
遵循第一性原理：数据的可移植性与互操作性

核心功能：
1. JSON/MessagePack/Pickle序列化
2. 序列化器注册机制
3. 自定义序列化器
4. 自动格式检测
"""

from __future__ import annotations

import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class SerializationFormat(Enum):
    """序列化格式"""
    JSON = "json"
    MESSAGEPACK = "messagepack"
    PICKLE = "pickle"


class SerializationError(Exception):
    """序列化异常"""
    pass


class DeserializationError(Exception):
    """反序列化异常"""
    pass


class BaseSerializer(ABC):
    """序列化器抽象基类"""

    @property
    @abstractmethod
    def format(self) -> SerializationFormat:
        pass

    @abstractmethod
    def serialize(self, data: Any) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        pass


class JSONSerializer(BaseSerializer):
    """JSON序列化器"""

    def __init__(self, ensure_ascii: bool = False, indent: Optional[int] = None):
        self.ensure_ascii = ensure_ascii
        self.indent = indent

    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.JSON

    def serialize(self, data: Any) -> bytes:
        try:
            return json.dumps(data, ensure_ascii=self.ensure_ascii, indent=self.indent, default=str).encode("utf-8")
        except Exception as e:
            raise SerializationError(f"JSON序列化失败: {e}")

    def deserialize(self, data: bytes) -> Any:
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            raise DeserializationError(f"JSON反序列化失败: {e}")


class MessagePackSerializer(BaseSerializer):
    """MessagePack序列化器"""

    def __init__(self):
        self._msgpack = None
        try:
            import msgpack
            self._msgpack = msgpack
        except ImportError:
            logger.warning("msgpack库未安装，MessagePackSerializer不可用")

    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.MESSAGEPACK

    def _check_available(self):
        if self._msgpack is None:
            raise SerializationError("msgpack库未安装")

    def serialize(self, data: Any) -> bytes:
        self._check_available()
        try:
            return self._msgpack.packb(data, use_bin_type=True)
        except Exception as e:
            raise SerializationError(f"MessagePack序列化失败: {e}")

    def deserialize(self, data: bytes) -> Any:
        self._check_available()
        try:
            return self._msgpack.unpackb(data, raw=False)
        except Exception as e:
            raise DeserializationError(f"MessagePack反序列化失败: {e}")


class PickleSerializer(BaseSerializer):
    """Pickle序列化器"""

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol

    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.PICKLE

    def serialize(self, data: Any) -> bytes:
        try:
            return pickle.dumps(data, protocol=self.protocol)
        except Exception as e:
            raise SerializationError(f"Pickle序列化失败: {e}")

    def deserialize(self, data: bytes) -> Any:
        try:
            return pickle.loads(data)
        except Exception as e:
            raise DeserializationError(f"Pickle反序列化失败: {e}")


class SerializerRegistry:
    """序列化器注册表"""

    _instance: Optional[SerializerRegistry] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._serializers: Dict[SerializationFormat, BaseSerializer] = {}
            cls._instance._default_format = SerializationFormat.JSON
            cls._instance._register_defaults()
        return cls._instance

    def _register_defaults(self) -> None:
        """注册默认序列化器"""
        self.register(JSONSerializer())
        self.register(MessagePackSerializer())
        self.register(PickleSerializer())

    def register(self, serializer: BaseSerializer) -> None:
        """注册序列化器"""
        self._serializers[serializer.format] = serializer
        logger.debug(f"序列化器已注册: {serializer.format.value}")

    def unregister(self, format: SerializationFormat) -> bool:
        """注销序列化器"""
        if format in self._serializers:
            del self._serializers[format]
            return True
        return False

    def get(self, format: SerializationFormat) -> BaseSerializer:
        """获取序列化器"""
        if format not in self._serializers:
            raise SerializationError(f"未找到序列化器: {format.value}")
        return self._serializers[format]

    def set_default(self, format: SerializationFormat) -> None:
        """设置默认序列化格式"""
        if format not in self._serializers:
            raise SerializationError(f"未找到序列化器: {format.value}")
        self._default_format = format

    @property
    def default_format(self) -> SerializationFormat:
        return self._default_format

    @property
    def default_serializer(self) -> BaseSerializer:
        return self.get(self._default_format)

    def list_formats(self) -> list:
        """列出所有可用格式"""
        return [f.value for f in self._serializers.keys()]


class Serializer:
    """统一序列化接口"""

    def __init__(self, format: Optional[SerializationFormat] = None):
        self.registry = SerializerRegistry()
        self.format = format or self.registry.default_format

    def serialize(self, data: Any) -> bytes:
        """序列化数据"""
        serializer = self.registry.get(self.format)
        return serializer.serialize(data)

    def deserialize(self, data: bytes) -> Any:
        """反序列化数据"""
        serializer = self.registry.get(self.format)
        return serializer.deserialize(data)

    @staticmethod
    def auto_deserialize(data: bytes) -> Any:
        """自动检测格式并反序列化"""
        # 尝试JSON
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            pass

        # 尝试MessagePack
        try:
            import msgpack
            return msgpack.unpackb(data, raw=False)
        except Exception:
            pass

        # 尝试Pickle
        try:
            return pickle.loads(data)
        except Exception:
            pass

        raise DeserializationError("无法自动检测序列化格式")

    @staticmethod
    def detect_format(data: bytes) -> Optional[SerializationFormat]:
        """检测数据格式"""
        # JSON检测
        try:
            json.loads(data.decode("utf-8"))
            return SerializationFormat.JSON
        except Exception:
            pass

        # MessagePack检测
        try:
            import msgpack
            msgpack.unpackb(data, raw=False)
            return SerializationFormat.MESSAGEPACK
        except Exception:
            pass

        # Pickle检测（简单启发式）
        if data.startswith(b"\x80"):
            return SerializationFormat.PICKLE

        return None


# 便捷函数
def serialize(data: Any, format: str = "json") -> bytes:
    """便捷序列化函数"""
    fmt = SerializationFormat(format)
    serializer = Serializer(fmt)
    return serializer.serialize(data)


def deserialize(data: bytes, format: Optional[str] = None) -> Any:
    """便捷反序列化函数"""
    if format:
        fmt = SerializationFormat(format)
        serializer = Serializer(fmt)
        return serializer.deserialize(data)
    return Serializer.auto_deserialize(data)
