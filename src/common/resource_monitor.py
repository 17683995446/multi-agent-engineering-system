"""
公共层 - 系统资源监控模块
职责：提供CPU/内存/磁盘监控、资源阈值告警、资源使用报告
依赖规则：仅依赖公共层 utils
"""

from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from common.utils import setup_logger


class ResourceAlert(Exception):
    """资源告警异常"""
    pass


@dataclass
class ResourceThresholds:
    """资源阈值配置"""
    cpu_percent: float = 80.0
    memory_percent: float = 85.0
    disk_percent: float = 90.0


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: float = field(default_factory=time.monotonic)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "memory_total_mb": round(self.memory_total_mb, 2),
            "disk_percent": round(self.disk_percent, 2),
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
        }


class BaseResourceCollector(ABC):
    """资源采集器抽象基类"""

    @abstractmethod
    def collect(self) -> ResourceSnapshot:
        """采集资源信息"""


class PSUtilResourceCollector(BaseResourceCollector):
    """
    基于psutil的资源采集器

    如果psutil不可用，则回退到基础实现
    """

    def __init__(self):
        self._has_psutil = False
        self._psutil = None
        try:
            import psutil
            self._has_psutil = True
            self._psutil = psutil
        except ImportError:
            pass

    def collect(self) -> ResourceSnapshot:
        if self._has_psutil and self._psutil:
            return self._collect_with_psutil()
        return self._collect_fallback()

    def _collect_with_psutil(self) -> ResourceSnapshot:
        psutil = self._psutil
        snapshot = ResourceSnapshot()

        # CPU
        snapshot.cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory
        mem = psutil.virtual_memory()
        snapshot.memory_percent = mem.percent
        snapshot.memory_used_mb = mem.used / (1024 * 1024)
        snapshot.memory_total_mb = mem.total / (1024 * 1024)

        # Disk
        disk = psutil.disk_usage("/")
        snapshot.disk_percent = (disk.used / disk.total) * 100
        snapshot.disk_used_gb = disk.used / (1024 * 1024 * 1024)
        snapshot.disk_total_gb = disk.total / (1024 * 1024 * 1024)

        return snapshot

    def _collect_fallback(self) -> ResourceSnapshot:
        """无psutil时的回退采集"""
        snapshot = ResourceSnapshot()

        # CPU - 通过/proc/stat估算
        try:
            snapshot.cpu_percent = self._read_cpu_stat()
        except Exception:
            snapshot.cpu_percent = 0.0

        # Memory - 通过/proc/meminfo
        try:
            mem_info = self._read_meminfo()
            snapshot.memory_total_mb = mem_info.get("MemTotal", 0) / 1024
            snapshot.memory_used_mb = snapshot.memory_total_mb - mem_info.get("MemAvailable", 0) / 1024
            if snapshot.memory_total_mb > 0:
                snapshot.memory_percent = (snapshot.memory_used_mb / snapshot.memory_total_mb) * 100
        except Exception:
            pass

        # Disk - 通过df命令或os.statvfs
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            snapshot.disk_total_gb = total / (1024 * 1024 * 1024)
            snapshot.disk_used_gb = used / (1024 * 1024 * 1024)
            if total > 0:
                snapshot.disk_percent = (used / total) * 100
        except Exception:
            pass

        return snapshot

    def _read_cpu_stat(self) -> float:
        """读取/proc/stat计算CPU使用率"""
        with open("/proc/stat", "r") as f:
            line = f.readline()
        fields = line.split()
        if fields[0] != "cpu":
            return 0.0
        values = [int(x) for x in fields[1:]]
        total = sum(values)
        idle = values[3]
        return ((total - idle) / total) * 100 if total > 0 else 0.0

    def _read_meminfo(self) -> dict[str, int]:
        """读取/proc/meminfo"""
        info = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = int(parts[1].strip().split()[0]) * 1024  # kB to bytes
                        info[key] = value
        except Exception:
            pass
        return info


class ResourceMonitor:
    """
    系统资源监控器

    提供：
    - 实时资源采集
    - 阈值告警
    - 历史记录
    - 定时报告
    """

    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        collector: Optional[BaseResourceCollector] = None,
        history_size: int = 100,
        name: str = "resource_monitor",
    ):
        self.thresholds = thresholds or ResourceThresholds()
        self.collector = collector or PSUtilResourceCollector()
        self.history_size = history_size
        self.name = name
        self.logger = setup_logger(f"common.resource_monitor.{name}")
        self._history: list[ResourceSnapshot] = []
        self._lock = threading.Lock()
        self._alert_handlers: list[Callable[[str, ResourceSnapshot], None]] = []
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._interval = 5.0

    def collect(self) -> ResourceSnapshot:
        """采集当前资源信息"""
        snapshot = self.collector.collect()
        with self._lock:
            self._history.append(snapshot)
            if len(self._history) > self.history_size:
                self._history.pop(0)
        return snapshot

    def get_latest(self) -> Optional[ResourceSnapshot]:
        """获取最新资源快照"""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_history(self) -> list[ResourceSnapshot]:
        """获取历史记录"""
        with self._lock:
            return self._history.copy()

    def check_alerts(self, snapshot: ResourceSnapshot) -> list[str]:
        """检查是否触发告警"""
        alerts = []
        if snapshot.cpu_percent > self.thresholds.cpu_percent:
            alerts.append(f"CPU使用率过高: {snapshot.cpu_percent:.1f}%")
        if snapshot.memory_percent > self.thresholds.memory_percent:
            alerts.append(f"内存使用率过高: {snapshot.memory_percent:.1f}%")
        if snapshot.disk_percent > self.thresholds.disk_percent:
            alerts.append(f"磁盘使用率过高: {snapshot.disk_percent:.1f}%")
        return alerts

    def add_alert_handler(self, handler: Callable[[str, ResourceSnapshot], None]) -> None:
        """添加告警处理器"""
        self._alert_handlers.append(handler)

    def _notify_alerts(self, alerts: list[str], snapshot: ResourceSnapshot) -> None:
        """通知告警"""
        for alert in alerts:
            self.logger.warning(alert)
            for handler in self._alert_handlers:
                try:
                    handler(alert, snapshot)
                except Exception as e:
                    self.logger.error(f"告警处理器错误: {e}")

    def generate_report(self) -> dict[str, Any]:
        """生成资源使用报告"""
        with self._lock:
            if not self._history:
                return {"status": "no_data"}

            latest = self._history[-1]
            cpu_values = [s.cpu_percent for s in self._history]
            mem_values = [s.memory_percent for s in self._history]
            disk_values = [s.disk_percent for s in self._history]

            return {
                "status": "ok",
                "latest": latest.to_dict(),
                "cpu": {
                    "current": round(latest.cpu_percent, 2),
                    "avg": round(sum(cpu_values) / len(cpu_values), 2),
                    "max": round(max(cpu_values), 2),
                    "min": round(min(cpu_values), 2),
                },
                "memory": {
                    "current_percent": round(latest.memory_percent, 2),
                    "current_used_mb": round(latest.memory_used_mb, 2),
                    "total_mb": round(latest.memory_total_mb, 2),
                    "avg_percent": round(sum(mem_values) / len(mem_values), 2),
                },
                "disk": {
                    "current_percent": round(latest.disk_percent, 2),
                    "current_used_gb": round(latest.disk_used_gb, 2),
                    "total_gb": round(latest.disk_total_gb, 2),
                },
                "history_count": len(self._history),
                "thresholds": {
                    "cpu": self.thresholds.cpu_percent,
                    "memory": self.thresholds.memory_percent,
                    "disk": self.thresholds.disk_percent,
                },
            }

    def start_monitoring(self, interval: float = 5.0) -> None:
        """启动后台监控线程"""
        if self._running:
            return

        self._interval = interval
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info(f"资源监控已启动，采集间隔: {interval}s")

    def stop_monitoring(self) -> None:
        """停止后台监控线程"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=self._interval + 1)
        self.logger.info("资源监控已停止")

    def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                snapshot = self.collect()
                alerts = self.check_alerts(snapshot)
                if alerts:
                    self._notify_alerts(alerts, snapshot)
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")

            # 使用短间隔检查停止标志
            waited = 0.0
            while waited < self._interval and self._running:
                time.sleep(0.1)
                waited += 0.1

    def is_monitoring(self) -> bool:
        """检查是否正在监控"""
        return self._running


def demo_resource_monitor():
    """演示资源监控"""
    print("=" * 60)
    print("系统资源监控模块验证")
    print("=" * 60)
    print()

    monitor = ResourceMonitor(
        thresholds=ResourceThresholds(cpu_percent=50.0, memory_percent=80.0, disk_percent=95.0),
        history_size=10,
    )

    # 1. 手动采集
    print("1. 手动采集资源信息:")
    snapshot = monitor.collect()
    print(f"   CPU: {snapshot.cpu_percent:.1f}%")
    print(f"   内存: {snapshot.memory_percent:.1f}% ({snapshot.memory_used_mb:.0f}MB / {snapshot.memory_total_mb:.0f}MB)")
    print(f"   磁盘: {snapshot.disk_percent:.1f}% ({snapshot.disk_used_gb:.1f}GB / {snapshot.disk_total_gb:.1f}GB)")
    print()

    # 2. 告警检查
    print("2. 告警检查:")
    alerts = monitor.check_alerts(snapshot)
    if alerts:
        for alert in alerts:
            print(f"   ⚠️ {alert}")
    else:
        print("   ✓ 所有资源正常")
    print()

    # 3. 生成报告
    print("3. 资源使用报告:")
    report = monitor.generate_report()
    print(f"   历史记录数: {report['history_count']}")
    print(f"   CPU当前: {report['cpu']['current']}%")
    print(f"   内存当前: {report['memory']['current_percent']}%")
    print(f"   磁盘当前: {report['disk']['current_percent']}%")
    print()

    # 4. 后台监控
    print("4. 后台监控（3秒）:")
    alert_received = []

    def on_alert(alert: str, snapshot: ResourceSnapshot):
        alert_received.append(alert)

    monitor.add_alert_handler(on_alert)
    monitor.start_monitoring(interval=1.0)
    time.sleep(3)
    monitor.stop_monitoring()
    print(f"   采集次数: {len(monitor.get_history())}")
    print(f"   告警次数: {len(alert_received)}")
    print()

    print("=" * 60)
    print("系统资源监控模块验证成功")
    print("=" * 60)


if __name__ == "__main__":
    demo_resource_monitor()
