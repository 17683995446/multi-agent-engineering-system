"""
阶段88验证脚本：威胁检测模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.threat_detection import (
    ThreatLevel,
    ThreatType,
    ResponseAction,
    BehaviorEvent,
    ThreatIndicator,
    RiskScore,
    ThreatAlert,
    AnomalyDetector,
    BruteForceDetector,
    ThreatIntelligence,
    RiskScorer,
    AutoResponder,
    ThreatDetection,
)


def test_anomaly_detector():
    """测试异常检测器"""
    detector = AnomalyDetector(window_size=3, threshold_sigma=1.5)
    events = [
        BehaviorEvent("e1", "user1", "action", "sys", metadata={"value": 10}),
        BehaviorEvent("e2", "user1", "action", "sys", metadata={"value": 11}),
        BehaviorEvent("e3", "user1", "action", "sys", metadata={"value": 10}),
        BehaviorEvent("e4", "user1", "action", "sys", metadata={"value": 100}),
    ]
    indicators = detector.analyze(events)
    assert len(indicators) == 1
    assert indicators[0].threat_type == ThreatType.ANOMALY
    print("✓ 异常检测器测试通过")


def test_brute_force_detector():
    """测试暴力破解检测器"""
    detector = BruteForceDetector(max_attempts=3, window_seconds=300)
    events = [
        BehaviorEvent(f"e{i}", "attacker", "login_failed", "sys")
        for i in range(4)
    ]
    indicators = detector.analyze(events)
    assert len(indicators) == 2
    assert indicators[0].threat_type == ThreatType.BRUTE_FORCE
    print("✓ 暴力破解检测器测试通过")


def test_threat_intelligence():
    """测试威胁情报"""
    intel = ThreatIntelligence()
    intel.update_reputation("actor1", 0.2)
    assert intel.get_reputation("actor1") == 0.2
    assert intel.get_reputation("unknown") == 0.5

    indicator = ThreatIndicator("i1", ThreatType.MALWARE, "恶意软件", 0.9, "source")
    intel.add_indicator(indicator)
    assert len(intel.get_indicators_by_type(ThreatType.MALWARE)) == 1
    print("✓ 威胁情报测试通过")


def test_risk_scorer():
    """测试风险评分器"""
    scorer = RiskScorer()
    intel = ThreatIntelligence()
    intel.update_reputation("actor1", 0.1)
    indicators = [ThreatIndicator("i1", ThreatType.BRUTE_FORCE, "暴力破解", 0.9, "det")]
    risk = scorer.calculate("actor1", indicators, intel, metadata={"privilege_level": 0.8})
    assert 0.0 <= risk.score <= 1.0
    assert len(risk.factors) == 5
    print("✓ 风险评分器测试通过")


def test_auto_responder():
    """测试自动响应器"""
    responder = AutoResponder()
    alert = ThreatAlert(
        alert_id="a1",
        threat_type=ThreatType.BRUTE_FORCE,
        threat_level=ThreatLevel.HIGH,
        actor_id="attacker",
        description="暴力破解"
    )
    results = responder.respond(alert)
    assert len(results) >= 2
    actions = [r.action for r in results]
    assert ResponseAction.BLOCK in actions
    assert ResponseAction.NOTIFY in actions
    print("✓ 自动响应器测试通过")


def test_threat_detection_integration():
    """测试威胁检测主类集成"""
    td = ThreatDetection()
    events = [
        BehaviorEvent("e1", "user1", "login_failed", "sys"),
        BehaviorEvent("e2", "user1", "login_failed", "sys"),
        BehaviorEvent("e3", "user1", "login_failed", "sys"),
        BehaviorEvent("e4", "user1", "login_failed", "sys"),
        BehaviorEvent("e5", "user1", "login_failed", "sys"),
        BehaviorEvent("e6", "user1", "login_failed", "sys"),
    ]
    alerts = td.process_events(events)
    assert len(alerts) >= 1

    stats = td.get_statistics()
    assert stats["total_alerts"] >= 1
    assert stats["open_alerts"] >= 1
    print("✓ 威胁检测主类集成测试通过")


def test_alert_close():
    """测试告警关闭"""
    td = ThreatDetection()
    events = [BehaviorEvent(f"e{i}", "user1", "login_failed", "sys") for i in range(6)]
    alerts = td.process_events(events)
    alert_id = alerts[0].alert_id
    assert td.close_alert(alert_id) is True
    assert len(td.get_open_alerts()) == 0
    print("✓ 告警关闭测试通过")


def test_custom_analyzer():
    """测试自定义分析器"""
    from common.threat_detection import BehaviorAnalyzer

    class CustomAnalyzer(BehaviorAnalyzer):
        def analyze(self, events):
            return [ThreatIndicator("c1", ThreatType.INSIDER_THREAT, "内部威胁", 0.8, "custom")]

    td = ThreatDetection()
    td.add_analyzer(CustomAnalyzer())
    events = [BehaviorEvent("e1", "user1", "action", "sys")]
    alerts = td.process_events(events)
    assert len(alerts) >= 1
    print("✓ 自定义分析器测试通过")


def test_risk_weights():
    """测试风险权重设置"""
    scorer = RiskScorer()
    scorer.set_weights({"behavior_anomaly": 0.5, "threat_intel": 0.5})
    intel = ThreatIntelligence()
    risk = scorer.calculate("user1", [], intel)
    assert risk.score >= 0.0
    print("✓ 风险权重设置测试通过")


def main():
    print("=" * 60)
    print("阶段88验证：威胁检测模块")
    print("=" * 60)

    test_anomaly_detector()
    test_brute_force_detector()
    test_threat_intelligence()
    test_risk_scorer()
    test_auto_responder()
    test_threat_detection_integration()
    test_alert_close()
    test_custom_analyzer()
    test_risk_weights()

    print("=" * 60)
    print("阶段88验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
