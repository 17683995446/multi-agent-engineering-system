"""
系统仪表盘模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 系统状态展示
2. 指标可视化
3. 告警展示
4. 操作面板
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class SystemMetric:
    """系统指标"""
    name: str
    value: float
    metric_type: MetricType
    unit: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "unit": self.unit,
            "labels": self.labels,
            "timestamp": self.timestamp,
        }


@dataclass
class Alert:
    """告警记录"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    source: str = ""
    timestamp: str = ""
    resolved: bool = False
    resolved_at: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def resolve(self):
        """标记告警已解决"""
        self.resolved = True
        self.resolved_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


@dataclass
class ServiceStatus:
    """服务状态"""
    name: str
    healthy: bool
    status: str
    uptime_seconds: float = 0.0
    last_check: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.last_check:
            self.last_check = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "last_check": self.last_check,
            "details": self.details,
        }


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self.metrics: List[SystemMetric] = []
        self.collectors: Dict[str, Callable[[], float]] = {}

    def register_collector(self, name: str, collector: Callable[[], float],
                           metric_type: MetricType = MetricType.GAUGE, unit: str = ""):
        """注册指标收集器"""
        self.collectors[name] = collector

    def collect(self, name: str, metric_type: MetricType = MetricType.GAUGE,
                unit: str = "", labels: Optional[Dict[str, str]] = None) -> SystemMetric:
        """收集单个指标"""
        collector = self.collectors.get(name)
        value = collector() if collector else 0.0
        metric = SystemMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            unit=unit,
            labels=labels or {},
        )
        self.metrics.append(metric)
        return metric

    def collect_all(self) -> List[SystemMetric]:
        """收集所有注册指标"""
        results = []
        for name, collector in self.collectors.items():
            try:
                value = collector()
                metric = SystemMetric(name=name, value=value, metric_type=MetricType.GAUGE)
                self.metrics.append(metric)
                results.append(metric)
            except Exception as e:
                logger.warning(f"指标收集失败 {name}: {e}")
        return results

    def get_metrics(self, name: Optional[str] = None) -> List[SystemMetric]:
        """获取指标列表"""
        if name:
            return [m for m in self.metrics if m.name == name]
        return self.metrics

    def get_history(self, name: str, limit: int = 100) -> List[SystemMetric]:
        """获取指标历史"""
        filtered = [m for m in self.metrics if m.name == name]
        return filtered[-limit:]

    def clear(self):
        """清空指标"""
        self.metrics.clear()


class AlertManager:
    """告警管理器"""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.rules: List[Dict[str, Any]] = []
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"ALERT-{self._counter:06d}"

    def add_rule(self, name: str, condition: Callable[[float], bool],
                 level: AlertLevel = AlertLevel.WARNING, message: str = ""):
        """添加告警规则"""
        self.rules.append({
            "name": name,
            "condition": condition,
            "level": level,
            "message": message,
        })

    def check_metric(self, metric: SystemMetric) -> List[Alert]:
        """检查指标触发告警"""
        triggered = []
        for rule in self.rules:
            if rule["name"] == metric.name:
                try:
                    if rule["condition"](metric.value):
                        alert = Alert(
                            alert_id=self._next_id(),
                            level=rule["level"],
                            title=f"{metric.name} 告警",
                            message=rule["message"] or f"{metric.name} = {metric.value}",
                            source=metric.name,
                        )
                        self.alerts.append(alert)
                        triggered.append(alert)
                        logger.warning(f"告警触发: {alert.alert_id} - {alert.title}")
                except Exception as e:
                    logger.warning(f"告警规则检查异常: {e}")
        return triggered

    def create_alert(self, level: AlertLevel, title: str, message: str,
                     source: str = "") -> Alert:
        """手动创建告警"""
        alert = Alert(
            alert_id=self._next_id(),
            level=level,
            title=title,
            message=message,
            source=source,
        )
        self.alerts.append(alert)
        return alert

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolve()
                logger.info(f"告警已解决: {alert_id}")
                return True
        return False

    def get_alerts(self, level: Optional[AlertLevel] = None,
                   include_resolved: bool = False) -> List[Alert]:
        """获取告警列表"""
        filtered = self.alerts
        if level:
            filtered = [a for a in filtered if a.level == level]
        if not include_resolved:
            filtered = [a for a in filtered if not a.resolved]
        return filtered

    def get_summary(self) -> Dict[str, int]:
        """获取告警摘要"""
        summary = {"total": 0, "active": 0, "resolved": 0}
        for level in AlertLevel:
            summary[level.value] = 0
        for alert in self.alerts:
            summary["total"] += 1
            if alert.resolved:
                summary["resolved"] += 1
            else:
                summary["active"] += 1
                summary[alert.level.value] += 1
        return summary


class StatusMonitor:
    """状态监控器"""

    def __init__(self):
        self.services: Dict[str, ServiceStatus] = {}
        self.checkers: Dict[str, Callable[[], ServiceStatus]] = {}

    def register_service(self, name: str, checker: Callable[[], ServiceStatus]):
        """注册服务检查器"""
        self.checkers[name] = checker

    def check_service(self, name: str) -> ServiceStatus:
        """检查单个服务"""
        checker = self.checkers.get(name)
        if checker:
            status = checker()
        else:
            status = ServiceStatus(
                name=name,
                healthy=False,
                status="unknown",
                details={"error": "未注册检查器"},
            )
        self.services[name] = status
        return status

    def check_all(self) -> Dict[str, ServiceStatus]:
        """检查所有服务"""
        for name in self.checkers:
            self.check_service(name)
        return self.services

    def get_overall_health(self) -> Dict[str, Any]:
        """获取整体健康状态"""
        if not self.services:
            return {"healthy": False, "total": 0, "healthy_count": 0, "unhealthy_count": 0}

        healthy_count = sum(1 for s in self.services.values() if s.healthy)
        total = len(self.services)
        return {
            "healthy": healthy_count == total,
            "total": total,
            "healthy_count": healthy_count,
            "unhealthy_count": total - healthy_count,
            "services": {name: s.to_dict() for name, s in self.services.items()},
        }


class DashboardRenderer:
    """仪表盘渲染器"""

    def __init__(self):
        self.sections: List[Dict[str, Any]] = []

    def add_section(self, title: str, content: str):
        """添加展示区块"""
        self.sections.append({"title": title, "content": content})

    def render_text(self, data: Dict[str, Any]) -> str:
        """渲染文本仪表盘"""
        lines = [
            "=" * 60,
            "系统仪表盘",
            f"时间: {datetime.now().isoformat()}",
            "=" * 60,
            "",
        ]

        # 整体健康
        health = data.get("health", {})
        status = "✓ 健康" if health.get("healthy") else "✗ 异常"
        lines.append(f"整体状态: {status}")
        lines.append(f"服务: {health.get('healthy_count', 0)}/{health.get('total', 0)} 正常")
        lines.append("")

        # 服务列表
        services = health.get("services", {})
        if services:
            lines.append("服务状态:")
            for name, svc in services.items():
                icon = "✓" if svc["healthy"] else "✗"
                lines.append(f"  {icon} {name}: {svc['status']} (运行 {svc['uptime_seconds']:.0f}s)")
            lines.append("")

        # 告警
        alerts = data.get("alerts", {})
        lines.append(f"告警: {alerts.get('active', 0)} 活跃 / {alerts.get('total', 0)} 总计")
        for level in ["critical", "error", "warning", "info"]:
            count = alerts.get(level, 0)
            if count > 0:
                lines.append(f"  {level.upper()}: {count}")
        lines.append("")

        # 指标
        metrics = data.get("metrics", [])
        if metrics:
            lines.append("关键指标:")
            for m in metrics[-5:]:
                lines.append(f"  {m['name']}: {m['value']:.2f} {m['unit']}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def render_json(self, data: Dict[str, Any]) -> str:
        """渲染JSON仪表盘"""
        return json.dumps(data, ensure_ascii=False, indent=2)

    def render_html(self, data: Dict[str, Any]) -> str:
        """渲染HTML仪表盘"""
        health = data.get("health", {})
        services = health.get("services", {})
        alerts = data.get("alerts", {})
        metrics = data.get("metrics", [])

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>系统仪表盘</title></head>
<body>
<h1>系统仪表盘</h1>
<p>时间: {datetime.now().isoformat()}</p>
<h2>整体状态: {'健康' if health.get('healthy') else '异常'}</h2>
<p>服务: {health.get('healthy_count', 0)}/{health.get('total', 0)} 正常</p>
<h2>服务列表</h2>
<ul>
"""
        for name, svc in services.items():
            color = "green" if svc["healthy"] else "red"
            html += f'<li style="color:{color}">{name}: {svc["status"]}</li>\n'

        html += f"""</ul>
<h2>告警: {alerts.get('active', 0)} 活跃</h2>
<ul>
"""
        for level in ["critical", "error", "warning", "info"]:
            count = alerts.get(level, 0)
            if count > 0:
                html += f"<li>{level.upper()}: {count}</li>\n"

        html += """</ul>
<h2>关键指标</h2>
<table border="1">
<tr><th>名称</th><th>值</th><th>单位</th></tr>
"""
        for m in metrics[-10:]:
            html += f"<tr><td>{m['name']}</td><td>{m['value']:.2f}</td><td>{m['unit']}</td></tr>\n"

        html += """</table>
</body>
</html>"""
        return html


class SystemDashboard:
    """系统仪表盘 - 主类"""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.status_monitor = StatusMonitor()
        self.renderer = DashboardRenderer()
        logger.info("系统仪表盘初始化完成")

    def collect_metrics(self) -> List[SystemMetric]:
        """收集所有指标"""
        return self.metrics_collector.collect_all()

    def check_services(self) -> Dict[str, ServiceStatus]:
        """检查所有服务"""
        return self.status_monitor.check_all()

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        return {
            "timestamp": datetime.now().isoformat(),
            "health": self.status_monitor.get_overall_health(),
            "alerts": self.alert_manager.get_summary(),
            "metrics": [m.to_dict() for m in self.metrics_collector.get_metrics()],
        }

    def render(self, format: str = "text") -> str:
        """渲染仪表盘"""
        data = self.get_dashboard_data()
        if format == "json":
            return self.renderer.render_json(data)
        elif format == "html":
            return self.renderer.render_html(data)
        else:
            return self.renderer.render_text(data)

    def save_dashboard(self, output_dir: Union[str, Path] = ".") -> Dict[str, Path]:
        """保存仪表盘到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        paths = {}
        text_path = output_dir / "dashboard.txt"
        text_path.write_text(self.render("text"), encoding="utf-8")
        paths["text"] = text_path

        json_path = output_dir / "dashboard.json"
        json_path.write_text(self.render("json"), encoding="utf-8")
        paths["json"] = json_path

        html_path = output_dir / "dashboard.html"
        html_path.write_text(self.render("html"), encoding="utf-8")
        paths["html"] = html_path

        logger.info(f"仪表盘已保存: {output_dir}")
        return paths

    def get_status(self) -> Dict[str, Any]:
        """获取仪表盘状态"""
        return {
            "metrics_count": len(self.metrics_collector.get_metrics()),
            "collectors_count": len(self.metrics_collector.collectors),
            "alerts_total": len(self.alert_manager.alerts),
            "alerts_active": len(self.alert_manager.get_alerts()),
            "services_count": len(self.status_monitor.services),
            "services_healthy": sum(1 for s in self.status_monitor.services.values() if s.healthy),
        }
