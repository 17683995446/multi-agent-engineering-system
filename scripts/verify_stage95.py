"""
阶段95验证脚本：系统仪表盘模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.dashboard import (
    Alert,
    AlertLevel,
    AlertManager,
    MetricType,
    MetricsCollector,
    ServiceStatus,
    StatusMonitor,
    SystemDashboard,
    SystemMetric,
)


def test_metric_collection():
    """测试指标收集"""
    collector = MetricsCollector()
    collector.register_collector("cpu_usage", lambda: 45.5, MetricType.GAUGE, "%")
    collector.register_collector("memory_usage", lambda: 72.3, MetricType.GAUGE, "%")

    metrics = collector.collect_all()
    assert len(metrics) == 2
    assert metrics[0].value == 45.5
    assert metrics[1].value == 72.3
    print("✓ 指标收集测试通过")


def test_metric_history():
    """测试指标历史"""
    collector = MetricsCollector()
    for i in range(5):
        collector.collect("temp", MetricType.GAUGE, "C", labels={"id": str(i)})

    history = collector.get_history("temp")
    assert len(history) == 5
    print("✓ 指标历史测试通过")


def test_alert_manager_create():
    """测试告警创建"""
    mgr = AlertManager()
    alert = mgr.create_alert(AlertLevel.ERROR, "服务异常", "连接超时", source="api")

    assert alert.alert_id.startswith("ALERT-")
    assert alert.level == AlertLevel.ERROR
    assert alert.resolved is False
    assert len(mgr.get_alerts()) == 1
    print("✓ 告警创建测试通过")


def test_alert_manager_resolve():
    """测试告警解决"""
    mgr = AlertManager()
    alert = mgr.create_alert(AlertLevel.WARNING, "CPU高", "使用率90%")
    success = mgr.resolve_alert(alert.alert_id)

    assert success is True
    assert alert.resolved is True
    assert len(mgr.get_alerts(include_resolved=False)) == 0
    assert len(mgr.get_alerts(include_resolved=True)) == 1
    print("✓ 告警解决测试通过")


def test_alert_rule_check():
    """测试告警规则检查"""
    mgr = AlertManager()
    mgr.add_rule("cpu_usage", lambda v: v > 80, AlertLevel.WARNING, "CPU使用率过高")

    normal_metric = SystemMetric("cpu_usage", 50.0, MetricType.GAUGE)
    triggered = mgr.check_metric(normal_metric)
    assert len(triggered) == 0

    high_metric = SystemMetric("cpu_usage", 90.0, MetricType.GAUGE)
    triggered = mgr.check_metric(high_metric)
    assert len(triggered) == 1
    assert triggered[0].level == AlertLevel.WARNING
    print("✓ 告警规则检查测试通过")


def test_alert_summary():
    """测试告警摘要"""
    mgr = AlertManager()
    mgr.create_alert(AlertLevel.ERROR, "E1", "msg")
    mgr.create_alert(AlertLevel.WARNING, "W1", "msg")
    mgr.create_alert(AlertLevel.CRITICAL, "C1", "msg")

    summary = mgr.get_summary()
    assert summary["total"] == 3
    assert summary["active"] == 3
    assert summary["error"] == 1
    assert summary["warning"] == 1
    assert summary["critical"] == 1
    print("✓ 告警摘要测试通过")


def test_status_monitor():
    """测试状态监控器"""
    monitor = StatusMonitor()
    monitor.register_service("db", lambda: ServiceStatus("db", True, "running", uptime_seconds=3600))
    monitor.register_service("cache", lambda: ServiceStatus("cache", False, "down"))

    services = monitor.check_all()
    assert len(services) == 2
    assert services["db"].healthy is True
    assert services["cache"].healthy is False

    overall = monitor.get_overall_health()
    assert overall["healthy"] is False
    assert overall["total"] == 2
    assert overall["healthy_count"] == 1
    print("✓ 状态监控器测试通过")


def test_dashboard_data():
    """测试仪表盘数据聚合"""
    dash = SystemDashboard()
    dash.metrics_collector.register_collector("m1", lambda: 10.0)
    dash.status_monitor.register_service("svc1", lambda: ServiceStatus("svc1", True, "ok", uptime_seconds=100))
    dash.alert_manager.create_alert(AlertLevel.INFO, "test", "test msg")

    data = dash.get_dashboard_data()
    assert "timestamp" in data
    assert "health" in data
    assert "alerts" in data
    assert "metrics" in data
    assert data["alerts"]["total"] == 1
    print("✓ 仪表盘数据聚合测试通过")


def test_dashboard_render_text():
    """测试文本渲染"""
    dash = SystemDashboard()
    dash.status_monitor.register_service("svc", lambda: ServiceStatus("svc", True, "ok"))
    dash.check_services()

    text = dash.render("text")
    assert "系统仪表盘" in text
    assert "svc" in text
    print("✓ 文本渲染测试通过")


def test_dashboard_render_json():
    """测试JSON渲染"""
    dash = SystemDashboard()
    json_str = dash.render("json")
    assert "timestamp" in json_str
    assert "health" in json_str
    print("✓ JSON渲染测试通过")


def test_dashboard_render_html():
    """测试HTML渲染"""
    dash = SystemDashboard()
    dash.status_monitor.register_service("svc", lambda: ServiceStatus("svc", True, "ok"))
    dash.check_services()

    html = dash.render("html")
    assert "<html>" in html
    assert "svc" in html
    print("✓ HTML渲染测试通过")


def test_dashboard_save():
    """测试仪表盘保存"""
    with tempfile.TemporaryDirectory() as tmpdir:
        dash = SystemDashboard()
        paths = dash.save_dashboard(tmpdir)
        assert paths["text"].exists()
        assert paths["json"].exists()
        assert paths["html"].exists()
    print("✓ 仪表盘保存测试通过")


def test_dashboard_status():
    """测试仪表盘状态"""
    dash = SystemDashboard()
    dash.metrics_collector.register_collector("x", lambda: 1.0)
    dash.collect_metrics()
    dash.status_monitor.register_service("s", lambda: ServiceStatus("s", True, "ok"))
    dash.check_services()

    status = dash.get_status()
    assert status["metrics_count"] == 1
    assert status["services_count"] == 1
    assert status["services_healthy"] == 1
    print("✓ 仪表盘状态测试通过")


def main():
    print("=" * 60)
    print("阶段95验证：系统仪表盘模块")
    print("=" * 60)

    test_metric_collection()
    test_metric_history()
    test_alert_manager_create()
    test_alert_manager_resolve()
    test_alert_rule_check()
    test_alert_summary()
    test_status_monitor()
    test_dashboard_data()
    test_dashboard_render_text()
    test_dashboard_render_json()
    test_dashboard_render_html()
    test_dashboard_save()
    test_dashboard_status()

    print("=" * 60)
    print("阶段95验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
