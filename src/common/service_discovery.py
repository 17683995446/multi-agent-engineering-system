"""
服务发现模块
遵循第一性原理：服务注册与发现机制

核心功能：
1. 服务注册
2. 服务发现
3. 健康检查
4. 负载均衡
"""

from __future__ import annotations

import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from common.utils import setup_logger

logger = setup_logger(__name__)


class ServiceStatus(Enum):
    """服务状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    """服务实例"""
    service_name: str
    instance_id: str
    host: str
    port: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.HEALTHY
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    weight: int = 1

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "host": self.host,
            "port": self.port,
            "address": self.address,
            "metadata": self.metadata,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "weight": self.weight,
        }


class LoadBalancer(ABC):
    """负载均衡器基类"""

    @abstractmethod
    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        """选择一个服务实例"""
        pass


class RoundRobinBalancer(LoadBalancer):
    """轮询负载均衡"""

    def __init__(self):
        self._index = 0
        self._lock = threading.Lock()

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        if not instances:
            return None
        with self._lock:
            instance = instances[self._index % len(instances)]
            self._index += 1
            return instance


class RandomBalancer(LoadBalancer):
    """随机负载均衡"""

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        if not instances:
            return None
        return random.choice(instances)


class WeightedBalancer(LoadBalancer):
    """加权负载均衡"""

    def select(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        if not instances:
            return None
        weights = [i.weight for i in instances]
        total = sum(weights)
        if total == 0:
            return random.choice(instances)
        r = random.uniform(0, total)
        cumulative = 0
        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance
        return instances[-1]


class HealthChecker(ABC):
    """健康检查器基类"""

    @abstractmethod
    def check(self, instance: ServiceInstance) -> ServiceStatus:
        """检查服务实例健康状态"""
        pass


class CallableHealthChecker(HealthChecker):
    """基于可调用对象的健康检查器"""

    def __init__(self, check_func: Callable[[ServiceInstance], ServiceStatus]):
        self.check_func = check_func

    def check(self, instance: ServiceInstance) -> ServiceStatus:
        return self.check_func(instance)


class ServiceRegistry:
    """
    服务注册中心

    核心功能：
    - 服务注册
    - 服务注销
    - 服务发现
    - 健康检查
    - 负载均衡
    """

    def __init__(self, heartbeat_timeout: float = 30.0):
        self._services: Dict[str, Dict[str, ServiceInstance]] = {}
        self._balancers: Dict[str, LoadBalancer] = {}
        self._health_checkers: Dict[str, HealthChecker] = {}
        self._heartbeat_timeout = heartbeat_timeout
        self._lock = threading.RLock()
        self._running = False
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def register(self, instance: ServiceInstance) -> None:
        """注册服务实例"""
        with self._lock:
            if instance.service_name not in self._services:
                self._services[instance.service_name] = {}
            self._services[instance.service_name][instance.instance_id] = instance
        logger.info(f"服务注册: {instance.service_name} / {instance.instance_id} @ {instance.address}")

    def deregister(self, service_name: str, instance_id: str) -> bool:
        """注销服务实例"""
        with self._lock:
            service = self._services.get(service_name)
            if service and instance_id in service:
                del service[instance_id]
                if not service:
                    del self._services[service_name]
                logger.info(f"服务注销: {service_name} / {instance_id}")
                return True
        return False

    def heartbeat(self, service_name: str, instance_id: str) -> bool:
        """服务心跳上报"""
        with self._lock:
            instance = self._services.get(service_name, {}).get(instance_id)
            if instance:
                instance.last_heartbeat = datetime.now()
                if instance.status == ServiceStatus.UNHEALTHY:
                    instance.status = ServiceStatus.HEALTHY
                return True
        return False

    def discover(self, service_name: str) -> List[ServiceInstance]:
        """发现服务实例列表"""
        with self._lock:
            instances = list(self._services.get(service_name, {}).values())
            return [i for i in instances if i.status != ServiceStatus.UNHEALTHY]

    def discover_one(self, service_name: str, balancer: Optional[LoadBalancer] = None) -> Optional[ServiceInstance]:
        """发现一个服务实例（使用负载均衡）"""
        instances = self.discover(service_name)
        if not instances:
            return None
        if balancer is None:
            balancer = self._balancers.get(service_name)
        if balancer is None:
            balancer = RoundRobinBalancer()
        return balancer.select(instances)

    def set_balancer(self, service_name: str, balancer: LoadBalancer) -> None:
        """设置服务的负载均衡器"""
        with self._lock:
            self._balancers[service_name] = balancer

    def set_health_checker(self, service_name: str, checker: HealthChecker) -> None:
        """设置服务的健康检查器"""
        with self._lock:
            self._health_checkers[service_name] = checker

    def get_all_services(self) -> Dict[str, List[ServiceInstance]]:
        """获取所有服务"""
        with self._lock:
            return {
                name: list(instances.values())
                for name, instances in self._services.items()
            }

    def get_service(self, service_name: str) -> Optional[Dict[str, ServiceInstance]]:
        """获取指定服务的所有实例"""
        with self._lock:
            instances = self._services.get(service_name)
            return instances.copy() if instances else None

    def start_health_check(self, interval: float = 10.0) -> None:
        """启动健康检查线程"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._health_check_thread = threading.Thread(target=self._health_check_loop, args=(interval,), daemon=True)
        self._health_check_thread.start()
        logger.info(f"健康检查线程已启动，间隔 {interval}s")

    def stop_health_check(self) -> None:
        """停止健康检查线程"""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5.0)
        logger.info("健康检查线程已停止")

    def _health_check_loop(self, interval: float) -> None:
        """健康检查循环"""
        while not self._stop_event.is_set():
            self._check_all()
            self._stop_event.wait(interval)

    def _check_all(self) -> None:
        """检查所有服务实例"""
        with self._lock:
            services_snapshot = {
                name: list(instances.values())
                for name, instances in self._services.items()
            }
            checkers = self._health_checkers.copy()

        now = datetime.now()
        timeout_delta = timedelta(seconds=self._heartbeat_timeout)

        for service_name, instances in services_snapshot.items():
            checker = checkers.get(service_name)
            for instance in instances:
                # 心跳超时检查
                if now - instance.last_heartbeat > timeout_delta:
                    instance.status = ServiceStatus.UNHEALTHY
                    logger.warning(f"心跳超时: {service_name} / {instance.instance_id}")
                    continue
                # 自定义健康检查
                if checker:
                    try:
                        status = checker.check(instance)
                        instance.status = status
                        if status != ServiceStatus.HEALTHY:
                            logger.warning(f"健康检查异常: {service_name} / {instance.instance_id} -> {status.value}")
                    except Exception as e:
                        logger.error(f"健康检查异常: {service_name} / {instance.instance_id} - {e}")
                        instance.status = ServiceStatus.UNHEALTHY

    def get_status(self) -> Dict[str, Any]:
        """获取注册中心状态"""
        with self._lock:
            total_instances = sum(len(instances) for instances in self._services.values())
            return {
                "service_count": len(self._services),
                "instance_count": total_instances,
                "services": list(self._services.keys()),
                "health_check_running": self._running,
                "heartbeat_timeout": self._heartbeat_timeout,
            }


class ServiceClient:
    """
    服务客户端

    封装服务发现与调用
    """

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry

    def call(self, service_name: str, method: str = "GET", path: str = "/", **kwargs) -> Dict[str, Any]:
        """调用服务（模拟）"""
        instance = self.registry.discover_one(service_name)
        if not instance:
            raise ServiceNotFoundError(f"未找到可用服务实例: {service_name}")
        return {
            "service": service_name,
            "instance": instance.instance_id,
            "address": instance.address,
            "method": method,
            "path": path,
            "status": "success",
        }

    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """获取服务实例列表"""
        return self.registry.discover(service_name)


class ServiceNotFoundError(Exception):
    """服务未找到异常"""
    pass


def demo_service_discovery():
    """演示服务发现系统"""
    print("=" * 60)
    print("服务发现系统演示")
    print("=" * 60)
    print()

    registry = ServiceRegistry(heartbeat_timeout=30.0)

    print("1. 服务注册:")
    registry.register(ServiceInstance("user-service", "u1", "192.168.1.10", 8080, weight=3))
    registry.register(ServiceInstance("user-service", "u2", "192.168.1.11", 8080, weight=2))
    registry.register(ServiceInstance("order-service", "o1", "192.168.1.20", 9090))
    print("   ✓ user-service 注册 2 个实例")
    print("   ✓ order-service 注册 1 个实例")
    print()

    print("2. 服务发现:")
    user_instances = registry.discover("user-service")
    print(f"   ✓ user-service 发现 {len(user_instances)} 个可用实例")
    order_instances = registry.discover("order-service")
    print(f"   ✓ order-service 发现 {len(order_instances)} 个可用实例")
    print()

    print("3. 负载均衡:")
    registry.set_balancer("user-service", RoundRobinBalancer())
    selections = [registry.discover_one("user-service") for _ in range(4)]
    print(f"   ✓ 轮询选择: {[s.instance_id for s in selections if s]}")

    registry.set_balancer("user-service", WeightedBalancer())
    weighted_counts: Dict[str, int] = {}
    for _ in range(1000):
        inst = registry.discover_one("user-service")
        if inst:
            weighted_counts[inst.instance_id] = weighted_counts.get(inst.instance_id, 0) + 1
    print(f"   ✓ 加权选择分布: {weighted_counts}")
    print()

    print("4. 健康检查:")
    def check_user(instance: ServiceInstance) -> ServiceStatus:
        if instance.instance_id == "u1":
            return ServiceStatus.HEALTHY
        return ServiceStatus.UNHEALTHY

    registry.set_health_checker("user-service", CallableHealthChecker(check_user))
    registry.start_health_check(interval=2.0)
    time.sleep(0.5)
    registry._check_all()
    healthy = registry.discover("user-service")
    print(f"   ✓ 健康检查后可用实例: {len(healthy)}")
    registry.stop_health_check()
    print()

    print("5. 心跳机制:")
    registry.heartbeat("user-service", "u1")
    registry.heartbeat("order-service", "o1")
    print("   ✓ 心跳上报成功")
    print()

    print("6. 服务注销:")
    registry.deregister("order-service", "o1")
    remaining = registry.discover("order-service")
    print(f"   ✓ order-service 注销后剩余实例: {len(remaining)}")
    print()

    print("7. 注册中心状态:")
    status = registry.get_status()
    print(f"   ✓ 服务数: {status['service_count']}")
    print(f"   ✓ 实例数: {status['instance_count']}")
    print()

    print("=" * 60)
    print("服务发现系统演示完成")
    print("=" * 60)
    print()
    print("✓ 服务注册")
    print("✓ 服务发现")
    print("✓ 健康检查")
    print("✓ 负载均衡")
    print()


if __name__ == "__main__":
    demo_service_discovery()
