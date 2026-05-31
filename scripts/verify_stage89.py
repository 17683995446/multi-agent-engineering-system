"""
阶段89验证脚本：合规检查模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.compliance_checker import (
    ComplianceLevel,
    ComplianceStatus,
    ComplianceFramework,
    ComplianceRule,
    ComplianceFinding,
    RemediationAdvice,
    ComplianceReport,
    RuleEngine,
    ComplianceChecker,
    RemediationAdvisor,
    ComplianceReporter,
    ComplianceManager,
)


def test_rule_engine():
    """测试规则引擎"""
    engine = RuleEngine()
    assert len(engine.get_all_rules()) == 7
    rules = engine.get_rules_by_framework(ComplianceFramework.GDPR)
    assert len(rules) == 2
    assert engine.get_rule("GDPR_001") is not None
    print("✓ 规则引擎测试通过")


def test_compliance_checker_gdpr():
    """测试GDPR合规检查"""
    engine = RuleEngine()
    checker = ComplianceChecker(engine)
    context = {"has_consent_mechanism": True, "consent_records": 100}
    finding = checker.check("GDPR_001", context)
    assert finding.status == ComplianceStatus.COMPLIANT

    context = {"has_consent_mechanism": False}
    finding = checker.check("GDPR_001", context)
    assert finding.status == ComplianceStatus.NON_COMPLIANT
    print("✓ GDPR合规检查测试通过")


def test_compliance_checker_iso():
    """测试ISO27001合规检查"""
    engine = RuleEngine()
    checker = ComplianceChecker(engine)
    context = {"password_min_length": 12, "password_complexity": True}
    finding = checker.check("ISO27001_002", context)
    assert finding.status == ComplianceStatus.COMPLIANT

    context = {"password_min_length": 8, "password_complexity": False}
    finding = checker.check("ISO27001_002", context)
    assert finding.status == ComplianceStatus.NON_COMPLIANT
    print("✓ ISO27001合规检查测试通过")


def test_compliance_checker_all():
    """测试全部检查"""
    engine = RuleEngine()
    checker = ComplianceChecker(engine)
    context = {
        "has_consent_mechanism": True,
        "data_fields": ["name"],
        "required_fields": ["name"],
        "has_access_control_policy": True,
        "password_min_length": 12,
        "password_complexity": True,
        "has_monitoring": True,
        "log_retention_days": 90,
        "encrypts_cardholder_data": True,
        "has_phi_access_control": True,
    }
    findings = checker.check_all(context=context)
    assert len(findings) == 7
    assert all(f.status == ComplianceStatus.COMPLIANT for f in findings)
    print("✓ 全部检查测试通过")


def test_remediation_advisor():
    """测试整改建议"""
    engine = RuleEngine()
    advisor = RemediationAdvisor()
    finding = ComplianceFinding("f1", "ISO27001_002", ComplianceStatus.NON_COMPLIANT, "密码策略不合规")
    rule = engine.get_rule("ISO27001_002")
    advice = advisor.generate(finding, rule)
    assert advice.priority == 2
    assert len(advice.steps) > 0
    print("✓ 整改建议测试通过")


def test_remediation_batch():
    """测试批量整改建议"""
    engine = RuleEngine()
    advisor = RemediationAdvisor()
    findings = [
        ComplianceFinding("f1", "GDPR_001", ComplianceStatus.NON_COMPLIANT, "无同意机制"),
        ComplianceFinding("f2", "ISO27001_002", ComplianceStatus.NON_COMPLIANT, "密码弱"),
    ]
    advices = advisor.generate_batch(findings, engine)
    assert len(advices) == 2
    assert advices[0].priority <= advices[1].priority
    print("✓ 批量整改建议测试通过")


def test_compliance_report():
    """测试合规报告"""
    engine = RuleEngine()
    reporter = ComplianceReporter(engine)
    findings = [
        ComplianceFinding("f1", "GDPR_001", ComplianceStatus.COMPLIANT, "通过"),
        ComplianceFinding("f2", "GDPR_002", ComplianceStatus.NON_COMPLIANT, "未通过"),
    ]
    report = reporter.generate_report(findings, ComplianceFramework.GDPR)
    assert report.overall_status == ComplianceStatus.NON_COMPLIANT
    assert report.compliance_rate == 0.5
    assert report.compliant_count == 1
    assert report.non_compliant_count == 1
    print("✓ 合规报告测试通过")


def test_report_summary():
    """测试报告摘要"""
    engine = RuleEngine()
    reporter = ComplianceReporter(engine)
    findings = [
        ComplianceFinding("f1", "GDPR_001", ComplianceStatus.COMPLIANT, "通过"),
        ComplianceFinding("f2", "GDPR_002", ComplianceStatus.NON_COMPLIANT, "未通过"),
    ]
    report = reporter.generate_report(findings, ComplianceFramework.GDPR)
    summary = reporter.generate_summary(report)
    assert summary["compliance_rate"] == 0.5
    assert summary["by_status"]["compliant"] == 1
    assert summary["by_status"]["non_compliant"] == 1
    print("✓ 报告摘要测试通过")


def test_compliance_manager():
    """测试合规管理主类"""
    mgr = ComplianceManager()
    context = {
        "has_consent_mechanism": True,
        "data_fields": ["name"],
        "required_fields": ["name"],
    }
    report = mgr.run_assessment(ComplianceFramework.GDPR, context)
    assert report.framework == ComplianceFramework.GDPR
    assert len(report.findings) == 2
    print("✓ 合规管理主类测试通过")


def test_custom_rule():
    """测试自定义规则"""
    mgr = ComplianceManager()
    rule = ComplianceRule(
        rule_id="CUSTOM_001",
        framework=ComplianceFramework.CUSTOM,
        title="自定义规则",
        description="测试自定义规则",
        level=ComplianceLevel.HIGH
    )
    mgr.add_custom_rule(rule, lambda ctx, r: ComplianceFinding("fc", "CUSTOM_001", ComplianceStatus.COMPLIANT, "通过"))
    finding = mgr.checker.check("CUSTOM_001", {})
    assert finding.status == ComplianceStatus.COMPLIANT
    print("✓ 自定义规则测试通过")


def test_get_frameworks():
    """测试获取框架列表"""
    mgr = ComplianceManager()
    frameworks = mgr.get_frameworks()
    assert ComplianceFramework.GDPR in frameworks
    assert ComplianceFramework.ISO27001 in frameworks
    print("✓ 获取框架列表测试通过")


def main():
    print("=" * 60)
    print("阶段89验证：合规检查模块")
    print("=" * 60)

    test_rule_engine()
    test_compliance_checker_gdpr()
    test_compliance_checker_iso()
    test_compliance_checker_all()
    test_remediation_advisor()
    test_remediation_batch()
    test_compliance_report()
    test_report_summary()
    test_compliance_manager()
    test_custom_rule()
    test_get_frameworks()

    print("=" * 60)
    print("阶段89验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
