"""
阶段76验证脚本：服务发现模块
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.service_discovery import (
    CallableHealthChecker,
    RoundRobinBalancer,
    ServiceClient,
    ServiceInstance,
    ServiceNotFoundError,
    ServiceRegistry,
    ServiceStatus,
    WeightedBalancer,
)


def test_service_registration():
    """测试服务注册"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("test-svc", "i1", "127.0.0.1", 8080))
    registry.register(ServiceInstance("test-svc", "i2", "127.0.0.1", 8081))

    instances = registry.discover("test-svc")
    assert len(instances) == 2, f"期望2个实例，实际{len(instances)}"
    print("✓ 服务注册测试通过")


def test_service_deregistration():
    """测试服务注销"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("test-svc", "i1", "127.0.0.1", 8080))
    result = registry.deregister("test-svc", "i1")
    assert result is True
    instances = registry.discover("test-svc")
    assert len(instances) == 0
    print("✓ 服务注销测试通过")


def test_service_discovery():
    """测试服务发现"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("svc-a", "a1", "10.0.0.1", 80))
    registry.register(ServiceInstance("svc-b", "b1", "10.0.0.2", 80))

    a = registry.discover("svc-a")
    b = registry.discover("svc-b")
    c = registry.discover("svc-c")
    assert len(a) == 1
    assert len(b) == 1
    assert len(c) == 0
    print("✓ 服务发现测试通过")


def test_load_balancing():
    """测试负载均衡"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("svc", "i1", "127.0.0.1", 8080))
    registry.register(ServiceInstance("svc", "i2", "127.0.0.1", 8081))
    registry.register(ServiceInstance("svc", "i3", "127.0.0.1", 8082))

    # 轮询
    rr = RoundRobinBalancer()
    selected = [rr.select(registry.discover("svc")) for _ in range(6)]
    ids = [s.instance_id for s in selected if s]
    assert ids == ["i1", "i2", "i3", "i1", "i2", "i3"], f"轮询结果异常: {ids}"

    # 加权
    registry2 = ServiceRegistry()
    registry2.register(ServiceInstance("svc", "w1", "127.0.0.1", 8080, weight=9))
    registry2.register(ServiceInstance("svc", "w2", "127.0.0.1", 8081, weight=1))
    wb = WeightedBalancer()
    counts = {"w1": 0, "w2": 0}
    for _ in range(1000):
        inst = wb.select(registry2.discover("svc"))
        if inst:
            counts[inst.instance_id] += 1
    assert counts["w1"] > counts["w2"], f"加权分布异常: {counts}"
    print("✓ 负载均衡测试通过")


def test_health_check():
    """测试健康检查"""
    registry = ServiceRegistry(heartbeat_timeout=1.0)
    inst = ServiceInstance("svc", "h1", "127.0.0.1", 8080)
    registry.register(inst)

    def checker(instance):
        return ServiceStatus.HEALTHY if instance.instance_id == "h1" else ServiceStatus.UNHEALTHY

    registry.set_health_checker("svc", CallableHealthChecker(checker))
    registry._check_all()
    healthy = registry.discover("svc")
    assert len(healthy) == 1

    # 模拟心跳超时
    time.sleep(1.2)
    registry._check_all()
    healthy = registry.discover("svc")
    assert len(healthy) == 0, "心跳超时后应无可用实例"
    print("✓ 健康检查测试通过")


def test_heartbeat():
    """测试心跳机制"""
    registry = ServiceRegistry(heartbeat_timeout=10.0)
    registry.register(ServiceInstance("svc", "hb1", "127.0.0.1", 8080))
    result = registry.heartbeat("svc", "hb1")
    assert result is True
    result = registry.heartbeat("svc", "nonexist")
    assert result is False
    print("✓ 心跳机制测试通过")


def test_service_client():
    """测试服务客户端"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("api", "c1", "127.0.0.1", 8080))
    client = ServiceClient(registry)

    result = client.call("api", method="GET", path="/users")
    assert result["service"] == "api"
    assert result["status"] == "success"

    try:
        client.call("nonexist")
        assert False, "应抛出异常"
    except ServiceNotFoundError:
        pass
    print("✓ 服务客户端测试通过")


def test_registry_status():
    """测试注册中心状态"""
    registry = ServiceRegistry()
    registry.register(ServiceInstance("s1", "i1", "127.0.0.1", 8080))
    registry.register(ServiceInstance("s2", "i2", "127.0.0.1", 8081))

    status = registry.get_status()
    assert status["service_count"] == 2
    assert status["instance_count"] == 2
    assert "s1" in status["services"]
    assert "s2" in status["services"]
    print("✓ 注册中心状态测试通过")


def main():
    print("=" * 60)
    print("阶段76验证：服务发现模块")
    print("=" * 60)

    test_service_registration()
    test_service_deregistration()
    test_service_discovery()
    test_load_balancing()
    test_health_check()
    test_heartbeat()
    test_service_client()
    test_registry_status()

    print("=" * 60)
    print("阶段76验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
