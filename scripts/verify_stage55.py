#!/usr/bin/env python3
"""
阶段55验证脚本：熔断器模式

测试内容：
1. 熔断器状态流转（CLOSED -> OPEN -> HALF_OPEN -> CLOSED）
2. 失败计数与阈值触发
3. 自动恢复
4. 装饰器支持
5. 熔断器注册表
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
)


def test_state_transition() -> bool:
    print("[Test] 熔断器状态流转")
    try:
        cb = CircuitBreaker("test_state", failure_threshold=2, recovery_timeout=0.3, half_open_max_calls=2)
        assert cb.state == CircuitState.CLOSED
        print("  ✓ 初始状态 CLOSED")

        # 触发 OPEN
        def fail():
            raise RuntimeError("fail")

        for _ in range(2):
            try:
                cb.call(fail)
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN
        print("  ✓ 失败2次后变为 OPEN")

        # 等待超时后变为 HALF_OPEN
        time.sleep(0.35)
        try:
            cb.call(fail)
        except RuntimeError:
            pass
        assert cb.state == CircuitState.OPEN  # HALF_OPEN 探测失败又变回 OPEN
        print("  ✓ HALF_OPEN 探测失败回到 OPEN")

        # 再次等待后成功恢复
        time.sleep(0.35)
        cb.call(lambda: "ok")
        cb.call(lambda: "ok")
        assert cb.state == CircuitState.CLOSED
        print("  ✓ HALF_OPEN 探测成功后恢复 CLOSED")

        print("[Pass] 熔断器状态流转\n")
        return True
    except Exception as e:
        print(f"[Fail] 熔断器状态流转: {e}\n")
        return False


def test_failure_threshold() -> bool:
    print("[Test] 失败计数与阈值触发")
    try:
        cb = CircuitBreaker("test_threshold", failure_threshold=3, recovery_timeout=10.0)

        def fail():
            raise ValueError("err")

        for i in range(2):
            try:
                cb.call(fail)
            except ValueError:
                pass
        assert cb.state == CircuitState.CLOSED  # 还没达到阈值
        print("  ✓ 未达阈值时保持 CLOSED")

        try:
            cb.call(fail)
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        print("  ✓ 达到阈值后变为 OPEN")

        # OPEN 状态下请求被拒绝
        try:
            cb.call(lambda: "ok")
            assert False, "应该抛出 CircuitBreakerOpen"
        except CircuitBreakerOpen:
            print("  ✓ OPEN 状态下请求被拒绝")

        print("[Pass] 失败计数与阈值触发\n")
        return True
    except Exception as e:
        print(f"[Fail] 失败计数与阈值触发: {e}\n")
        return False


def test_auto_recovery() -> bool:
    print("[Test] 自动恢复")
    try:
        cb = CircuitBreaker("test_recovery", failure_threshold=1, recovery_timeout=0.2, half_open_max_calls=1)

        def fail():
            raise RuntimeError("fail")

        try:
            cb.call(fail)
        except RuntimeError:
            pass
        assert cb.state == CircuitState.OPEN
        print("  ✓ 熔断器打开")

        time.sleep(0.25)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
        print("  ✓ 超时后自动恢复为 CLOSED")

        print("[Pass] 自动恢复\n")
        return True
    except Exception as e:
        print(f"[Fail] 自动恢复: {e}\n")
        return False


def test_decorator() -> bool:
    print("[Test] 熔断器装饰器")
    try:
        # 重置注册表单例，避免与其他测试共享状态
        CircuitBreakerRegistry._instance = None
        call_count = 0

        @circuit_breaker(name="test_decorator", failure_threshold=2, recovery_timeout=10.0)
        def decorated(should_fail: bool = False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise RuntimeError("fail")
            return "success"

        try:
            decorated(should_fail=True)
        except RuntimeError:
            pass
        try:
            decorated(should_fail=True)
        except RuntimeError:
            pass

        try:
            decorated()
            assert False, "应该抛出 CircuitBreakerOpen"
        except CircuitBreakerOpen:
            print("  ✓ 装饰器熔断生效")

        # 正常调用不应被熔断影响（使用新注册表）
        CircuitBreakerRegistry._instance = None
        @circuit_breaker(name="test_decorator2", failure_threshold=5)
        def normal():
            return "ok"

        assert normal() == "ok"
        print("  ✓ 正常调用不受影响")

        print("[Pass] 熔断器装饰器\n")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Fail] 熔断器装饰器: {e}\n")
        return False


def test_registry() -> bool:
    print("[Test] 熔断器注册表")
    try:
        CircuitBreakerRegistry._instance = None
        registry = CircuitBreakerRegistry()

        cb1 = registry.get_or_create("svc1", failure_threshold=3)
        cb2 = registry.get_or_create("svc2", failure_threshold=5)
        cb1_again = registry.get_or_create("svc1")

        assert cb1 is cb1_again
        print("  ✓ 单例注册表返回同一实例")

        assert registry.get("svc1") is cb1
        assert registry.get("not_exist") is None
        print("  ✓ 注册表查询正确")

        metrics = registry.get_all_metrics()
        assert "svc1" in metrics
        assert "svc2" in metrics
        print("  ✓ 注册表指标汇总正确")

        registry.remove("svc1")
        assert registry.get("svc1") is None
        print("  ✓ 注册表移除正确")

        print("[Pass] 熔断器注册表\n")
        return True
    except Exception as e:
        print(f"[Fail] 熔断器注册表: {e}\n")
        return False


def test_metrics() -> bool:
    print("[Test] 熔断器指标")
    try:
        cb = CircuitBreaker("test_metrics", failure_threshold=2, recovery_timeout=10.0)

        def fail():
            raise RuntimeError("fail")

        for _ in range(2):
            try:
                cb.call(fail)
            except RuntimeError:
                pass

        try:
            cb.call(lambda: "ok")
        except CircuitBreakerOpen:
            pass

        metrics = cb.get_metrics()
        assert metrics["name"] == "test_metrics"
        assert metrics["state"] == "open"
        assert metrics["metrics"]["failure_calls"] == 2
        assert metrics["metrics"]["rejected_calls"] == 1
        assert len(metrics["metrics"]["state_changes"]) == 1
        print(f"  ✓ 指标正确: failure={metrics['metrics']['failure_calls']}, rejected={metrics['metrics']['rejected_calls']}")

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        print("  ✓ 手动重置后恢复 CLOSED")

        print("[Pass] 熔断器指标\n")
        return True
    except Exception as e:
        print(f"[Fail] 熔断器指标: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段55验证脚本：熔断器模式")
    print("=" * 60 + "\n")

    results = []
    results.append(("熔断器状态流转", test_state_transition()))
    results.append(("失败计数与阈值触发", test_failure_threshold()))
    results.append(("自动恢复", test_auto_recovery()))
    results.append(("熔断器装饰器", test_decorator()))
    results.append(("熔断器注册表", test_registry()))
    results.append(("熔断器指标", test_metrics()))

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
        print("🎉 所有测试通过！阶段55验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
