"""
合规检查模块
职责：合规规则、合规检查、合规报告、整改建议
依赖规则：引用公共层 utils
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable

from common.utils import setup_logger

logger = setup_logger(__name__)


class ComplianceLevel(Enum):
    """合规级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplianceStatus(Enum):
    """合规状态"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class ComplianceFramework(Enum):
    """合规框架"""
    GDPR = "gdpr"
    ISO27001 = "iso27001"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    CUSTOM = "custom"


@dataclass
class ComplianceRule:
    """合规规则"""
    rule_id: str
    framework: ComplianceFramework
    title: str
    description: str
    level: ComplianceLevel
    check_function: Optional[Callable] = None
    references: List[str] = field(default_factory=list)


@dataclass
class ComplianceFinding:
    """合规发现"""
    finding_id: str
    rule_id: str
    status: ComplianceStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RemediationAdvice:
    """整改建议"""
    finding_id: str
    priority: int
    description: str
    steps: List[str] = field(default_factory=list)
    estimated_effort: str = ""
    resources: List[str] = field(default_factory=list)


@dataclass
class ComplianceReport:
    """合规报告"""
    report_id: str
    framework: ComplianceFramework
    findings: List[ComplianceFinding] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    overall_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    score: float = 0.0

    @property
    def compliant_count(self) -> int:
        return sum(1 for f in self.findings if f.status == ComplianceStatus.COMPLIANT)

    @property
    def non_compliant_count(self) -> int:
        return sum(1 for f in self.findings if f.status == ComplianceStatus.NON_COMPLIANT)

    @property
    def compliance_rate(self) -> float:
        if not self.findings:
            return 1.0
        return self.compliant_count / len(self.findings)


class RuleEngine:
    """
    合规规则引擎
    管理所有合规规则
    """

    def __init__(self):
        self._rules: Dict[str, ComplianceRule] = {}
        self.logger = setup_logger(f"{__name__}.rules")
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """初始化默认合规规则"""
        default_rules = [
            ComplianceRule(
                rule_id="GDPR_001",
                framework=ComplianceFramework.GDPR,
                title="数据主体同意",
                description="处理个人数据前必须获得数据主体明确同意",
                level=ComplianceLevel.CRITICAL
            ),
            ComplianceRule(
                rule_id="GDPR_002",
                framework=ComplianceFramework.GDPR,
                title="数据最小化",
                description="仅收集处理目的所必需的个人数据",
                level=ComplianceLevel.HIGH
            ),
            ComplianceRule(
                rule_id="ISO27001_001",
                framework=ComplianceFramework.ISO27001,
                title="访问控制策略",
                description="必须制定并实施访问控制策略",
                level=ComplianceLevel.CRITICAL
            ),
            ComplianceRule(
                rule_id="ISO27001_002",
                framework=ComplianceFramework.ISO27001,
                title="密码策略",
                description="必须实施强密码策略",
                level=ComplianceLevel.HIGH
            ),
            ComplianceRule(
                rule_id="SOC2_001",
                framework=ComplianceFramework.SOC2,
                title="系统监控",
                description="必须对系统进行持续监控",
                level=ComplianceLevel.HIGH
            ),
            ComplianceRule(
                rule_id="PCI_DSS_001",
                framework=ComplianceFramework.PCI_DSS,
                title="持卡人数据保护",
                description="必须保护存储的持卡人数据",
                level=ComplianceLevel.CRITICAL
            ),
            ComplianceRule(
                rule_id="HIPAA_001",
                framework=ComplianceFramework.HIPAA,
                title="PHI访问控制",
                description="必须限制对受保护健康信息的访问",
                level=ComplianceLevel.CRITICAL
            ),
        ]
        for rule in default_rules:
            self.register_rule(rule)

    def register_rule(self, rule: ComplianceRule) -> None:
        """注册规则"""
        self._rules[rule.rule_id] = rule
        self.logger.info(f"注册合规规则: {rule.rule_id}")

    def get_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """获取规则"""
        return self._rules.get(rule_id)

    def get_rules_by_framework(self, framework: ComplianceFramework) -> List[ComplianceRule]:
        """按框架获取规则"""
        return [r for r in self._rules.values() if r.framework == framework]

    def get_all_rules(self) -> List[ComplianceRule]:
        """获取所有规则"""
        return list(self._rules.values())


class ComplianceChecker:
    """
    合规检查器
    执行合规检查
    """

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.logger = setup_logger(f"{__name__}.checker")
        self._check_handlers: Dict[str, Callable] = {}
        self._init_default_handlers()

    def _init_default_handlers(self) -> None:
        """初始化默认检查处理器"""
        self._check_handlers["GDPR_001"] = self._check_gdpr_consent
        self._check_handlers["GDPR_002"] = self._check_gdpr_minimization
        self._check_handlers["ISO27001_001"] = self._check_iso_access_control
        self._check_handlers["ISO27001_002"] = self._check_iso_password
        self._check_handlers["SOC2_001"] = self._check_soc2_monitoring
        self._check_handlers["PCI_DSS_001"] = self._check_pci_data_protection
        self._check_handlers["HIPAA_001"] = self._check_hipaa_access

    def check(self, rule_id: str, context: Dict[str, Any]) -> ComplianceFinding:
        """执行单条规则检查"""
        rule = self.rule_engine.get_rule(rule_id)
        if not rule:
            return ComplianceFinding(
                finding_id=f"finding_{rule_id}",
                rule_id=rule_id,
                status=ComplianceStatus.NOT_APPLICABLE,
                message=f"规则不存在: {rule_id}"
            )

        handler = self._check_handlers.get(rule_id)
        if handler:
            return handler(context, rule)

        return self._default_check(context, rule)

    def check_all(self, framework: Optional[ComplianceFramework] = None,
                  context: Optional[Dict[str, Any]] = None) -> List[ComplianceFinding]:
        """执行全部或指定框架检查"""
        context = context or {}
        if framework:
            rules = self.rule_engine.get_rules_by_framework(framework)
        else:
            rules = self.rule_engine.get_all_rules()

        findings = []
        for rule in rules:
            finding = self.check(rule.rule_id, context)
            findings.append(finding)
            self.logger.info(f"检查完成: {rule.rule_id} -> {finding.status.value}")

        return findings

    def _default_check(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        """默认检查"""
        if rule.check_function:
            result = rule.check_function(context)
            return ComplianceFinding(
                finding_id=f"finding_{rule.rule_id}",
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if result else ComplianceStatus.NON_COMPLIANT,
                message=f"规则 {rule.rule_id}: {'通过' if result else '未通过'}"
            )
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.NOT_APPLICABLE,
            message=f"规则 {rule.rule_id}: 无检查处理器"
        )

    def _check_gdpr_consent(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        has_consent = context.get("has_consent_mechanism", False)
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.COMPLIANT if has_consent else ComplianceStatus.NON_COMPLIANT,
            message="已实施同意机制" if has_consent else "未实施同意机制",
            details={"consent_records": context.get("consent_records", 0)}
        )

    def _check_gdpr_minimization(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        data_fields = context.get("data_fields", [])
        required_fields = context.get("required_fields", [])
        excess = set(data_fields) - set(required_fields)
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.COMPLIANT if not excess else ComplianceStatus.NON_COMPLIANT,
            message=f"数据字段: {len(data_fields)}, 必需: {len(required_fields)}, 多余: {len(excess)}",
            details={"excess_fields": list(excess)}
        )

    def _check_iso_access_control(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        has_policy = context.get("has_access_control_policy", False)
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.COMPLIANT if has_policy else ComplianceStatus.NON_COMPLIANT,
            message="已制定访问控制策略" if has_policy else "未制定访问控制策略"
        )

    def _check_iso_password(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        min_length = context.get("password_min_length", 0)
        has_complexity = context.get("password_complexity", False)
        status = ComplianceStatus.COMPLIANT if min_length >= 12 and has_complexity else ComplianceStatus.NON_COMPLIANT
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=status,
            message=f"密码最小长度: {min_length}, 复杂度要求: {has_complexity}"
        )

    def _check_soc2_monitoring(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        has_monitoring = context.get("has_monitoring", False)
        log_retention = context.get("log_retention_days", 0)
        status = ComplianceStatus.COMPLIANT if has_monitoring and log_retention >= 90 else ComplianceStatus.NON_COMPLIANT
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=status,
            message=f"监控: {has_monitoring}, 日志保留: {log_retention}天"
        )

    def _check_pci_data_protection(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        encrypts_cardholder = context.get("encrypts_cardholder_data", False)
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.COMPLIANT if encrypts_cardholder else ComplianceStatus.NON_COMPLIANT,
            message="已加密持卡人数据" if encrypts_cardholder else "未加密持卡人数据"
        )

    def _check_hipaa_access(self, context: Dict[str, Any], rule: ComplianceRule) -> ComplianceFinding:
        has_phi_access_control = context.get("has_phi_access_control", False)
        return ComplianceFinding(
            finding_id=f"finding_{rule.rule_id}",
            rule_id=rule.rule_id,
            status=ComplianceStatus.COMPLIANT if has_phi_access_control else ComplianceStatus.NON_COMPLIANT,
            message="已实施PHI访问控制" if has_phi_access_control else "未实施PHI访问控制"
        )

    def register_handler(self, rule_id: str, handler: Callable) -> None:
        """注册自定义检查处理器"""
        self._check_handlers[rule_id] = handler
        self.logger.info(f"注册检查处理器: {rule_id}")


class RemediationAdvisor:
    """
    整改建议生成器
    根据不合规发现生成整改建议
    """

    def __init__(self):
        self._advice_templates: Dict[str, List[str]] = {}
        self.logger = setup_logger(f"{__name__}.remediation")
        self._init_templates()

    def _init_templates(self) -> None:
        """初始化整改模板"""
        self._advice_templates = {
            "GDPR_001": [
                "实施同意管理系统",
                "记录所有同意操作",
                "提供撤销同意机制"
            ],
            "GDPR_002": [
                "审查数据收集范围",
                "删除非必要数据字段",
                "更新隐私政策"
            ],
            "ISO27001_001": [
                "制定访问控制策略文档",
                "实施角色权限矩阵",
                "定期审查访问权限"
            ],
            "ISO27001_002": [
                "设置最小密码长度为12",
                "启用密码复杂度要求",
                "实施密码过期策略"
            ],
            "SOC2_001": [
                "部署系统监控工具",
                "配置日志收集与保留",
                "设置告警机制"
            ],
            "PCI_DSS_001": [
                "启用持卡人数据加密",
                "实施密钥管理",
                "定期扫描漏洞"
            ],
            "HIPAA_001": [
                "实施PHI访问控制",
                "配置审计日志",
                "员工安全培训"
            ],
        }

    def generate(self, finding: ComplianceFinding, rule: ComplianceRule) -> RemediationAdvice:
        """生成整改建议"""
        steps = self._advice_templates.get(finding.rule_id, ["联系合规团队获取建议"])

        priority_map = {
            ComplianceLevel.CRITICAL: 1,
            ComplianceLevel.HIGH: 2,
            ComplianceLevel.MEDIUM: 3,
            ComplianceLevel.LOW: 4
        }

        advice = RemediationAdvice(
            finding_id=finding.finding_id,
            priority=priority_map.get(rule.level, 5),
            description=f"针对 {rule.title} 的整改建议",
            steps=steps.copy(),
            estimated_effort="1-2周" if rule.level == ComplianceLevel.HIGH else "2-4周",
            resources=["合规团队", "IT团队", "安全团队"]
        )
        self.logger.info(f"生成整改建议: {finding.finding_id}")
        return advice

    def generate_batch(self, findings: List[ComplianceFinding],
                       rule_engine: RuleEngine) -> List[RemediationAdvice]:
        """批量生成整改建议"""
        advices = []
        for finding in findings:
            if finding.status == ComplianceStatus.NON_COMPLIANT:
                rule = rule_engine.get_rule(finding.rule_id)
                if rule:
                    advices.append(self.generate(finding, rule))
        return sorted(advices, key=lambda x: x.priority)


class ComplianceReporter:
    """
    合规报告生成器
    """

    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
        self.logger = setup_logger(f"{__name__}.reporter")

    def generate_report(self, findings: List[ComplianceFinding],
                        framework: ComplianceFramework) -> ComplianceReport:
        """生成合规报告"""
        non_compliant = sum(1 for f in findings if f.status == ComplianceStatus.NON_COMPLIANT)
        overall = ComplianceStatus.COMPLIANT if non_compliant == 0 else ComplianceStatus.NON_COMPLIANT

        score = sum(1 for f in findings if f.status == ComplianceStatus.COMPLIANT) / max(len(findings), 1)

        report = ComplianceReport(
            report_id=f"report_{framework.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            framework=framework,
            findings=findings,
            overall_status=overall,
            score=score
        )
        self.logger.info(f"生成报告: {report.report_id}, 合规率={score:.2%}")
        return report

    def generate_summary(self, report: ComplianceReport) -> Dict[str, Any]:
        """生成报告摘要"""
        by_status = {}
        by_level = {}
        for finding in report.findings:
            status = finding.status.value
            by_status[status] = by_status.get(status, 0) + 1

            rule = self.rule_engine.get_rule(finding.rule_id)
            if rule:
                level = rule.level.value
                by_level[level] = by_level.get(level, 0) + 1

        return {
            "report_id": report.report_id,
            "framework": report.framework.value,
            "overall_status": report.overall_status.value,
            "compliance_rate": report.compliance_rate,
            "total_findings": len(report.findings),
            "by_status": by_status,
            "by_level": by_level,
            "generated_at": report.generated_at.isoformat()
        }


class ComplianceManager:
    """
    合规管理主类
    整合规则、检查、报告、整改建议
    """

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.checker = ComplianceChecker(self.rule_engine)
        self.advisor = RemediationAdvisor()
        self.reporter = ComplianceReporter(self.rule_engine)
        self.logger = setup_logger(__name__)

    def run_assessment(self, framework: Optional[ComplianceFramework] = None,
                       context: Optional[Dict[str, Any]] = None) -> ComplianceReport:
        """运行合规评估"""
        self.logger.info(f"开始合规评估: framework={framework.value if framework else 'all'}")
        findings = self.checker.check_all(framework, context)
        report = self.reporter.generate_report(findings, framework or ComplianceFramework.CUSTOM)
        return report

    def get_remediation_plan(self, report: ComplianceReport) -> List[RemediationAdvice]:
        """获取整改计划"""
        return self.advisor.generate_batch(report.findings, self.rule_engine)

    def add_custom_rule(self, rule: ComplianceRule, check_handler: Optional[Callable] = None) -> None:
        """添加自定义规则"""
        self.rule_engine.register_rule(rule)
        if check_handler:
            self.checker.register_handler(rule.rule_id, check_handler)

    def get_frameworks(self) -> List[ComplianceFramework]:
        """获取所有框架"""
        frameworks = set()
        for rule in self.rule_engine.get_all_rules():
            frameworks.add(rule.framework)
        return list(frameworks)


def demo_compliance():
    """演示合规检查系统"""
    print("=" * 70)
    print("合规检查系统演示")
    print("=" * 70)
    print()

    manager = ComplianceManager()

    print("1. 合规规则列表:")
    for rule in manager.rule_engine.get_all_rules():
        print(f"   - [{rule.framework.value}] {rule.rule_id}: {rule.title} ({rule.level.value})")
    print()

    print("2. GDPR合规检查:")
    context = {
        "has_consent_mechanism": True,
        "consent_records": 150,
        "data_fields": ["name", "email", "phone", "address"],
        "required_fields": ["name", "email"]
    }
    report = manager.run_assessment(ComplianceFramework.GDPR, context)
    print(f"   总体状态: {report.overall_status.value}")
    print(f"   合规率: {report.compliance_rate:.2%}")
    for finding in report.findings:
        print(f"   - {finding.rule_id}: {finding.status.value} - {finding.message}")
    print()

    print("3. ISO27001合规检查:")
    context = {
        "has_access_control_policy": True,
        "password_min_length": 8,
        "password_complexity": False
    }
    report = manager.run_assessment(ComplianceFramework.ISO27001, context)
    print(f"   总体状态: {report.overall_status.value}")
    print(f"   合规率: {report.compliance_rate:.2%}")
    for finding in report.findings:
        print(f"   - {finding.rule_id}: {finding.status.value} - {finding.message}")
    print()

    print("4. 整改建议:")
    advices = manager.get_remediation_plan(report)
    for advice in advices:
        print(f"   - [优先级{advice.priority}] {advice.description}")
        for step in advice.steps:
            print(f"     * {step}")
    print()

    print("5. 报告摘要:")
    summary = manager.reporter.generate_summary(report)
    print(f"   报告ID: {summary['report_id']}")
    print(f"   按状态: {summary['by_status']}")
    print(f"   按级别: {summary['by_level']}")
    print()

    print("=" * 70)
    print("合规检查系统演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_compliance()
