"""
安全策略引擎模块
职责：策略定义、策略评估、策略执行、策略版本
依赖规则：引用公共层 utils
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable

from common.utils import setup_logger

logger = setup_logger(__name__)


class PolicyEffect(Enum):
    """策略效果"""
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    REQUIRE_MFA = "require_mfa"


class PolicyStatus(Enum):
    """策略状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


@dataclass
class PolicyCondition:
    """策略条件"""
    field: str
    operator: str
    value: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估条件"""
        actual = context.get(self.field)
        if self.operator == "eq":
            return actual == self.value
        elif self.operator == "ne":
            return actual != self.value
        elif self.operator == "gt":
            return actual is not None and actual > self.value
        elif self.operator == "gte":
            return actual is not None and actual >= self.value
        elif self.operator == "lt":
            return actual is not None and actual < self.value
        elif self.operator == "lte":
            return actual is not None and actual <= self.value
        elif self.operator == "in":
            return actual in self.value if isinstance(self.value, (list, set, tuple)) else False
        elif self.operator == "contains":
            return self.value in actual if isinstance(actual, (list, str)) else False
        elif self.operator == "exists":
            return actual is not None
        return False


@dataclass
class PolicyRule:
    """策略规则"""
    rule_id: str
    effect: PolicyEffect
    conditions: List[PolicyCondition] = field(default_factory=list)
    description: str = ""

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估规则：所有条件满足时返回True"""
        return all(cond.evaluate(context) for cond in self.conditions)


@dataclass
class PolicyVersion:
    """策略版本"""
    version_id: str
    policy_id: str
    version_number: str
    rules: List[PolicyRule] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    change_log: str = ""


@dataclass
class Policy:
    """安全策略"""
    policy_id: str
    name: str
    description: str
    status: PolicyStatus
    current_version: PolicyVersion
    versions: List[PolicyVersion] = field(default_factory=list)
    priority: int = 100
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_version(self, version: PolicyVersion) -> None:
        """添加新版本"""
        self.versions.append(version)
        self.current_version = version
        self.updated_at = datetime.now()

    def get_version(self, version_number: str) -> Optional[PolicyVersion]:
        """获取指定版本"""
        for v in self.versions:
            if v.version_number == version_number:
                return v
        return None


@dataclass
class PolicyDecision:
    """策略决策结果"""
    policy_id: str
    rule_id: str
    effect: PolicyEffect
    matched: bool
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""


@dataclass
class PolicyExecutionResult:
    """策略执行结果"""
    request_id: str
    final_effect: PolicyEffect
    decisions: List[PolicyDecision] = field(default_factory=list)
    enforced: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class PolicyStore:
    """
    策略存储
    管理所有策略的CRUD
    """

    def __init__(self):
        self._policies: Dict[str, Policy] = {}
        self.logger = setup_logger(f"{__name__}.store")

    def create(self, policy: Policy) -> None:
        """创建策略"""
        self._policies[policy.policy_id] = policy
        self.logger.info(f"创建策略: {policy.policy_id}")

    def get(self, policy_id: str) -> Optional[Policy]:
        """获取策略"""
        return self._policies.get(policy_id)

    def update(self, policy: Policy) -> None:
        """更新策略"""
        self._policies[policy.policy_id] = policy
        policy.updated_at = datetime.now()
        self.logger.info(f"更新策略: {policy.policy_id}")

    def delete(self, policy_id: str) -> bool:
        """删除策略"""
        if policy_id in self._policies:
            del self._policies[policy_id]
            self.logger.info(f"删除策略: {policy_id}")
            return True
        return False

    def list_all(self) -> List[Policy]:
        """列出所有策略"""
        return list(self._policies.values())

    def list_active(self) -> List[Policy]:
        """列出活跃策略"""
        return [p for p in self._policies.values() if p.status == PolicyStatus.ACTIVE]

    def list_by_tag(self, tag: str) -> List[Policy]:
        """按标签列出策略"""
        return [p for p in self._policies.values() if tag in p.tags]


class PolicyEvaluator:
    """
    策略评估器
    评估策略规则是否匹配上下文
    """

    def __init__(self):
        self.logger = setup_logger(f"{__name__}.evaluator")

    def evaluate(self, policy: Policy, context: Dict[str, Any]) -> List[PolicyDecision]:
        """评估策略"""
        decisions = []
        version = policy.current_version

        for rule in version.rules:
            matched = rule.evaluate(context)
            decision = PolicyDecision(
                policy_id=policy.policy_id,
                rule_id=rule.rule_id,
                effect=rule.effect,
                matched=matched,
                context=context,
                reason=f"规则{'匹配' if matched else '不匹配'}: {rule.description}"
            )
            decisions.append(decision)
            if matched:
                self.logger.info(f"策略规则匹配: {policy.policy_id}/{rule.rule_id} -> {rule.effect.value}")

        return decisions

    def evaluate_all(self, policies: List[Policy], context: Dict[str, Any]) -> List[PolicyDecision]:
        """评估多个策略"""
        all_decisions = []
        for policy in sorted(policies, key=lambda p: p.priority):
            decisions = self.evaluate(policy, context)
            all_decisions.extend(decisions)
        return all_decisions


class PolicyEnforcer:
    """
    策略执行器
    根据评估结果执行策略效果
    """

    def __init__(self):
        self._effect_handlers: Dict[PolicyEffect, Callable] = {}
        self.logger = setup_logger(f"{__name__}.enforcer")
        self._init_default_handlers()

    def _init_default_handlers(self) -> None:
        """初始化默认效果处理器"""
        self._effect_handlers[PolicyEffect.ALLOW] = self._handle_allow
        self._effect_handlers[PolicyEffect.DENY] = self._handle_deny
        self._effect_handlers[PolicyEffect.AUDIT] = self._handle_audit
        self._effect_handlers[PolicyEffect.REQUIRE_MFA] = self._handle_require_mfa

    def enforce(self, decisions: List[PolicyDecision]) -> PolicyExecutionResult:
        """执行策略决策"""
        request_id = f"req_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        matched_decisions = [d for d in decisions if d.matched]

        if not matched_decisions:
            result = PolicyExecutionResult(
                request_id=request_id,
                final_effect=PolicyEffect.ALLOW,
                decisions=decisions,
                enforced=True
            )
            self.logger.info(f"无匹配规则，默认允许: {request_id}")
            return result

        deny_decisions = [d for d in matched_decisions if d.effect == PolicyEffect.DENY]
        if deny_decisions:
            final_effect = PolicyEffect.DENY
        else:
            final_effect = matched_decisions[0].effect

        for decision in matched_decisions:
            handler = self._effect_handlers.get(decision.effect)
            if handler:
                handler(decision)

        result = PolicyExecutionResult(
            request_id=request_id,
            final_effect=final_effect,
            decisions=decisions,
            enforced=True
        )
        self.logger.info(f"策略执行完成: {request_id}, effect={final_effect.value}")
        return result

    def _handle_allow(self, decision: PolicyDecision) -> Dict[str, Any]:
        return {"action": "allow", "policy_id": decision.policy_id}

    def _handle_deny(self, decision: PolicyDecision) -> Dict[str, Any]:
        return {"action": "deny", "policy_id": decision.policy_id, "reason": decision.reason}

    def _handle_audit(self, decision: PolicyDecision) -> Dict[str, Any]:
        return {"action": "audit_log", "policy_id": decision.policy_id, "context": decision.context}

    def _handle_require_mfa(self, decision: PolicyDecision) -> Dict[str, Any]:
        return {"action": "require_mfa", "policy_id": decision.policy_id}

    def register_handler(self, effect: PolicyEffect, handler: Callable) -> None:
        """注册自定义效果处理器"""
        self._effect_handlers[effect] = handler
        self.logger.info(f"注册效果处理器: {effect.value}")


class PolicyVersionManager:
    """
    策略版本管理器
    管理策略的版本历史
    """

    def __init__(self, policy_store: PolicyStore):
        self.policy_store = policy_store
        self.logger = setup_logger(f"{__name__}.version")

    def create_version(self, policy_id: str, rules: List[PolicyRule],
                       version_number: str, created_by: str = "",
                       change_log: str = "") -> Optional[PolicyVersion]:
        """创建新版本"""
        policy = self.policy_store.get(policy_id)
        if not policy:
            return None

        version = PolicyVersion(
            version_id=f"{policy_id}_v{version_number}",
            policy_id=policy_id,
            version_number=version_number,
            rules=rules,
            created_by=created_by,
            change_log=change_log
        )
        policy.add_version(version)
        self.policy_store.update(policy)
        self.logger.info(f"创建策略版本: {policy_id} -> {version_number}")
        return version

    def rollback(self, policy_id: str, version_number: str) -> bool:
        """回滚到指定版本"""
        policy = self.policy_store.get(policy_id)
        if not policy:
            return False

        version = policy.get_version(version_number)
        if not version:
            return False

        policy.current_version = version
        policy.updated_at = datetime.now()
        self.policy_store.update(policy)
        self.logger.info(f"回滚策略版本: {policy_id} -> {version_number}")
        return True

    def get_version_history(self, policy_id: str) -> List[PolicyVersion]:
        """获取版本历史"""
        policy = self.policy_store.get(policy_id)
        return policy.versions if policy else []

    def compare_versions(self, policy_id: str, v1: str, v2: str) -> Dict[str, Any]:
        """比较两个版本"""
        policy = self.policy_store.get(policy_id)
        if not policy:
            return {}

        version1 = policy.get_version(v1)
        version2 = policy.get_version(v2)

        return {
            "version1": v1,
            "version2": v2,
            "rules_count_v1": len(version1.rules) if version1 else 0,
            "rules_count_v2": len(version2.rules) if version2 else 0,
            "same_rules": version1.rules == version2.rules if version1 and version2 else False
        }


class SecurityPolicyEngine:
    """
    安全策略引擎主类
    整合策略存储、评估、执行、版本管理
    """

    def __init__(self):
        self.policy_store = PolicyStore()
        self.evaluator = PolicyEvaluator()
        self.enforcer = PolicyEnforcer()
        self.version_manager = PolicyVersionManager(self.policy_store)
        self.logger = setup_logger(__name__)

    def define_policy(self, policy_id: str, name: str, description: str,
                      rules: List[PolicyRule], priority: int = 100,
                      tags: Optional[List[str]] = None) -> Policy:
        """定义策略"""
        version = PolicyVersion(
            version_id=f"{policy_id}_v1.0.0",
            policy_id=policy_id,
            version_number="1.0.0",
            rules=rules
        )
        policy = Policy(
            policy_id=policy_id,
            name=name,
            description=description,
            status=PolicyStatus.ACTIVE,
            current_version=version,
            versions=[version],
            priority=priority,
            tags=tags or []
        )
        self.policy_store.create(policy)
        return policy

    def evaluate_request(self, context: Dict[str, Any],
                         policy_ids: Optional[List[str]] = None) -> PolicyExecutionResult:
        """评估请求"""
        if policy_ids:
            policies = [self.policy_store.get(pid) for pid in policy_ids]
            policies = [p for p in policies if p and p.status == PolicyStatus.ACTIVE]
        else:
            policies = self.policy_store.list_active()

        decisions = self.evaluator.evaluate_all(policies, context)
        return self.enforcer.enforce(decisions)

    def activate_policy(self, policy_id: str) -> bool:
        """激活策略"""
        policy = self.policy_store.get(policy_id)
        if policy:
            policy.status = PolicyStatus.ACTIVE
            self.policy_store.update(policy)
            return True
        return False

    def deactivate_policy(self, policy_id: str) -> bool:
        """停用策略"""
        policy = self.policy_store.get(policy_id)
        if policy:
            policy.status = PolicyStatus.INACTIVE
            self.policy_store.update(policy)
            return True
        return False

    def get_policy_summary(self) -> Dict[str, Any]:
        """获取策略汇总"""
        policies = self.policy_store.list_all()
        return {
            "total": len(policies),
            "active": len([p for p in policies if p.status == PolicyStatus.ACTIVE]),
            "inactive": len([p for p in policies if p.status == PolicyStatus.INACTIVE]),
            "draft": len([p for p in policies if p.status == PolicyStatus.DRAFT]),
            "by_tag": {}
        }


def demo_security_policy():
    """演示安全策略引擎"""
    print("=" * 70)
    print("安全策略引擎演示")
    print("=" * 70)
    print()

    engine = SecurityPolicyEngine()

    print("1. 定义访问控制策略:")
    rules = [
        PolicyRule(
            rule_id="deny_external_ip",
            effect=PolicyEffect.DENY,
            conditions=[PolicyCondition("source_ip", "in", ["10.0.0.0/8", "192.168.0.0/16"])],
            description="拒绝外部IP访问"
        ),
        PolicyRule(
            rule_id="require_mfa_admin",
            effect=PolicyEffect.REQUIRE_MFA,
            conditions=[PolicyCondition("role", "eq", "admin")],
            description="管理员需要MFA"
        ),
        PolicyRule(
            rule_id="allow_readonly",
            effect=PolicyEffect.ALLOW,
            conditions=[PolicyCondition("action", "eq", "read")],
            description="允许只读操作"
        ),
    ]
    policy = engine.define_policy(
        policy_id="access_control_001",
        name="访问控制策略",
        description="控制对敏感资源的访问",
        rules=rules,
        priority=10,
        tags=["security", "access"]
    )
    print(f"   策略: {policy.name} (ID: {policy.policy_id})")
    print(f"   规则数: {len(policy.current_version.rules)}")
    print()

    print("2. 评估允许请求:")
    context = {
        "source_ip": "10.0.0.1",
        "role": "user",
        "action": "read",
        "resource": "document_1"
    }
    result = engine.evaluate_request(context)
    print(f"   请求上下文: {context}")
    print(f"   最终效果: {result.final_effect.value}")
    for d in result.decisions:
        print(f"   - {d.rule_id}: matched={d.matched}, effect={d.effect.value}")
    print()

    print("3. 评估拒绝请求:")
    context = {
        "source_ip": "172.16.0.1",
        "role": "user",
        "action": "write",
        "resource": "document_1"
    }
    result = engine.evaluate_request(context)
    print(f"   请求上下文: {context}")
    print(f"   最终效果: {result.final_effect.value}")
    for d in result.decisions:
        print(f"   - {d.rule_id}: matched={d.matched}, effect={d.effect.value}")
    print()

    print("4. 策略版本管理:")
    new_rules = rules + [PolicyRule(
        rule_id="audit_sensitive",
        effect=PolicyEffect.AUDIT,
        conditions=[PolicyCondition("resource", "contains", "sensitive")],
        description="审计敏感资源访问"
    )]
    engine.version_manager.create_version(
        "access_control_001",
        new_rules,
        "1.1.0",
        created_by="admin",
        change_log="增加敏感资源审计规则"
    )
    policy = engine.policy_store.get("access_control_001")
    print(f"   当前版本: {policy.current_version.version_number}")
    print(f"   版本历史: {len(policy.versions)} 个")
    print()

    print("5. 策略汇总:")
    summary = engine.get_policy_summary()
    print(f"   总策略: {summary['total']}")
    print(f"   活跃: {summary['active']}")
    print(f"   停用: {summary['inactive']}")
    print()

    print("=" * 70)
    print("安全策略引擎演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_security_policy()
