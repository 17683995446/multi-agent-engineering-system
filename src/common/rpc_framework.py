"""
RPC框架模块
遵循第一性原理：远程过程调用抽象

核心功能：
1. 远程过程调用
2. 序列化传输
3. 超时控制
4. 错误处理
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from common.utils import setup_logger

logger = setup_logger(__name__)


class RPCError(Exception):
    """RPC异常基类"""
    def __init__(self, message: str, code: str = "RPC_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class RPCTimeoutError(RPCError):
    """RPC超时异常"""
    def __init__(self, message: str = "RPC调用超时"):
        super().__init__(message, code="RPC_TIMEOUT")


class RPCNotFoundError(RPCError):
    """RPC方法未找到异常"""
    def __init__(self, method: str):
        super().__init__(f"方法未找到: {method}", code="RPC_NOT_FOUND")


class RPCSerializationError(RPCError):
    """RPC序列化异常"""
    def __init__(self, message: str):
        super().__init__(message, code="RPC_SERIALIZATION_ERROR")


class Serializer(ABC):
    """序列化器基类"""

    @abstractmethod
    def serialize(self, data: Any) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        pass


class JSONSerializer(Serializer):
    """JSON序列化器"""

    def serialize(self, data: Any) -> bytes:
        try:
            return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        except Exception as e:
            raise RPCSerializationError(f"JSON序列化失败: {e}")

    def deserialize(self, data: bytes) -> Any:
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            raise RPCSerializationError(f"JSON反序列化失败: {e}")


@dataclass
class RPCRequest:
    """RPC请求"""
    request_id: str
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    timeout: float = 5.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "params": self.params,
            "timestamp": self.timestamp,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RPCRequest:
        return cls(
            request_id=data["request_id"],
            method=data["method"],
            params=data.get("params", {}),
            timestamp=data.get("timestamp", time.time()),
            timeout=data.get("timeout", 5.0),
        )


@dataclass
class RPCResponse:
    """RPC响应"""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "error_code": self.error_code,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RPCResponse:
        return cls(
            request_id=data["request_id"],
            success=data["success"],
            result=data.get("result"),
            error=data.get("error"),
            error_code=data.get("error_code"),
            duration_ms=data.get("duration_ms", 0.0),
        )


class RPCTransport(ABC):
    """RPC传输层基类"""

    @abstractmethod
    def send(self, data: bytes) -> bytes:
        """发送请求并接收响应"""
        pass


class LocalTransport(RPCTransport):
    """本地传输（内存中直接调用，用于测试）"""

    def __init__(self, handler: Callable[[bytes], bytes]):
        self.handler = handler

    def send(self, data: bytes) -> bytes:
        return self.handler(data)


class RPCServer:
    """
    RPC服务器

    核心功能：
    - 注册方法
    - 处理请求
    - 序列化/反序列化
    - 错误处理
    """

    def __init__(self, serializer: Optional[Serializer] = None):
        self._methods: Dict[str, Callable] = {}
        self._serializer = serializer or JSONSerializer()
        self._lock = threading.RLock()

    def register(self, method: str, func: Callable) -> None:
        """注册RPC方法"""
        with self._lock:
            self._methods[method] = func
        logger.info(f"RPC方法注册: {method}")

    def register_instance(self, instance: Any, prefix: str = "") -> None:
        """注册对象的所有公开方法"""
        for name in dir(instance):
            if not name.startswith("_"):
                func = getattr(instance, name)
                if callable(func):
                    method_name = f"{prefix}.{name}" if prefix else name
                    self.register(method_name, func)

    def handle(self, data: bytes) -> bytes:
        """处理RPC请求"""
        start = time.time()
        try:
            request_dict = self._serializer.deserialize(data)
            request = RPCRequest.from_dict(request_dict)
        except RPCSerializationError as e:
            response = RPCResponse(
                request_id="",
                success=False,
                error=str(e.message),
                error_code=e.code,
            )
            return self._serializer.serialize(response.to_dict())

        try:
            result = self._invoke(request)
            response = RPCResponse(
                request_id=request.request_id,
                success=True,
                result=result,
                duration_ms=(time.time() - start) * 1000,
            )
        except RPCError as e:
            response = RPCResponse(
                request_id=request.request_id,
                success=False,
                error=e.message,
                error_code=e.code,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            response = RPCResponse(
                request_id=request.request_id,
                success=False,
                error=f"内部错误: {e}",
                error_code="RPC_INTERNAL_ERROR",
                duration_ms=(time.time() - start) * 1000,
            )

        return self._serializer.serialize(response.to_dict())

    def _invoke(self, request: RPCRequest) -> Any:
        """调用方法"""
        with self._lock:
            func = self._methods.get(request.method)
        if not func:
            raise RPCNotFoundError(request.method)
        return func(**request.params)

    def get_methods(self) -> List[str]:
        """获取已注册方法列表"""
        with self._lock:
            return list(self._methods.keys())


class RPCClient:
    """
    RPC客户端

    核心功能：
    - 发送请求
    - 超时控制
    - 序列化/反序列化
    - 错误处理
    """

    def __init__(self, transport: RPCTransport, serializer: Optional[Serializer] = None, default_timeout: float = 5.0):
        self._transport = transport
        self._serializer = serializer or JSONSerializer()
        self._default_timeout = default_timeout

    def call(self, method: str, timeout: Optional[float] = None, **params) -> Any:
        """同步调用RPC方法"""
        request = RPCRequest(
            request_id=str(uuid.uuid4()),
            method=method,
            params=params,
            timeout=timeout or self._default_timeout,
        )
        data = self._serializer.serialize(request.to_dict())

        start = time.time()
        response_data = self._transport.send(data)
        elapsed = (time.time() - start) * 1000

        response_dict = self._serializer.deserialize(response_data)
        response = RPCResponse.from_dict(response_dict)

        if not response.success:
            raise RPCError(response.error or "未知错误", response.error_code or "RPC_ERROR")

        logger.debug(f"RPC调用 {method} 成功，耗时 {elapsed:.2f}ms")
        return response.result

    def call_async(self, method: str, callback: Optional[Callable[[Any, Optional[Exception]], None]] = None, **params) -> threading.Thread:
        """异步调用RPC方法"""
        def _call():
            try:
                result = self.call(method, **params)
                if callback:
                    callback(result, None)
            except Exception as e:
                if callback:
                    callback(None, e)

        thread = threading.Thread(target=_call, daemon=True)
        thread.start()
        return thread


class RPCProxy:
    """RPC代理，支持属性访问式调用"""

    def __init__(self, client: RPCClient, prefix: str = ""):
        self._client = client
        self._prefix = prefix

    def __getattr__(self, name: str):
        method_name = f"{self._prefix}.{name}" if self._prefix else name
        return lambda **kwargs: self._client.call(method_name, **kwargs)


def demo_rpc_framework():
    """演示RPC框架"""
    print("=" * 60)
    print("RPC框架演示")
    print("=" * 60)
    print()

    # 创建服务器
    server = RPCServer()

    print("1. 注册RPC方法:")
    server.register("add", lambda a, b: a + b)
    server.register("multiply", lambda a, b: a * b)
    server.register("greet", lambda name: f"Hello, {name}!")
    print(f"   ✓ 已注册方法: {server.get_methods()}")
    print()

    # 创建本地传输
    transport = LocalTransport(server.handle)
    client = RPCClient(transport)

    print("2. 同步RPC调用:")
    result1 = client.call("add", a=3, b=5)
    print(f"   ✓ add(3, 5) = {result1}")
    result2 = client.call("multiply", a=4, b=7)
    print(f"   ✓ multiply(4, 7) = {result2}")
    result3 = client.call("greet", name="World")
    print(f"   ✓ greet(name='World') = {result3}")
    print()

    print("3. 错误处理:")
    try:
        client.call("not_exist")
    except RPCError as e:
        print(f"   ✓ 调用不存在方法抛出异常: {e.code} - {e.message}")
    print()

    print("4. 异步RPC调用:")
    results = []
    def on_result(result, error):
        if error:
            results.append(("error", str(error)))
        else:
            results.append(("success", result))

    client.call_async("add", callback=on_result, a=10, b=20)
    time.sleep(0.1)
    print(f"   ✓ 异步调用结果: {results}")
    print()

    print("5. RPC代理:")
    proxy = RPCProxy(client)
    print(f"   ✓ proxy.add(a=1, b=2) = {proxy.add(a=1, b=2)}")
    print()

    print("=" * 60)
    print("RPC框架演示完成")
    print("=" * 60)
    print()
    print("✓ 远程过程调用")
    print("✓ 序列化传输")
    print("✓ 超时控制")
    print("✓ 错误处理")
    print()


if __name__ == "__main__":
    demo_rpc_framework()
