"""
API网关模块
遵循第一性原理：统一入口与职责分离

核心功能：
1. 请求路由 - URL到处理器的映射
2. 请求验证 - 参数校验与鉴权
3. 响应格式化 - 统一响应结构
4. 中间件链 - 可插拔的请求处理管道
"""

from __future__ import annotations

import json
import re
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class HTTPMethod(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class Request:
    """请求对象"""
    path: str
    method: HTTPMethod = HTTPMethod.GET
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method.value,
            "headers": self.headers,
            "query_params": self.query_params,
            "body": self.body,
            "timestamp": self.timestamp,
        }


@dataclass
class Response:
    """响应对象"""
    status_code: int = 200
    data: Any = None
    headers: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    request_id: str = ""
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status_code": self.status_code,
            "request_id": self.request_id,
            "processing_time_ms": round(self.processing_time_ms, 3),
        }
        if self.error:
            result["error"] = self.error
        else:
            result["data"] = self.data
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class Middleware(ABC):
    """中间件抽象基类"""

    @abstractmethod
    def process_request(self, request: Request) -> Request:
        """处理请求，返回修改后的请求"""
        pass

    @abstractmethod
    def process_response(self, request: Request, response: Response) -> Response:
        """处理响应，返回修改后的响应"""
        pass


class LoggingMiddleware(Middleware):
    """日志中间件"""

    def process_request(self, request: Request) -> Request:
        logger.info(f"[{request.request_id}] {request.method.value} {request.path}")
        return request

    def process_response(self, request: Request, response: Response) -> Response:
        logger.info(
            f"[{request.request_id}] {request.method.value} {request.path} "
            f"-> {response.status_code} ({response.processing_time_ms:.2f}ms)"
        )
        return response


class AuthMiddleware(Middleware):
    """认证中间件"""

    def __init__(self, token_header: str = "Authorization", tokens: Optional[List[str]] = None):
        self.token_header = token_header
        self.tokens = set(tokens or [])
        self._public_paths: List[str] = []

    def add_public_path(self, path: str) -> None:
        """添加公开路径（无需认证）"""
        self._public_paths.append(path)

    def process_request(self, request: Request) -> Request:
        if any(request.path.startswith(p) for p in self._public_paths):
            return request

        token = request.headers.get(self.token_header, "")
        if not token:
            request.context["auth_error"] = "Missing authentication token"
            return request

        if self.tokens and token not in self.tokens:
            request.context["auth_error"] = "Invalid authentication token"
            return request

        request.context["authenticated"] = True
        request.context["token"] = token
        return request

    def process_response(self, request: Request, response: Response) -> Response:
        return response


class RateLimitMiddleware(Middleware):
    """限流中间件"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def process_request(self, request: Request) -> Request:
        client_id = request.headers.get("X-Client-ID", "default")
        now = time.time()

        if client_id not in self._requests:
            self._requests[client_id] = []

        # 清理过期请求记录
        self._requests[client_id] = [
            t for t in self._requests[client_id] if now - t < self.window_seconds
        ]

        if len(self._requests[client_id]) >= self.max_requests:
            request.context["rate_limited"] = True
            request.context["rate_limit_error"] = "Rate limit exceeded"
        else:
            self._requests[client_id].append(now)

        return request

    def process_response(self, request: Request, response: Response) -> Response:
        if request.context.get("rate_limited"):
            response.status_code = 429
            response.error = request.context.get("rate_limit_error", "Rate limit exceeded")
        return response


class ValidationMiddleware(Middleware):
    """参数验证中间件"""

    def __init__(self):
        self._validators: Dict[str, Callable[[Request], Optional[str]]] = {}

    def add_validator(self, path: str, validator: Callable[[Request], Optional[str]]) -> None:
        """为路径添加验证器，返回错误信息或None"""
        self._validators[path] = validator

    def process_request(self, request: Request) -> Request:
        validator = self._validators.get(request.path)
        if validator:
            error = validator(request)
            if error:
                request.context["validation_error"] = error
        return request

    def process_response(self, request: Request, response: Response) -> Response:
        if request.context.get("validation_error"):
            response.status_code = 400
            response.error = request.context["validation_error"]
        return response


class Route:
    """路由定义"""

    def __init__(
        self,
        path: str,
        handler: Callable[[Request], Response],
        methods: Optional[List[HTTPMethod]] = None,
        name: Optional[str] = None,
    ):
        self.path = path
        self.handler = handler
        self.methods = methods or [HTTPMethod.GET]
        self.name = name or handler.__name__
        self._pattern = self._compile_pattern(path)

    def _compile_pattern(self, path: str) -> re.Pattern:
        """将路由路径编译为正则表达式"""
        # 将 /users/{id} 转换为 /users/(?P<id>[^/]+)
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", path)
        return re.compile(f"^{pattern}$")

    def match(self, path: str, method: HTTPMethod) -> Tuple[bool, Dict[str, str]]:
        """匹配路径和方法，返回是否匹配和路径参数"""
        if method not in self.methods:
            return False, {}
        m = self._pattern.match(path)
        if m:
            return True, m.groupdict()
        return False, {}


class Router:
    """路由器"""

    def __init__(self):
        self._routes: List[Route] = []

    def add_route(self, route: Route) -> None:
        """添加路由"""
        self._routes.append(route)
        logger.info(f"注册路由: {route.name} -> {route.path} [{', '.join(m.value for m in route.methods)}]")

    def route(
        self,
        path: str,
        methods: Optional[List[HTTPMethod]] = None,
        name: Optional[str] = None,
    ) -> Callable:
        """路由装饰器"""
        def decorator(handler: Callable[[Request], Response]) -> Callable[[Request], Response]:
            self.add_route(Route(path, handler, methods, name))
            return handler
        return decorator

    def resolve(self, path: str, method: HTTPMethod) -> Tuple[Optional[Route], Dict[str, str]]:
        """解析路径，返回匹配的路由和路径参数"""
        for route in self._routes:
            matched, params = route.match(path, method)
            if matched:
                return route, params
        return None, {}

    def get_routes(self) -> List[Route]:
        """获取所有路由"""
        return self._routes.copy()


class APIGateway:
    """
    API网关

    核心功能：
    - 请求路由分发
    - 中间件链处理
    - 请求验证
    - 响应格式化
    """

    def __init__(self):
        self.router = Router()
        self._middlewares: List[Middleware] = []
        self._error_handlers: Dict[int, Callable[[Request, Exception], Response]] = {}
        self._default_error_handler: Optional[Callable[[Request, Exception], Response]] = None

    def add_middleware(self, middleware: Middleware) -> None:
        """添加中间件"""
        self._middlewares.append(middleware)
        logger.info(f"添加中间件: {middleware.__class__.__name__}")

    def add_error_handler(self, status_code: int, handler: Callable[[Request, Exception], Response]) -> None:
        """添加错误处理器"""
        self._error_handlers[status_code] = handler

    def set_default_error_handler(self, handler: Callable[[Request, Exception], Response]) -> None:
        """设置默认错误处理器"""
        self._default_error_handler = handler

    def route(
        self,
        path: str,
        methods: Optional[List[HTTPMethod]] = None,
        name: Optional[str] = None,
    ) -> Callable:
        """路由装饰器"""
        return self.router.route(path, methods, name)

    def handle(self, request: Request) -> Response:
        """处理请求"""
        start_time = time.time()
        response = Response(request_id=request.request_id)

        try:
            # 中间件请求处理
            for middleware in self._middlewares:
                request = middleware.process_request(request)

            # 检查中间件是否已标记错误
            if request.context.get("auth_error"):
                response.status_code = 401
                response.error = request.context["auth_error"]
            elif request.context.get("rate_limited"):
                response.status_code = 429
                response.error = request.context.get("rate_limit_error", "Rate limit exceeded")
            elif request.context.get("validation_error"):
                response.status_code = 400
                response.error = request.context["validation_error"]
            else:
                # 路由解析
                route, path_params = self.router.resolve(request.path, request.method)
                if route is None:
                    response.status_code = 404
                    response.error = f"Route not found: {request.method.value} {request.path}"
                else:
                    request.context["path_params"] = path_params
                    # 调用处理器
                    response = route.handler(request)
                    if not isinstance(response, Response):
                        response = Response(
                            status_code=200,
                            data=response,
                            request_id=request.request_id,
                        )

        except Exception as e:
            logger.error(f"请求处理异常 [{request.request_id}]: {e}\n{traceback.format_exc()}")
            response.status_code = 500
            response.error = str(e)

            # 查找错误处理器
            handler = self._error_handlers.get(response.status_code) or self._default_error_handler
            if handler:
                response = handler(request, e)

        finally:
            response.processing_time_ms = (time.time() - start_time) * 1000
            response.request_id = request.request_id

            # 中间件响应处理
            for middleware in reversed(self._middlewares):
                response = middleware.process_response(request, response)

        return response

    def get(self, path: str, name: Optional[str] = None) -> Callable:
        """GET路由快捷方式"""
        return self.route(path, [HTTPMethod.GET], name)

    def post(self, path: str, name: Optional[str] = None) -> Callable:
        """POST路由快捷方式"""
        return self.route(path, [HTTPMethod.POST], name)

    def put(self, path: str, name: Optional[str] = None) -> Callable:
        """PUT路由快捷方式"""
        return self.route(path, [HTTPMethod.PUT], name)

    def delete(self, path: str, name: Optional[str] = None) -> Callable:
        """DELETE路由快捷方式"""
        return self.route(path, [HTTPMethod.DELETE], name)

    def get_routes_info(self) -> List[Dict[str, Any]]:
        """获取路由信息"""
        return [
            {
                "name": r.name,
                "path": r.path,
                "methods": [m.value for m in r.methods],
            }
            for r in self.router.get_routes()
        ]


def demo_api_gateway():
    """演示API网关"""
    print("=" * 60)
    print("API网关演示")
    print("=" * 60)
    print()

    gateway = APIGateway()

    # 添加中间件
    gateway.add_middleware(LoggingMiddleware())
    auth = AuthMiddleware(tokens=["valid_token_123"])
    auth.add_public_path("/health")
    gateway.add_middleware(auth)
    gateway.add_middleware(RateLimitMiddleware(max_requests=5, window_seconds=60))

    # 定义处理器
    @gateway.get("/health", name="health_check")
    def health_check(request: Request) -> Response:
        return Response(status_code=200, data={"status": "healthy"})

    @gateway.get("/users", name="list_users")
    def list_users(request: Request) -> Response:
        return Response(status_code=200, data={"users": ["alice", "bob"]})

    @gateway.get("/users/{id}", name="get_user")
    def get_user(request: Request) -> Response:
        user_id = request.context.get("path_params", {}).get("id")
        return Response(status_code=200, data={"id": user_id, "name": f"User-{user_id}"})

    @gateway.post("/users", name="create_user")
    def create_user(request: Request) -> Response:
        return Response(status_code=201, data={"id": "new_id", "created": True})

    # 测试请求
    print("1. 健康检查（公开路径）:")
    req = Request(path="/health", method=HTTPMethod.GET)
    resp = gateway.handle(req)
    print(f"   ✓ {resp.status_code}: {resp.to_dict()}")
    print()

    print("2. 未认证请求:")
    req = Request(path="/users", method=HTTPMethod.GET)
    resp = gateway.handle(req)
    print(f"   ✓ {resp.status_code}: {resp.to_dict()}")
    print()

    print("3. 认证通过请求:")
    req = Request(path="/users", method=HTTPMethod.GET, headers={"Authorization": "valid_token_123"})
    resp = gateway.handle(req)
    print(f"   ✓ {resp.status_code}: {resp.to_dict()}")
    print()

    print("4. 路径参数:")
    req = Request(path="/users/42", method=HTTPMethod.GET, headers={"Authorization": "valid_token_123"})
    resp = gateway.handle(req)
    print(f"   ✓ {resp.status_code}: {resp.to_dict()}")
    print()

    print("5. 路由不存在:")
    req = Request(path="/notfound", method=HTTPMethod.GET, headers={"Authorization": "valid_token_123"})
    resp = gateway.handle(req)
    print(f"   ✓ {resp.status_code}: {resp.to_dict()}")
    print()

    print("6. 路由信息:")
    for info in gateway.get_routes_info():
        print(f"   ✓ {info['name']}: {info['path']} [{', '.join(info['methods'])}]")
    print()

    print("=" * 60)
    print("API网关演示完成")
    print("=" * 60)
    print()
    print("✓ 请求路由")
    print("✓ 请求验证（认证）")
    print("✓ 响应格式化")
    print("✓ 中间件链")
    print()


if __name__ == "__main__":
    demo_api_gateway()
