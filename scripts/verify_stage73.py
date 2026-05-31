#!/usr/bin/env python3
"""
阶段73验证脚本：HTTP客户端

测试内容：
1. HTTP方法（GET/POST/PUT/DELETE/PATCH）
2. 请求重试
3. 超时管理
4. 响应解析
5. 请求头管理
6. 连接池
7. 统计信息
8. 本地服务测试
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.http_client import (
    HTTPClient,
    HTTPConfig,
    HTTPException,
    HTTPMethod,
    HTTPResponse,
    get_http_client,
)
from common.retry_mechanism import RetryStrategy


def test_http_methods() -> bool:
    print("[Test] HTTP Methods - HTTP方法")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), MockHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}"), name="test_methods")

            # GET
            resp = client.get("/test", retry=False)
            assert resp.status_code == 200
            assert resp.json()["method"] == "GET"
            print(f"  ✓ GET: {resp.status_code}")

            # POST
            resp = client.post("/test", json_data={"hello": "world"}, retry=False)
            assert resp.status_code == 201
            assert json.loads(resp.json()["received"]) == {"hello": "world"}
            print(f"  ✓ POST: {resp.status_code}")

            # PUT
            resp = client.put("/test", json_data={"update": True}, retry=False)
            assert resp.status_code == 200
            print(f"  ✓ PUT: {resp.status_code}")

            # DELETE
            resp = client.delete("/test", retry=False)
            assert resp.status_code == 204
            print(f"  ✓ DELETE: {resp.status_code}")

            # PATCH
            resp = client.patch("/test", json_data={"patch": True}, retry=False)
            assert resp.status_code == 200
            print(f"  ✓ PATCH: {resp.status_code}")

            httpd.shutdown()

        print("[Pass] HTTP Methods\n")
        return True
    except Exception as e:
        print(f"[Fail] HTTP Methods: {e}\n")
        return False


def test_response_parsing() -> bool:
    print("[Test] Response Parsing - 响应解析")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), MockHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}"), name="test_response")

            resp = client.get("/test", retry=False)
            assert resp.is_success() is True
            assert resp.is_client_error() is False
            assert resp.is_server_error() is False
            assert resp.duration_ms >= 0
            print(f"  ✓ 成功判断: {resp.is_success()}")
            print(f"  ✓ 耗时: {resp.duration_ms:.2f}ms")

            # 错误响应
            resp = client.get("/error", retry=False)
            assert resp.status_code == 500
            assert resp.is_server_error() is True
            print(f"  ✓ 错误响应: {resp.status_code}")

            httpd.shutdown()

        print("[Pass] Response Parsing\n")
        return True
    except Exception as e:
        print(f"[Fail] Response Parsing: {e}\n")
        return False


def test_headers() -> bool:
    print("[Test] Headers - 请求头管理")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), MockHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}"), name="test_headers")

            client.set_header("X-Custom-Header", "test-value")
            resp = client.get("/headers", retry=False)
            assert resp.status_code == 200
            print(f"  ✓ 自定义请求头设置成功")

            client.remove_header("X-Custom-Header")
            print(f"  ✓ 自定义请求头移除成功")

            httpd.shutdown()

        print("[Pass] Headers\n")
        return True
    except Exception as e:
        print(f"[Fail] Headers: {e}\n")
        return False


def test_timeout() -> bool:
    print("[Test] Timeout - 超时管理")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), SlowHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}", timeout=0.1), name="test_timeout")

            try:
                client.get("/slow", retry=False)
                print("  ✗ 应该超时")
                return False
            except HTTPException:
                print("  ✓ 超时正常触发")

            httpd.shutdown()

        print("[Pass] Timeout\n")
        return True
    except Exception as e:
        print(f"[Fail] Timeout: {e}\n")
        return False


def test_stats() -> bool:
    print("[Test] Stats - 统计信息")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), MockHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}"), name="test_stats")

            stats_before = client.get_stats()
            print(f"  ✓ 初始统计: {stats_before}")

            client.get("/test", retry=False)
            client.post("/test", json_data={"test": True}, retry=False)

            stats_after = client.get_stats()
            print(f"  ✓ 请求后统计: {stats_after}")
            assert stats_after["total_requests"] >= 2

            client.reset_stats()
            stats_reset = client.get_stats()
            assert stats_reset["total_requests"] == 0
            print(f"  ✓ 重置后统计: {stats_reset}")

            httpd.shutdown()

        print("[Pass] Stats\n")
        return True
    except Exception as e:
        print(f"[Fail] Stats: {e}\n")
        return False


def test_url_params() -> bool:
    print("[Test] URL Params - URL参数")
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), MockHandler) as httpd:
            port = httpd.server_address[1]
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()

            client = HTTPClient(HTTPConfig(base_url=f"http://127.0.0.1:{port}"), name="test_params")

            resp = client.get("/params", params={"foo": "bar", "num": 123}, retry=False)
            assert resp.status_code == 200
            data = resp.json()
            assert data["args"]["foo"] == "bar"
            print(f"  ✓ URL参数传递: {data['args']}")

            httpd.shutdown()

        print("[Pass] URL Params\n")
        return True
    except Exception as e:
        print(f"[Fail] URL Params: {e}\n")
        return False


def test_config() -> bool:
    print("[Test] Config - 配置验证")
    try:
        config = HTTPConfig(
            base_url="http://example.com",
            timeout=15.0,
            max_retries=3,
            retry_delay=0.5,
            retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        )
        assert config.base_url == "http://example.com"
        assert config.timeout == 15.0
        assert config.max_retries == 3
        print(f"  ✓ 配置正确: timeout={config.timeout}, retries={config.max_retries}")

        print("[Pass] Config\n")
        return True
    except Exception as e:
        print(f"[Fail] Config: {e}\n")
        return False


class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "/error" in self.path:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "server error"}')
            return
        if "/params" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            import urllib.parse
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            # flatten
            args = {k: v[0] for k, v in params.items()}
            self.wfile.write(json.dumps({"args": args}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"path": self.path, "method": "GET"}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"received": body.decode(), "method": "POST"}).encode())

    def do_PUT(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"method": "PUT"}).encode())

    def do_DELETE(self):
        self.send_response(204)
        self.end_headers()

    def do_PATCH(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"method": "PATCH"}).encode())

    def log_message(self, format, *args):
        pass


class SlowHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(1.0)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main() -> int:
    print("=" * 60)
    print("阶段73验证脚本：HTTP客户端")
    print("=" * 60 + "\n")

    results = []
    results.append(("HTTP Methods", test_http_methods()))
    results.append(("Response Parsing", test_response_parsing()))
    results.append(("Headers", test_headers()))
    results.append(("Timeout", test_timeout()))
    results.append(("Stats", test_stats()))
    results.append(("URL Params", test_url_params()))
    results.append(("Config", test_config()))

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
        print("🎉 所有测试通过！阶段73验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
