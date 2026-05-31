#!/usr/bin/env python3
"""
阶段54验证脚本：健康检查系统

测试内容：
1. 组件健康检查
2. 依赖健康检查
3. 健康报告
4. 自动恢复
5. 检查历史
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.health_check import (
    CallableHealthCheck,
    HealthCheckResult,
    HealthCheckSystem,
    HealthStatus,
)


def test_component_health_check() -> bool:
    print("[Test] 组件健康检查")
    try:
        HealthCheckSystem._instance = None
        system = HealthCheckSystem()

        def check_ok():
            return HealthCheckResult("svc_a", HealthStatus.HEALTHY, "正常", 10.0)

        system.register(CallableHealthCheck("svc_a", check_ok))
        result = system.check("svc_a")
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "svc_a"
        print("  ✓ 组件健康检查通过")

        # 未知组件
        unknown = system.check("not_exist")
        assert unknown.status == HealthStatus.UNKNOWN
        print("  ✓ 未知组件返回 UNKNOWN")

        print("[Pass] 组件健康检查\n")
        return True
    except Exception as e:
        print(f"[Fail] 组件健康检查: {e}\n")
        return False


def test_dependency_health_check() -> bool:
    print("[Test] 依赖健康检查")
    try:
        HealthCheckSystem._instance = None
        system = HealthCheckSystem()

        system.register_dependency("redis", lambda: True)
        system.register_dependency("mysql", lambda: False)

        redis_result = system.check("redis")
        assert redis_result.status == HealthStatus.HEALTHY
        print("  ✓ 健康依赖检查通过")

        mysql_result = system.check("mysql")
        assert mysql_result.status == HealthStatus.UNHEALTHY
        print("  ✓ 异常依赖检查通过")

        # 异常抛出的依赖
        system.register_dependency("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        broken_result = system.check("broken")
        assert broken_result.status == HealthStatus.UNHEALTHY
        print("  ✓ 异常抛出依赖检查通过")

        print("[Pass] 依赖健康检查\n")
        return True
    except Exception as e:
        print(f"[Fail] 依赖健康检查: {e}\n")
        return False


def test_health_report() -> bool:
    print("[Test] 健康报告")
    try:
        HealthCheckSystem._instance = None
        system = HealthCheckSystem()

        system.register(CallableHealthCheck("db", lambda: HealthCheckResult("db", HealthStatus.HEALTHY, "ok", 5.0)))
        system.register(CallableHealthCheck("cache", lambda: HealthCheckResult("cache", HealthStatus.DEGRADED, "slow", 200.0)))

        report = system.get_report()
        assert report["overall_status"] == HealthStatus.DEGRADED.value
        assert report["component_count"] == 2
        assert report["status_counts"]["healthy"] == 1
        assert report["status_counts"]["degraded"] == 1
        print(f"  ✓ 健康报告正确: overall={report['overall_status']}")

        print("[Pass] 健康报告\n")
        return True
    except Exception as e:
        print(f"[Fail] 健康报告: {e}\n")
        return False


def test_auto_recovery() -> bool:
    print("[Test] 自动恢复")
    try:
        HealthCheckSystem._instance = None
        system = HealthCheckSystem()

        attempt = 0
        def check_func():
            return HealthCheckResult("unstable", HealthStatus.UNHEALTHY, "不稳定", 50.0)

        def recover():
            nonlocal attempt
            attempt += 1
            return attempt >= 2

        system.register(CallableHealthCheck("unstable", check_func))
        system.register_recovery("unstable", recover, max_attempts=3)

        r1 = system.check("unstable")
        assert r1.metadata.get("recovered") is None
        print(f"  ✓ 第一次检查: {r1.message}")

        r2 = system.check("unstable")
        assert r2.metadata.get("recovered") is True
        assert r2.status == HealthStatus.DEGRADED
        print(f"  ✓ 第二次检查已自动恢复: {r2.message}")

        print("[Pass] 自动恢复\n")
        return True
    except Exception as e:
        print(f"[Fail] 自动恢复: {e}\n")
        return False


def test_check_history() -> bool:
    print("[Test] 检查历史")
    try:
        HealthCheckSystem._instance = None
        system = HealthCheckSystem()

        system.register(CallableHealthCheck("svc", lambda: HealthCheckResult("svc", HealthStatus.HEALTHY, "ok", 1.0)))
        system.check("svc")
        system.check("svc")
        system.check("svc")

        history = system.get_history(limit=2)
        assert len(history) == 2
        print("  ✓ 历史记录限制查询正确")

        history_all = system.get_history(component="svc")
        assert len(history_all) == 3
        print("  ✓ 按组件查询历史正确")

        status = system.get_status()
        assert status["checks_count"] == 1
        assert status["history_count"] == 3
        print(f"  ✓ 系统状态正确: {status}")

        print("[Pass] 检查历史\n")
        return True
    except Exception as e:
        print(f"[Fail] 检查历史: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段54验证脚本：健康检查系统")
    print("=" * 60 + "\n")

    results = []
    results.append(("组件健康检查", test_component_health_check()))
    results.append(("依赖健康检查", test_dependency_health_check()))
    results.append(("健康报告", test_health_report()))
    results.append(("自动恢复", test_auto_recovery()))
    results.append(("检查历史", test_check_history()))

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
        print("🎉 所有测试通过！阶段54验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
