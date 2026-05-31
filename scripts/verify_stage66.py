#!/usr/bin/env python3
"""
阶段66验证脚本：API网关

测试内容：
1. 请求路由
2. 请求验证（认证）
3. 响应格式化
4. 中间件链
5. 路径参数
6. 错误处理
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.api_gateway import (
    APIGateway,
    AuthMiddleware,
    HTTPMethod,
    LoggingMiddleware,
    RateLimitMiddleware,
    Request,
    Response,
    Router,
    Route,
    ValidationMiddleware,
)


def test_request_routing() -> bool:
    print("[Test] 请求路由")
    try:
        gateway = APIGateway()

        @gateway.get("/items", name="list_items")
        def list_items(request: Request) -> Response:
            return Response(status_code=200, data={"items": [1, 2, 3]})

        @gateway.post("/items", name="create_item")
        def create_item(request: Request) -> Response:
            return Response(status_code=201, data={"id": 4})

        # GET /items
        req = Request(path="/items", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 200
        assert resp.data == {"items": [1, 2, 3]}
        print("  ✓ GET /items 路由正确")

        # POST /items
        req = Request(path="/items", method=HTTPMethod.POST)
        resp = gateway.handle(req)
        assert resp.status_code == 201
        assert resp.data == {"id": 4}
        print("  ✓ POST /items 路由正确")

        # 方法不匹配
        req = Request(path="/items", method=HTTPMethod.DELETE)
        resp = gateway.handle(req)
        assert resp.status_code == 404
        print("  ✓ 方法不匹配返回404")

        print("[Pass] 请求路由\n")
        return True
    except Exception as e:
        print(f"[Fail] 请求路由: {e}\n")
        return False


def test_request_validation() -> bool:
    print("[Test] 请求验证（认证）")
    try:
        gateway = APIGateway()
        auth = AuthMiddleware(tokens=["secret_token"])
        auth.add_public_path("/public")
        gateway.add_middleware(auth)

        @gateway.get("/public", name="public_route")
        def public_route(request: Request) -> Response:
            return Response(status_code=200, data={"public": True})

        @gateway.get("/private", name="private_route")
        def private_route(request: Request) -> Response:
            return Response(status_code=200, data={"private": True})

        # 公开路径无需认证
        req = Request(path="/public", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 200
        print("  ✓ 公开路径无需认证")

        # 私有路径未认证
        req = Request(path="/private", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 401
        print("  ✓ 私有路径未认证返回401")

        # 私有路径错误token
        req = Request(path="/private", method=HTTPMethod.GET, headers={"Authorization": "wrong"})
        resp = gateway.handle(req)
        assert resp.status_code == 401
        print("  ✓ 错误token返回401")

        # 私有路径正确token
        req = Request(path="/private", method=HTTPMethod.GET, headers={"Authorization": "secret_token"})
        resp = gateway.handle(req)
        assert resp.status_code == 200
        print("  ✓ 正确token通过认证")

        print("[Pass] 请求验证\n")
        return True
    except Exception as e:
        print(f"[Fail] 请求验证: {e}\n")
        return False


def test_response_formatting() -> bool:
    print("[Test] 响应格式化")
    try:
        gateway = APIGateway()

        @gateway.get("/data", name="get_data")
        def get_data(request: Request) -> Response:
            return Response(status_code=200, data={"key": "value"})

        req = Request(path="/data", method=HTTPMethod.GET)
        resp = gateway.handle(req)

        d = resp.to_dict()
        assert "status_code" in d
        assert "request_id" in d
        assert "processing_time_ms" in d
        assert d["data"] == {"key": "value"}
        print(f"  ✓ 响应字典结构正确: {d}")

        json_str = resp.to_json()
        assert "status_code" in json_str
        print(f"  ✓ JSON序列化正确")

        # 错误响应
        @gateway.get("/error", name="error_route")
        def error_route(request: Request) -> Response:
            return Response(status_code=500, error="Something went wrong")

        req = Request(path="/error", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        d = resp.to_dict()
        assert "error" in d
        assert "data" not in d
        print(f"  ✓ 错误响应格式正确")

        print("[Pass] 响应格式化\n")
        return True
    except Exception as e:
        print(f"[Fail] 响应格式化: {e}\n")
        return False


def test_middleware_chain() -> bool:
    print("[Test] 中间件链")
    try:
        gateway = APIGateway()

        call_order = []

        class TestMiddleware1(LoggingMiddleware):
            def process_request(self, request: Request) -> Request:
                call_order.append("m1_req")
                return request
            def process_response(self, request: Request, response: Response) -> Response:
                call_order.append("m1_resp")
                return response

        class TestMiddleware2(LoggingMiddleware):
            def process_request(self, request: Request) -> Request:
                call_order.append("m2_req")
                return request
            def process_response(self, request: Request, response: Response) -> Response:
                call_order.append("m2_resp")
                return response

        gateway.add_middleware(TestMiddleware1())
        gateway.add_middleware(TestMiddleware2())

        @gateway.get("/test", name="middleware_test")
        def middleware_test(request: Request) -> Response:
            call_order.append("handler")
            return Response(status_code=200, data={"ok": True})

        req = Request(path="/test", method=HTTPMethod.GET)
        gateway.handle(req)

        # 请求顺序: m1_req -> m2_req -> handler
        # 响应顺序: m2_resp -> m1_resp
        expected = ["m1_req", "m2_req", "handler", "m2_resp", "m1_resp"]
        assert call_order == expected, f"实际顺序: {call_order}"
        print(f"  ✓ 中间件执行顺序正确: {call_order}")

        print("[Pass] 中间件链\n")
        return True
    except Exception as e:
        print(f"[Fail] 中间件链: {e}\n")
        return False


def test_path_parameters() -> bool:
    print("[Test] 路径参数")
    try:
        gateway = APIGateway()

        @gateway.get("/users/{user_id}/orders/{order_id}", name="get_order")
        def get_order(request: Request) -> Response:
            params = request.context.get("path_params", {})
            return Response(status_code=200, data=params)

        req = Request(path="/users/42/orders/100", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 200
        assert resp.data == {"user_id": "42", "order_id": "100"}
        print(f"  ✓ 多路径参数解析正确: {resp.data}")

        # 不匹配
        req = Request(path="/users/42", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 404
        print("  ✓ 路径不匹配返回404")

        print("[Pass] 路径参数\n")
        return True
    except Exception as e:
        print(f"[Fail] 路径参数: {e}\n")
        return False


def test_error_handling() -> bool:
    print("[Test] 错误处理")
    try:
        gateway = APIGateway()

        @gateway.get("/exception", name="exception_route")
        def exception_route(request: Request) -> Response:
            raise ValueError("Test exception")

        req = Request(path="/exception", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 500
        assert "Test exception" in resp.error
        print(f"  ✓ 异常捕获返回500: {resp.error}")

        # 自定义错误处理器
        def custom_handler(request: Request, exc: Exception) -> Response:
            return Response(status_code=503, data={"custom": True})

        gateway.set_default_error_handler(custom_handler)

        req = Request(path="/exception", method=HTTPMethod.GET)
        resp = gateway.handle(req)
        assert resp.status_code == 503
        print("  ✓ 自定义错误处理器生效")

        print("[Pass] 错误处理\n")
        return True
    except Exception as e:
        print(f"[Fail] 错误处理: {e}\n")
        return False


def test_rate_limit() -> bool:
    print("[Test] 限流中间件")
    try:
        gateway = APIGateway()
        gateway.add_middleware(RateLimitMiddleware(max_requests=2, window_seconds=60))

        @gateway.get("/limited", name="limited_route")
        def limited_route(request: Request) -> Response:
            return Response(status_code=200, data={"ok": True})

        # 前2次通过
        for i in range(2):
            req = Request(path="/limited", method=HTTPMethod.GET, headers={"X-Client-ID": "client1"})
            resp = gateway.handle(req)
            assert resp.status_code == 200, f"第{i+1}次请求应通过"
        print("  ✓ 前2次请求通过")

        # 第3次被限流
        req = Request(path="/limited", method=HTTPMethod.GET, headers={"X-Client-ID": "client1"})
        resp = gateway.handle(req)
        assert resp.status_code == 429
        print("  ✓ 第3次请求被限流(429)")

        # 不同客户端不受影响
        req = Request(path="/limited", method=HTTPMethod.GET, headers={"X-Client-ID": "client2"})
        resp = gateway.handle(req)
        assert resp.status_code == 200
        print("  ✓ 不同客户端不受限流影响")

        print("[Pass] 限流中间件\n")
        return True
    except Exception as e:
        print(f"[Fail] 限流中间件: {e}\n")
        return False


def test_validation_middleware() -> bool:
    print("[Test] 参数验证中间件")
    try:
        gateway = APIGateway()
        vm = ValidationMiddleware()

        def validate_name(request: Request) -> Optional[str]:
            if not request.query_params.get("name"):
                return "Missing required parameter: name"
            return None

        vm.add_validator("/greet", validate_name)
        gateway.add_middleware(vm)

        @gateway.get("/greet", name="greet")
        def greet(request: Request) -> Response:
            name = request.query_params.get("name", "")
            return Response(status_code=200, data={"message": f"Hello, {name}"})

        # 缺少参数
        req = Request(path="/greet", method=HTTPMethod.GET, query_params={})
        resp = gateway.handle(req)
        assert resp.status_code == 400
        assert "name" in resp.error
        print(f"  ✓ 缺少参数返回400: {resp.error}")

        # 参数正确
        req = Request(path="/greet", method=HTTPMethod.GET, query_params={"name": "Alice"})
        resp = gateway.handle(req)
        assert resp.status_code == 200
        assert resp.data == {"message": "Hello, Alice"}
        print("  ✓ 参数正确通过验证")

        print("[Pass] 参数验证中间件\n")
        return True
    except Exception as e:
        print(f"[Fail] 参数验证中间件: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段66验证脚本：API网关")
    print("=" * 60 + "\n")

    results = []
    results.append(("请求路由", test_request_routing()))
    results.append(("请求验证", test_request_validation()))
    results.append(("响应格式化", test_response_formatting()))
    results.append(("中间件链", test_middleware_chain()))
    results.append(("路径参数", test_path_parameters()))
    results.append(("错误处理", test_error_handling()))
    results.append(("限流中间件", test_rate_limit()))
    results.append(("参数验证中间件", test_validation_middleware()))

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
        print("🎉 所有测试通过！阶段66验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
