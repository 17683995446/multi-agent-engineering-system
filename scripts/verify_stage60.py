#!/usr/bin/env python3
"""
阶段60验证脚本：系统资源监控

测试内容：
1. 资源采集（回退模式）
2. 资源快照
3. 阈值告警
4. 历史记录
5. 资源报告
6. 后台监控
7. 告警处理器
8. 多线程安全
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.resource_monitor import (
    BaseResourceCollector,
    PSUtilResourceCollector,
    ResourceMonitor,
    ResourceSnapshot,
    ResourceThresholds,
)


def test_collector_fallback() -> bool:
    print("[Test] PSUtilResourceCollector - 资源采集（回退模式）")
    try:
        collector = PSUtilResourceCollector()
        snapshot = collector.collect()

        assert isinstance(snapshot, ResourceSnapshot)
        assert snapshot.memory_total_mb >= 0
        assert snapshot.disk_total_gb >= 0
        print(f"  ✓ CPU: {snapshot.cpu_percent:.1f}%")
        print(f"  ✓ 内存: {snapshot.memory_percent:.1f}% ({snapshot.memory_used_mb:.0f}MB / {snapshot.memory_total_mb:.0f}MB)")
        print(f"  ✓ 磁盘: {snapshot.disk_percent:.1f}% ({snapshot.disk_used_gb:.1f}GB / {snapshot.disk_total_gb:.1f}GB)")

        print("[Pass] ResourceCollector\n")
        return True
    except Exception as e:
        print(f"[Fail] ResourceCollector: {e}\n")
        return False


def test_resource_snapshot() -> bool:
    print("[Test] ResourceSnapshot - 资源快照")
    try:
        snapshot = ResourceSnapshot(
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_used_mb=4096.0,
            memory_total_mb=8192.0,
            disk_percent=70.0,
            disk_used_gb=100.0,
            disk_total_gb=200.0,
        )

        d = snapshot.to_dict()
        assert d["cpu_percent"] == 50.0
        assert d["memory_percent"] == 60.0
        assert d["memory_used_mb"] == 4096.0
        assert d["disk_percent"] == 70.0
        print(f"  ✓ to_dict正确: {d}")

        print("[Pass] ResourceSnapshot\n")
        return True
    except Exception as e:
        print(f"[Fail] ResourceSnapshot: {e}\n")
        return False


def test_alert_check() -> bool:
    print("[Test] 阈值告警检查")
    try:
        thresholds = ResourceThresholds(cpu_percent=50.0, memory_percent=60.0, disk_percent=70.0)
        monitor = ResourceMonitor(thresholds=thresholds)

        # CPU告警
        snapshot = ResourceSnapshot(cpu_percent=55.0, memory_percent=50.0, disk_percent=50.0)
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 1
        assert "CPU" in alerts[0]
        print(f"  ✓ CPU告警: {alerts}")

        # 内存告警
        snapshot = ResourceSnapshot(cpu_percent=40.0, memory_percent=65.0, disk_percent=50.0)
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 1
        assert "内存" in alerts[0]
        print(f"  ✓ 内存告警: {alerts}")

        # 磁盘告警
        snapshot = ResourceSnapshot(cpu_percent=40.0, memory_percent=50.0, disk_percent=75.0)
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 1
        assert "磁盘" in alerts[0]
        print(f"  ✓ 磁盘告警: {alerts}")

        # 多告警
        snapshot = ResourceSnapshot(cpu_percent=55.0, memory_percent=65.0, disk_percent=75.0)
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 3
        print(f"  ✓ 多告警: {alerts}")

        # 无告警
        snapshot = ResourceSnapshot(cpu_percent=40.0, memory_percent=50.0, disk_percent=60.0)
        alerts = monitor.check_alerts(snapshot)
        assert len(alerts) == 0
        print("  ✓ 无告警")

        print("[Pass] Alert Check\n")
        return True
    except Exception as e:
        print(f"[Fail] Alert Check: {e}\n")
        return False


def test_history() -> bool:
    print("[Test] 历史记录")
    try:
        monitor = ResourceMonitor(history_size=5)

        for i in range(3):
            snapshot = ResourceSnapshot(cpu_percent=float(i * 10))
            monitor.collect()
            # 手动替换最后一个为自定义值
            with monitor._lock:
                monitor._history[-1] = snapshot

        history = monitor.get_history()
        assert len(history) == 3
        print(f"  ✓ 历史记录数: {len(history)}")

        latest = monitor.get_latest()
        assert latest is not None
        assert latest.cpu_percent == 20.0
        print(f"  ✓ 最新记录: cpu={latest.cpu_percent}%")

        # 超过容量
        for i in range(5):
            snapshot = ResourceSnapshot(cpu_percent=float(100 + i))
            monitor.collect()
            with monitor._lock:
                monitor._history[-1] = snapshot

        history = monitor.get_history()
        assert len(history) == 5
        print(f"  ✓ 容量限制: {len(history)}")

        print("[Pass] History\n")
        return True
    except Exception as e:
        print(f"[Fail] History: {e}\n")
        return False


def test_report() -> bool:
    print("[Test] 资源使用报告")
    try:
        monitor = ResourceMonitor(history_size=10)

        # 无数据报告
        report = monitor.generate_report()
        assert report["status"] == "no_data"
        print("  ✓ 无数据报告")

        # 有数据报告
        for i in range(5):
            snapshot = ResourceSnapshot(
                cpu_percent=float(i * 10),
                memory_percent=float(50 + i),
                disk_percent=float(60 + i),
            )
            monitor.collect()
            with monitor._lock:
                monitor._history[-1] = snapshot

        report = monitor.generate_report()
        assert report["status"] == "ok"
        assert report["history_count"] == 5
        assert report["cpu"]["current"] == 40.0
        assert report["cpu"]["max"] == 40.0
        assert report["cpu"]["min"] == 0.0
        assert report["cpu"]["avg"] == 20.0
        print(f"  ✓ 报告: {report}")

        print("[Pass] Report\n")
        return True
    except Exception as e:
        print(f"[Fail] Report: {e}\n")
        return False


def test_background_monitoring() -> bool:
    print("[Test] 后台监控")
    try:
        monitor = ResourceMonitor(history_size=10)

        assert not monitor.is_monitoring()
        monitor.start_monitoring(interval=0.2)
        assert monitor.is_monitoring()
        print("  ✓ 监控启动")

        time.sleep(0.7)
        history = monitor.get_history()
        assert len(history) >= 2
        print(f"  ✓ 采集次数: {len(history)}")

        monitor.stop_monitoring()
        assert not monitor.is_monitoring()
        print("  ✓ 监控停止")

        print("[Pass] Background Monitoring\n")
        return True
    except Exception as e:
        print(f"[Fail] Background Monitoring: {e}\n")
        return False


def test_alert_handler() -> bool:
    print("[Test] 告警处理器")
    try:
        monitor = ResourceMonitor(
            thresholds=ResourceThresholds(cpu_percent=0.0),
            history_size=10,
        )

        alerts_received = []

        def handler(alert: str, snapshot: ResourceSnapshot):
            alerts_received.append(alert)

        monitor.add_alert_handler(handler)

        # 触发告警
        snapshot = ResourceSnapshot(cpu_percent=10.0)
        monitor._notify_alerts(monitor.check_alerts(snapshot), snapshot)

        assert len(alerts_received) == 1
        assert "CPU" in alerts_received[0]
        print(f"  ✓ 告警处理器触发: {alerts_received}")

        # 多个处理器
        alerts2 = []
        monitor.add_alert_handler(lambda a, s: alerts2.append(a))
        monitor._notify_alerts(monitor.check_alerts(snapshot), snapshot)
        assert len(alerts2) == 1
        print("  ✓ 多个处理器正常")

        print("[Pass] Alert Handler\n")
        return True
    except Exception as e:
        print(f"[Fail] Alert Handler: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] 线程安全")
    try:
        monitor = ResourceMonitor(history_size=100)
        errors = []

        def worker():
            try:
                for _ in range(20):
                    monitor.collect()
                    monitor.get_latest()
                    monitor.get_history()
                    monitor.generate_report()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        print(f"  ✓ 5线程并发操作无错误")

        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段60验证脚本：系统资源监控")
    print("=" * 60 + "\n")

    results = []
    results.append(("ResourceCollector", test_collector_fallback()))
    results.append(("ResourceSnapshot", test_resource_snapshot()))
    results.append(("Alert Check", test_alert_check()))
    results.append(("History", test_history()))
    results.append(("Report", test_report()))
    results.append(("Background Monitoring", test_background_monitoring()))
    results.append(("Alert Handler", test_alert_handler()))
    results.append(("Thread Safety", test_thread_safety()))

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
        print("🎉 所有测试通过！阶段60验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
