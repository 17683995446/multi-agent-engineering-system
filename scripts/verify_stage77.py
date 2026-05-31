"""
阶段77验证脚本：RPC框架模块
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.rpc_framework import (
    JSONSerializer,
    LocalTransport,
    RPCClient,
    RPCError,
    RPCNotFoundError,
    RPCProxy,
    RPCRequest,
    RPCResponse,
    RPCServer,
)


def test_json_serializer():
    """测试JSON序列化器"""
    serializer = JSONSerializer()
    data = {"key": "value", "number": 42}
    serialized = serializer.serialize(data)
    deserialized = serializer.deserialize(serialized)
    assert deserialized == data
    print("✓ JSON序列化测试通过")


def test_rpc_request_response():
    """测试RPC请求/响应数据模型"""
    req = RPCRequest(request_id="123", method="test", params={"a": 1})
    req_dict = req.to_dict()
    req2 = RPCRequest.from_dict(req_dict)
    assert req2.request_id == "123"
    assert req2.method == "test"

    resp = RPCResponse(request_id="123", success=True, result=42)
    resp_dict = resp.to_dict()
    resp2 = RPCResponse.from_dict(resp_dict)
    assert resp2.success is True
    assert resp2.result == 42
    print("✓ RPC请求/响应模型测试通过")


def test_rpc_server_register():
    """测试RPC服务器方法注册"""
    server = RPCServer()
    server.register("echo", lambda msg: msg)
    assert "echo" in server.get_methods()
    print("✓ RPC方法注册测试通过")


def test_rpc_sync_call():
    """测试同步RPC调用"""
    server = RPCServer()
    server.register("add", lambda a, b: a + b)
    transport = LocalTransport(server.handle)
    client = RPCClient(transport)

    result = client.call("add", a=2, b=3)
    assert result == 5
    print("✓ 同步RPC调用测试通过")


def test_rpc_error_handling():
    """测试RPC错误处理"""
    server = RPCServer()
    server.register("fail", lambda: (_ for _ in ()).throw(ValueError("故意失败")))
    transport = LocalTransport(server.handle)
    client = RPCClient(transport)

    try:
        client.call("not_exist")
        assert False, "应抛出RPCError"
    except RPCError as e:
        assert e.code == "RPC_NOT_FOUND"

    try:
        client.call("fail")
        assert False, "应抛出RPCError"
    except RPCError as e:
        assert "RPC_INTERNAL_ERROR" == e.code
    print("✓ RPC错误处理测试通过")


def test_rpc_async_call():
    """测试异步RPC调用"""
    server = RPCServer()
    server.register("slow_add", lambda a, b: a + b)
    transport = LocalTransport(server.handle)
    client = RPCClient(transport)

    results = []
    def callback(result, error):
        results.append((result, error))

    thread = client.call_async("slow_add", callback=callback, a=5, b=7)
    thread.join(timeout=2.0)
    assert len(results) == 1
    assert results[0][0] == 12
    assert results[0][1] is None
    print("✓ 异步RPC调用测试通过")


def test_rpc_proxy():
    """测试RPC代理"""
    server = RPCServer()
    server.register("math.add", lambda a, b: a + b)
    transport = LocalTransport(server.handle)
    client = RPCClient(transport)
    proxy = RPCProxy(client, prefix="math")

    result = proxy.add(a=3, b=4)
    assert result == 7
    print("✓ RPC代理测试通过")


def test_rpc_register_instance():
    """测试注册实例方法"""
    class Calculator:
        def add(self, a, b):
            return a + b

    server = RPCServer()
    calc = Calculator()
    server.register_instance(calc, prefix="calc")
    assert "calc.add" in server.get_methods()

    transport = LocalTransport(server.handle)
    client = RPCClient(transport)
    result = client.call("calc.add", a=1, b=2)
    assert result == 3
    print("✓ 注册实例方法测试通过")


def main():
    print("=" * 60)
    print("阶段77验证：RPC框架模块")
    print("=" * 60)

    test_json_serializer()
    test_rpc_request_response()
    test_rpc_server_register()
    test_rpc_sync_call()
    test_rpc_error_handling()
    test_rpc_async_call()
    test_rpc_proxy()
    test_rpc_register_instance()

    print("=" * 60)
    print("阶段77验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
