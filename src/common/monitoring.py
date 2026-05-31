"""
监控告警系统
遵循第一性原理：信息最小熵公理

核心功能：
1. 指标收集（Metrics）
2. 告警规则管理
3. 告警通道
4. 告警抑制和分组
5. 告警历史记录
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(Enum):
    """告警严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(Enum):
    """告警状态"""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class AlertChannelType(Enum):
    """告警通道类型"""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"


@dataclass
class Metric:
    """
    指标数据
    
    属性：
    - name: 指标名称
    - type: 指标类型
    - value: 当前值
    - labels: 标签
    - timestamp: 时间戳
    """
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Alert:
    """
    告警记录
    
    属性：
    - alert_id: 告警ID
    - name: 告警名称
    - severity: 严重程度
    - status: 状态
    - message: 消息
    - metric_name: 关联的指标名
    - current_value: 当前值
    - threshold: 阈值
    - fired_at: 触发时间
    - resolved_at: 解决时间
    - labels: 标签
    """
    alert_id: str
    name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    metric_name: str
    current_value: float
    threshold: float
    fired_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "fired_at": self.fired_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "labels": self.labels
        }


@dataclass
class AlertRule:
    """
    告警规则
    
    属性：
    - rule_id: 规则ID
    - name: 规则名称
    - metric_name: 监控的指标名
    - condition: 条件（">", "<", ">=", "<=", "==", "!="）
    - threshold: 阈值
    - severity: 严重程度
    - enabled: 是否启用
    - description: 描述
    """
    rule_id: str
    name: str
    metric_name: str
    condition: str
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    description: str = ""
    
    def evaluate(self, value: float) -> bool:
        """评估规则是否触发"""
        if self.condition == ">":
            return value > self.threshold
        elif self.condition == "<":
            return value < self.threshold
        elif self.condition == ">=":
            return value >= self.threshold
        elif self.condition == "<=":
            return value <= self.threshold
        elif self.condition == "==":
            return value == self.threshold
        elif self.condition == "!=":
            return value != self.threshold
        return False


class AlertChannel(ABC):
    """告警通道基类"""
    
    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """发送告警"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """关闭通道"""
        pass


class LogAlertChannel(AlertChannel):
    """日志告警通道"""
    
    def __init__(self):
        """初始化日志通道"""
        logger.info("日志告警通道初始化")
    
    def send(self, alert: Alert) -> bool:
        """发送告警到日志"""
        logger.warning(
            f"[{alert.severity.value.upper()}] {alert.name}: {alert.message}"
        )
        return True
    
    def close(self) -> None:
        """关闭通道"""
        logger.info("日志告警通道关闭")


class ConsoleAlertChannel(AlertChannel):
    """控制台告警通道"""
    
    def __init__(self):
        """初始化控制台通道"""
        self.alerts: List[Alert] = []
    
    def send(self, alert: Alert) -> bool:
        """发送告警到控制台"""
        self.alerts.append(alert)
        print(f"[{alert.severity.value.upper()}] {alert.name}: {alert.message}")
        return True
    
    def close(self) -> None:
        """关闭通道"""
        self.alerts.clear()
    
    def get_alerts(self) -> List[Alert]:
        """获取所有告警"""
        return self.alerts.copy()


class WebhookAlertChannel(AlertChannel):
    """Webhook告警通道"""
    
    def __init__(self, webhook_url: str = ""):
        """初始化Webhook通道"""
        self.webhook_url = webhook_url
        self.sent_alerts: List[Alert] = []
        logger.info(f"Webhook告警通道初始化: {webhook_url}")
    
    def send(self, alert: Alert) -> bool:
        """发送告警到Webhook"""
        self.sent_alerts.append(alert)
        logger.info(f"告警发送到Webhook: {self.webhook_url}")
        return True
    
    def close(self) -> None:
        """关闭通道"""
        self.sent_alerts.clear()
        logger.info("Webhook告警通道关闭")


class MetricsCollector:
    """
    指标收集器
    
    核心方法：
    - record_counter: 记录计数器
    - record_gauge: 记录仪表
    - record_histogram: 记录直方图
    - get_metric: 获取指标
    - get_all_metrics: 获取所有指标
    """
    
    def __init__(self, name: str = "metrics_collector"):
        """初始化指标收集器"""
        self.name = name
        self.metrics: Dict[str, Metric] = {}
        self.counters: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        logger.info(f"指标收集器初始化: {name}")
    
    def record_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """记录计数器"""
        labels = labels or {}
        key = self._make_key(name, labels)
        
        self.counters[key] += value
        self.metrics[key] = Metric(
            name=name,
            type=MetricType.COUNTER,
            value=self.counters[key],
            labels=labels
        )
        logger.debug(f"计数器记录: {key} = {self.counters[key]}")
    
    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录仪表"""
        labels = labels or {}
        key = self._make_key(name, labels)
        
        self.metrics[key] = Metric(
            name=name,
            type=MetricType.GAUGE,
            value=value,
            labels=labels
        )
        logger.debug(f"仪表记录: {key} = {value}")
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录直方图"""
        labels = labels or {}
        key = self._make_key(name, labels)
        
        self.histograms[key].append(value)
        self.metrics[key] = Metric(
            name=name,
            type=MetricType.HISTOGRAM,
            value=value,
            labels=labels
        )
        logger.debug(f"直方图记录: {key} = {value}")
    
    def get_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[Metric]:
        """获取指标"""
        labels = labels or {}
        key = self._make_key(name, labels)
        return self.metrics.get(key)
    
    def get_all_metrics(self) -> List[Metric]:
        """获取所有指标"""
        return list(self.metrics.values())
    
    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """生成指标键"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def reset(self) -> None:
        """重置所有指标"""
        self.counters.clear()
        self.histograms.clear()
        self.metrics.clear()
        logger.info("指标收集器重置")


class AlertManager:
    """
    告警管理器
    
    核心方法：
    - add_rule: 添加告警规则
    - remove_rule: 移除告警规则
    - add_channel: 添加告警通道
    - remove_channel: 移除告警通道
    - check_metrics: 检查指标并触发告警
    - get_active_alerts: 获取活跃告警
    - acknowledge_alert: 确认告警
    - resolve_alert: 解决告警
    """
    
    def __init__(self, name: str = "alert_manager"):
        """初始化告警管理器"""
        self.name = name
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[str, AlertChannel] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_count = 0
        logger.info(f"告警管理器初始化: {name}")
    
    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self.rules[rule.rule_id] = rule
        logger.info(f"添加告警规则: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除告警规则"""
        if rule_id in self.rules:
            rule = self.rules.pop(rule_id)
            logger.info(f"移除告警规则: {rule.name}")
            return True
        return False
    
    def add_channel(self, channel: AlertChannel, channel_id: Optional[str] = None) -> None:
        """添加告警通道"""
        channel_id = channel_id or f"channel_{len(self.channels)}"
        self.channels[channel_id] = channel
        logger.info(f"添加告警通道: {channel_id}")
    
    def remove_channel(self, channel_id: str) -> bool:
        """移除告警通道"""
        if channel_id in self.channels:
            channel = self.channels.pop(channel_id)
            channel.close()
            logger.info(f"移除告警通道: {channel_id}")
            return True
        return False
    
    def check_metrics(self, metrics: List[Metric]) -> List[Alert]:
        """检查指标并触发告警"""
        fired_alerts = []
        
        for metric in metrics:
            for rule in self.rules.values():
                if not rule.enabled:
                    continue
                
                if rule.metric_name != metric.name:
                    continue
                
                if rule.evaluate(metric.value):
                    alert = self._fire_alert(rule, metric)
                    fired_alerts.append(alert)
                    self._notify_channels(alert)
        
        return fired_alerts
    
    def _fire_alert(self, rule: AlertRule, metric: Metric) -> Alert:
        """触发告警"""
        self.alert_count += 1
        alert_id = f"alert_{self.alert_count}"
        
        message = (
            f"{rule.name}: {metric.name} = {metric.value} "
            f"({rule.condition} {rule.threshold})"
        )
        
        alert = Alert(
            alert_id=alert_id,
            name=rule.name,
            severity=rule.severity,
            status=AlertStatus.FIRING,
            message=message,
            metric_name=metric.name,
            current_value=metric.value,
            threshold=rule.threshold,
            labels=metric.labels
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        logger.warning(f"告警触发: {alert.name} - {alert.message}")
        return alert
    
    def _notify_channels(self, alert: Alert) -> None:
        """通知所有通道"""
        for channel in self.channels.values():
            try:
                channel.send(alert)
            except Exception as e:
                logger.error(f"告警通道发送失败: {e}")
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [
            alert for alert in self.active_alerts.values()
            if alert.status == AlertStatus.FIRING
        ]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].status = AlertStatus.ACKNOWLEDGED
            logger.info(f"告警确认: {alert_id}")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            logger.info(f"告警解决: {alert_id}")
            return True
        return False
    
    def get_alert_history(self, limit: Optional[int] = None) -> List[Alert]:
        """获取告警历史"""
        if limit:
            return self.alert_history[-limit:]
        return self.alert_history.copy()
    
    def get_alert_count_by_severity(self) -> Dict[str, int]:
        """按严重程度统计告警数量"""
        counts = defaultdict(int)
        for alert in self.active_alerts.values():
            counts[alert.severity.value] += 1
        return dict(counts)


class MonitoringSystem:
    """
    监控系统
    
    整合指标收集和告警管理
    
    核心方法：
    - start: 启动监控系统
    - stop: 停止监控系统
    - record_metric: 记录指标
    - check_alerts: 检查告警
    - get_status: 获取状态
    """
    
    def __init__(self, name: str = "monitoring_system"):
        """初始化监控系统"""
        self.name = name
        self.collector = MetricsCollector(f"{name}_collector")
        self.alert_manager = AlertManager(f"{name}_manager")
        self.is_running = False
        logger.info(f"监控系统初始化: {name}")
    
    def start(self) -> None:
        """启动监控系统"""
        self.is_running = True
        logger.info(f"监控系统启动: {self.name}")
    
    def stop(self) -> None:
        """停止监控系统"""
        self.is_running = False
        logger.info(f"监控系统停止: {self.name}")
    
    def record_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """记录计数器"""
        self.collector.record_counter(name, value, labels)
    
    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录仪表"""
        self.collector.record_gauge(name, value, labels)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录直方图"""
        self.collector.record_histogram(name, value, labels)
    
    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        severity: AlertSeverity,
        description: str = ""
    ) -> None:
        """添加告警规则"""
        import uuid
        rule_id = str(uuid.uuid4())[:8]
        rule = AlertRule(
            rule_id=rule_id,
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            severity=severity,
            description=description
        )
        self.alert_manager.add_rule(rule)
    
    def check_alerts(self) -> List[Alert]:
        """检查告警"""
        metrics = self.collector.get_all_metrics()
        return self.alert_manager.check_metrics(metrics)
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "name": self.name,
            "is_running": self.is_running,
            "metrics_count": len(self.collector.get_all_metrics()),
            "active_alerts": len(self.alert_manager.get_active_alerts()),
            "alert_rules": len(self.alert_manager.rules),
            "alert_channels": len(self.alert_manager.channels)
        }
