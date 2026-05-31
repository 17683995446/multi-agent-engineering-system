"""
威胁检测模块
职责：异常行为检测、威胁情报、风险评分、自动响应
依赖规则：引用公共层 utils
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Set
from collections import defaultdict
import statistics

from common.utils import setup_logger

logger = setup_logger(__name__)


class ThreatLevel(Enum):
    """威胁级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ThreatType(Enum):
    """威胁类型"""
    ANOMALY = "anomaly"
    BRUTE_FORCE = "brute_force"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MALWARE = "malware"
    INSIDER_THREAT = "insider_threat"


class ResponseAction(Enum):
    """响应动作"""
    ALERT = "alert"
    BLOCK = "block"
    QUARANTINE = "quarantine"
    NOTIFY = "notify"
    LOG = "log"
    ESCALATE = "escalate"


@dataclass
class BehaviorEvent:
    """行为事件"""
    event_id: str
    actor_id: str
    action: str
    target: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatIndicator:
    """威胁指标"""
    indicator_id: str
    threat_type: ThreatType
    description: str
    confidence: float
    source: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskScore:
    """风险评分"""
    actor_id: str
    score: float
    factors: List[Dict[str, Any]] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ThreatAlert:
    """威胁告警"""
    alert_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    actor_id: str
    description: str
    indicators: List[ThreatIndicator] = field(default_factory=list)
    recommended_actions: List[ResponseAction] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "open"


@dataclass
class ResponseResult:
    """响应结果"""
    alert_id: str
    action: ResponseAction
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=datetime.now)


class BehaviorAnalyzer(ABC):
    """行为分析器基类"""

    @abstractmethod
    def analyze(self, events: List[BehaviorEvent]) -> List[ThreatIndicator]:
        pass


class AnomalyDetector(BehaviorAnalyzer):
    """
    异常行为检测器
    基于统计方法检测偏离正常模式的行为
    """

    def __init__(self, window_size: int = 10, threshold_sigma: float = 2.0):
        self.window_size = window_size
        self.threshold_sigma = threshold_sigma
        self._history: Dict[str, List[float]] = defaultdict(list)
        self.logger = setup_logger(f"{__name__}.anomaly")

    def analyze(self, events: List[BehaviorEvent]) -> List[ThreatIndicator]:
        indicators = []
        for event in events:
            actor = event.actor_id
            value = self._extract_metric(event)
            if value is None:
                continue

            history = self._history[actor]
            if len(history) >= self.window_size:
                mean = statistics.mean(history[-self.window_size:])
                stdev = statistics.stdev(history[-self.window_size:]) if len(history) >= 2 else 0
                if stdev > 0 and abs(value - mean) > self.threshold_sigma * stdev:
                    indicators.append(ThreatIndicator(
                        indicator_id=f"anomaly_{event.event_id}",
                        threat_type=ThreatType.ANOMALY,
                        description=f"检测到异常行为: {event.action}，值={value}，均值={mean:.2f}",
                        confidence=min(0.99, abs(value - mean) / (stdev + 1e-6) / 3),
                        source="anomaly_detector"
                    ))
                    self.logger.warning(f"异常行为: actor={actor}, action={event.action}")

            history.append(value)

        return indicators

    def _extract_metric(self, event: BehaviorEvent) -> Optional[float]:
        """从事件中提取数值指标"""
        return event.metadata.get("value", event.metadata.get("count"))


class BruteForceDetector(BehaviorAnalyzer):
    """
    暴力破解检测器
    检测短时间内大量失败尝试
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, List[datetime]] = defaultdict(list)
        self.logger = setup_logger(f"{__name__}.brute_force")

    def analyze(self, events: List[BehaviorEvent]) -> List[ThreatIndicator]:
        indicators = []
        for event in events:
            if event.action != "login_failed":
                continue

            actor = event.actor_id
            now = event.timestamp
            window_start = now - timedelta(seconds=self.window_seconds)

            attempts = self._attempts[actor]
            attempts.append(now)
            attempts[:] = [t for t in attempts if t > window_start]

            if len(attempts) >= self.max_attempts:
                indicators.append(ThreatIndicator(
                    indicator_id=f"brute_force_{event.event_id}",
                    threat_type=ThreatType.BRUTE_FORCE,
                    description=f"检测到暴力破解: {len(attempts)} 次失败登录",
                    confidence=min(0.95, len(attempts) / self.max_attempts * 0.8),
                    source="brute_force_detector"
                ))
                self.logger.warning(f"暴力破解: actor={actor}, attempts={len(attempts)}")

        return indicators


class ThreatIntelligence:
    """
    威胁情报管理
    维护已知威胁指标库
    """

    def __init__(self):
        self._indicators: Dict[str, ThreatIndicator] = {}
        self._actor_reputation: Dict[str, float] = {}
        self.logger = setup_logger(f"{__name__}.intel")

    def add_indicator(self, indicator: ThreatIndicator) -> None:
        """添加威胁指标"""
        self._indicators[indicator.indicator_id] = indicator
        self.logger.info(f"添加威胁指标: {indicator.indicator_id}")

    def check_actor(self, actor_id: str) -> Optional[ThreatIndicator]:
        """检查Actor是否在威胁情报中"""
        for indicator in self._indicators.values():
            if indicator.metadata.get("actor_id") == actor_id:
                return indicator
        return None

    def get_reputation(self, actor_id: str) -> float:
        """获取Actor信誉分 (0-1, 1为最高信誉)"""
        return self._actor_reputation.get(actor_id, 0.5)

    def update_reputation(self, actor_id: str, score: float) -> None:
        """更新Actor信誉分"""
        self._actor_reputation[actor_id] = max(0.0, min(1.0, score))
        self.logger.info(f"更新信誉: actor={actor_id}, score={score}")

    def get_indicators_by_type(self, threat_type: ThreatType) -> List[ThreatIndicator]:
        """按类型获取威胁指标"""
        return [i for i in self._indicators.values() if i.threat_type == threat_type]


class RiskScorer:
    """
    风险评分器
    综合多维度因素计算风险分数
    """

    def __init__(self):
        self._weights = {
            "behavior_anomaly": 0.3,
            "threat_intel": 0.25,
            "privilege_level": 0.2,
            "data_sensitivity": 0.15,
            "time_factor": 0.1,
        }
        self.logger = setup_logger(f"{__name__}.risk")

    def calculate(self, actor_id: str, indicators: List[ThreatIndicator],
                  intel: ThreatIntelligence, metadata: Optional[Dict[str, Any]] = None) -> RiskScore:
        """计算风险评分"""
        factors = []
        total_score = 0.0

        behavior_score = self._calc_behavior_score(indicators)
        factors.append({"name": "behavior_anomaly", "score": behavior_score, "weight": self._weights["behavior_anomaly"]})
        total_score += behavior_score * self._weights["behavior_anomaly"]

        intel_score = 1.0 - intel.get_reputation(actor_id)
        factors.append({"name": "threat_intel", "score": intel_score, "weight": self._weights["threat_intel"]})
        total_score += intel_score * self._weights["threat_intel"]

        privilege = metadata.get("privilege_level", 0.5) if metadata else 0.5
        factors.append({"name": "privilege_level", "score": privilege, "weight": self._weights["privilege_level"]})
        total_score += privilege * self._weights["privilege_level"]

        sensitivity = metadata.get("data_sensitivity", 0.5) if metadata else 0.5
        factors.append({"name": "data_sensitivity", "score": sensitivity, "weight": self._weights["data_sensitivity"]})
        total_score += sensitivity * self._weights["data_sensitivity"]

        hour = datetime.now().hour
        time_risk = 0.7 if hour < 6 or hour > 22 else 0.3
        factors.append({"name": "time_factor", "score": time_risk, "weight": self._weights["time_factor"]})
        total_score += time_risk * self._weights["time_factor"]

        score = RiskScore(
            actor_id=actor_id,
            score=min(1.0, total_score),
            factors=factors
        )
        self.logger.info(f"风险评分: actor={actor_id}, score={score.score:.2f}")
        return score

    def _calc_behavior_score(self, indicators: List[ThreatIndicator]) -> float:
        """计算行为异常分数"""
        if not indicators:
            return 0.0
        return min(1.0, sum(i.confidence for i in indicators) / max(len(indicators), 3))

    def set_weights(self, weights: Dict[str, float]) -> None:
        """设置权重"""
        self._weights.update(weights)
        self.logger.info(f"更新风险权重: {weights}")


class AutoResponder:
    """
    自动响应器
    根据威胁级别自动执行响应动作
    """

    def __init__(self):
        self._action_handlers: Dict[ResponseAction, Callable] = {}
        self._rules: List[Dict[str, Any]] = []
        self.logger = setup_logger(f"{__name__}.responder")
        self._init_default_handlers()
        self._init_default_rules()

    def _init_default_handlers(self) -> None:
        """初始化默认处理器"""
        self._action_handlers[ResponseAction.ALERT] = self._handle_alert
        self._action_handlers[ResponseAction.BLOCK] = self._handle_block
        self._action_handlers[ResponseAction.NOTIFY] = self._handle_notify
        self._action_handlers[ResponseAction.LOG] = self._handle_log
        self._action_handlers[ResponseAction.ESCALATE] = self._handle_escalate

    def _init_default_rules(self) -> None:
        """初始化默认响应规则"""
        self._rules = [
            {"threat_level": ThreatLevel.CRITICAL, "actions": [ResponseAction.BLOCK, ResponseAction.NOTIFY, ResponseAction.ESCALATE]},
            {"threat_level": ThreatLevel.HIGH, "actions": [ResponseAction.BLOCK, ResponseAction.NOTIFY]},
            {"threat_level": ThreatLevel.MEDIUM, "actions": [ResponseAction.ALERT, ResponseAction.LOG]},
            {"threat_level": ThreatLevel.LOW, "actions": [ResponseAction.LOG]},
        ]

    def respond(self, alert: ThreatAlert) -> List[ResponseResult]:
        """对告警执行响应"""
        results = []
        actions = self._determine_actions(alert)

        for action in actions:
            handler = self._action_handlers.get(action)
            if handler:
                try:
                    detail = handler(alert)
                    results.append(ResponseResult(
                        alert_id=alert.alert_id,
                        action=action,
                        success=True,
                        details=detail
                    ))
                    self.logger.info(f"响应执行: alert={alert.alert_id}, action={action.value}")
                except Exception as e:
                    results.append(ResponseResult(
                        alert_id=alert.alert_id,
                        action=action,
                        success=False,
                        details={"error": str(e)}
                    ))
                    self.logger.error(f"响应失败: alert={alert.alert_id}, action={action.value}, error={e}")

        return results

    def _determine_actions(self, alert: ThreatAlert) -> List[ResponseAction]:
        """确定响应动作"""
        for rule in self._rules:
            if rule["threat_level"] == alert.threat_level:
                return rule["actions"]
        return [ResponseAction.LOG]

    def _handle_alert(self, alert: ThreatAlert) -> Dict[str, Any]:
        return {"message": f"告警: {alert.description}", "severity": alert.threat_level.value}

    def _handle_block(self, alert: ThreatAlert) -> Dict[str, Any]:
        return {"actor_id": alert.actor_id, "blocked": True, "duration": "1h"}

    def _handle_notify(self, alert: ThreatAlert) -> Dict[str, Any]:
        return {"channels": ["email", "sms"], "recipients": ["security_team"]}

    def _handle_log(self, alert: ThreatAlert) -> Dict[str, Any]:
        return {"log_level": "warning", "event": "threat_detected"}

    def _handle_escalate(self, alert: ThreatAlert) -> Dict[str, Any]:
        return {"escalated_to": "incident_response_team", "priority": "p1"}

    def register_handler(self, action: ResponseAction, handler: Callable) -> None:
        """注册自定义处理器"""
        self._action_handlers[action] = handler
        self.logger.info(f"注册响应处理器: {action.value}")

    def add_rule(self, threat_level: ThreatLevel, actions: List[ResponseAction]) -> None:
        """添加响应规则"""
        self._rules.append({"threat_level": threat_level, "actions": actions})


class ThreatDetection:
    """
    威胁检测主类
    整合异常检测、威胁情报、风险评分、自动响应
    """

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.brute_force_detector = BruteForceDetector()
        self.threat_intel = ThreatIntelligence()
        self.risk_scorer = RiskScorer()
        self.auto_responder = AutoResponder()
        self.logger = setup_logger(__name__)
        self._alerts: List[ThreatAlert] = []
        self._analyzers: List[BehaviorAnalyzer] = [
            self.anomaly_detector,
            self.brute_force_detector,
        ]

    def process_events(self, events: List[BehaviorEvent]) -> List[ThreatAlert]:
        """处理行为事件，检测威胁"""
        all_indicators = []
        for analyzer in self._analyzers:
            indicators = analyzer.analyze(events)
            all_indicators.extend(indicators)

        alerts = []
        actor_indicators: Dict[str, List[ThreatIndicator]] = defaultdict(list)
        for indicator in all_indicators:
            actor = indicator.metadata.get("actor_id", "unknown")
            actor_indicators[actor].append(indicator)

        for actor, indicators in actor_indicators.items():
            risk = self.risk_scorer.calculate(actor, indicators, self.threat_intel)
            threat_level = self._score_to_level(risk.score)

            alert = ThreatAlert(
                alert_id=f"alert_{actor}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                threat_type=indicators[0].threat_type if indicators else ThreatType.ANOMALY,
                threat_level=threat_level,
                actor_id=actor,
                description=f"检测到威胁: {len(indicators)} 个指标，风险分={risk.score:.2f}",
                indicators=indicators,
                recommended_actions=self._get_recommended_actions(threat_level)
            )
            alerts.append(alert)
            self._alerts.append(alert)
            self.logger.warning(f"威胁告警: {alert.alert_id}, level={threat_level.value}, actor={actor}")

            if threat_level in {ThreatLevel.CRITICAL, ThreatLevel.HIGH}:
                self.auto_responder.respond(alert)

        return alerts

    def _score_to_level(self, score: float) -> ThreatLevel:
        """分数转威胁级别"""
        if score >= 0.8:
            return ThreatLevel.CRITICAL
        elif score >= 0.6:
            return ThreatLevel.HIGH
        elif score >= 0.4:
            return ThreatLevel.MEDIUM
        elif score >= 0.2:
            return ThreatLevel.LOW
        return ThreatLevel.INFO

    def _get_recommended_actions(self, level: ThreatLevel) -> List[ResponseAction]:
        """获取推荐响应动作"""
        mapping = {
            ThreatLevel.CRITICAL: [ResponseAction.BLOCK, ResponseAction.NOTIFY, ResponseAction.ESCALATE],
            ThreatLevel.HIGH: [ResponseAction.BLOCK, ResponseAction.NOTIFY],
            ThreatLevel.MEDIUM: [ResponseAction.ALERT, ResponseAction.LOG],
            ThreatLevel.LOW: [ResponseAction.LOG],
            ThreatLevel.INFO: [ResponseAction.LOG],
        }
        return mapping.get(level, [ResponseAction.LOG])

    def get_open_alerts(self) -> List[ThreatAlert]:
        """获取未关闭告警"""
        return [a for a in self._alerts if a.status == "open"]

    def close_alert(self, alert_id: str) -> bool:
        """关闭告警"""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.status = "closed"
                self.logger.info(f"告警关闭: {alert_id}")
                return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._alerts)
        by_level = defaultdict(int)
        by_type = defaultdict(int)
        for alert in self._alerts:
            by_level[alert.threat_level.value] += 1
            by_type[alert.threat_type.value] += 1

        return {
            "total_alerts": total,
            "open_alerts": len(self.get_open_alerts()),
            "by_level": dict(by_level),
            "by_type": dict(by_type),
        }

    def add_analyzer(self, analyzer: BehaviorAnalyzer) -> None:
        """添加自定义分析器"""
        self._analyzers.append(analyzer)
        self.logger.info(f"添加行为分析器: {analyzer.__class__.__name__}")


def demo_threat_detection():
    """演示威胁检测系统"""
    print("=" * 70)
    print("威胁检测系统演示")
    print("=" * 70)
    print()

    td = ThreatDetection()

    print("1. 正常行为事件:")
    normal_events = [
        BehaviorEvent("e1", "user_a", "login", "system", metadata={"value": 10}),
        BehaviorEvent("e2", "user_a", "login", "system", metadata={"value": 12}),
        BehaviorEvent("e3", "user_a", "login", "system", metadata={"value": 11}),
    ]
    alerts = td.process_events(normal_events)
    print(f"   事件数: {len(normal_events)}, 告警数: {len(alerts)}")
    print()

    print("2. 异常行为事件:")
    anomaly_events = [
        BehaviorEvent("e4", "user_a", "login", "system", metadata={"value": 100}),
    ]
    alerts = td.process_events(anomaly_events)
    print(f"   事件数: {len(anomaly_events)}, 告警数: {len(alerts)}")
    for alert in alerts:
        print(f"   - [{alert.threat_level.value}] {alert.description}")
    print()

    print("3. 暴力破解检测:")
    brute_events = []
    for i in range(6):
        brute_events.append(BehaviorEvent(
            f"bf{i}", "attacker_1", "login_failed", "system"
        ))
    alerts = td.process_events(brute_events)
    print(f"   失败登录: {len(brute_events)}, 告警数: {len(alerts)}")
    for alert in alerts:
        print(f"   - [{alert.threat_level.value}] {alert.description}")
    print()

    print("4. 威胁情报:")
    td.threat_intel.update_reputation("attacker_1", 0.1)
    print(f"   attacker_1 信誉分: {td.threat_intel.get_reputation('attacker_1')}")
    print()

    print("5. 风险评分:")
    indicators = [
        ThreatIndicator("i1", ThreatType.BRUTE_FORCE, "暴力破解", 0.9, "detector")
    ]
    risk = td.risk_scorer.calculate("attacker_1", indicators, td.threat_intel,
                                     metadata={"privilege_level": 0.8, "data_sensitivity": 0.9})
    print(f"   风险分: {risk.score:.2f}")
    for factor in risk.factors:
        print(f"   - {factor['name']}: {factor['score']:.2f} (权重 {factor['weight']})")
    print()

    print("6. 告警统计:")
    stats = td.get_statistics()
    print(f"   总告警: {stats['total_alerts']}")
    print(f"   未关闭: {stats['open_alerts']}")
    print(f"   按级别: {stats['by_level']}")
    print()

    print("=" * 70)
    print("威胁检测系统演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_threat_detection()
