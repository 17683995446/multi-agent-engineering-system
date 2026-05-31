"""
阶段90验证脚本：安全策略引擎模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.security_policy import (
    PolicyEffect,
    PolicyStatus,
    PolicyCondition,
    PolicyRule,
    PolicyVersion,
    Policy,
    PolicyDecision,
    PolicyExecutionResult,
    PolicyStore,
    PolicyEvaluator,
    PolicyEnforcer,
    PolicyVersionManager,
    SecurityPolicyEngine,
)


def test_policy_condition():
    """测试策略条件"""
    cond = PolicyCondition("role", "eq", "admin")
    assert cond.evaluate({"role": "admin"}) is True
    assert cond.evaluate({"role": "user"}) is False

    cond = PolicyCondition("age", "gte", 18)
    assert cond.evaluate({"age": 20}) is True
    assert cond.evaluate({"age": 16}) is False

    cond = PolicyCondition("ip", "in", ["10.0.0.1", "10.0.0.2"])
    assert cond.evaluate({"ip": "10.0.0.1"}) is True
    assert cond.evaluate({"ip": "10.0.0.3"}) is False
    print("✓ 策略条件测试通过")


def test_policy_rule():
    """测试策略规则"""
    rule = PolicyRule(
        rule_id="r1",
        effect=PolicyEffect.ALLOW,
        conditions=[
            PolicyCondition("role", "eq", "admin"),
            PolicyCondition("action", "eq", "read")
        ]
    )
    assert rule.evaluate({"role": "admin", "action": "read"}) is True
    assert rule.evaluate({"role": "admin", "action": "write"}) is False
    print("✓ 策略规则测试通过")


def test_policy_store():
    """测试策略存储"""
    store = PolicyStore()
    version = PolicyVersion("v1", "p1", "1.0.0", [])
    policy = Policy("p1", "测试策略", "描述", PolicyStatus.ACTIVE, version)
    store.create(policy)
    assert store.get("p1") is not None
    assert len(store.list_all()) == 1
    assert len(store.list_active()) == 1

    store.delete("p1")
    assert store.get("p1") is None
    print("✓ 策略存储测试通过")


def test_policy_evaluator():
    """测试策略评估器"""
    evaluator = PolicyEvaluator()
    version = PolicyVersion("v1", "p1", "1.0.0", [
        PolicyRule("r1", PolicyEffect.ALLOW, [PolicyCondition("action", "eq", "read")])
    ])
    policy = Policy("p1", "测试", "描述", PolicyStatus.ACTIVE, version)
    decisions = evaluator.evaluate(policy, {"action": "read"})
    assert len(decisions) == 1
    assert decisions[0].matched is True
    assert decisions[0].effect == PolicyEffect.ALLOW
    print("✓ 策略评估器测试通过")


def test_policy_enforcer():
    """测试策略执行器"""
    enforcer = PolicyEnforcer()
    decisions = [
        PolicyDecision("p1", "r1", PolicyEffect.ALLOW, True),
    ]
    result = enforcer.enforce(decisions)
    assert result.final_effect == PolicyEffect.ALLOW
    assert result.enforced is True

    decisions = [
        PolicyDecision("p1", "r1", PolicyEffect.DENY, True),
    ]
    result = enforcer.enforce(decisions)
    assert result.final_effect == PolicyEffect.DENY
    print("✓ 策略执行器测试通过")


def test_policy_version_manager():
    """测试策略版本管理器"""
    store = PolicyStore()
    version = PolicyVersion("v1", "p1", "1.0.0", [])
    policy = Policy("p1", "测试", "描述", PolicyStatus.ACTIVE, version, versions=[version])
    store.create(policy)

    vm = PolicyVersionManager(store)
    new_version = vm.create_version("p1", [PolicyRule("r2", PolicyEffect.DENY)], "1.1.0")
    assert new_version is not None
    assert policy.current_version.version_number == "1.1.0"
    assert len(vm.get_version_history("p1")) == 2

    vm.rollback("p1", "1.0.0")
    assert policy.current_version.version_number == "1.0.0"

    comparison = vm.compare_versions("p1", "1.0.0", "1.1.0")
    assert comparison["same_rules"] is False
    print("✓ 策略版本管理器测试通过")


def test_security_policy_engine():
    """测试安全策略引擎主类"""
    engine = SecurityPolicyEngine()
    rules = [
        PolicyRule("allow_read", PolicyEffect.ALLOW, [PolicyCondition("action", "eq", "read")]),
        PolicyRule("deny_delete", PolicyEffect.DENY, [PolicyCondition("action", "eq", "delete")]),
    ]
    engine.define_policy("p1", "测试策略", "描述", rules, priority=10)

    result = engine.evaluate_request({"action": "read"})
    assert result.final_effect == PolicyEffect.ALLOW

    result = engine.evaluate_request({"action": "delete"})
    assert result.final_effect == PolicyEffect.DENY

    result = engine.evaluate_request({"action": "write"})
    assert result.final_effect == PolicyEffect.ALLOW
    print("✓ 安全策略引擎主类测试通过")


def test_policy_activation():
    """测试策略激活/停用"""
    engine = SecurityPolicyEngine()
    rules = [PolicyRule("r1", PolicyEffect.ALLOW, [])]
    engine.define_policy("p1", "测试", "描述", rules)

    engine.deactivate_policy("p1")
    result = engine.evaluate_request({})
    assert result.final_effect == PolicyEffect.ALLOW

    engine.activate_policy("p1")
    result = engine.evaluate_request({})
    assert result.final_effect == PolicyEffect.ALLOW
    print("✓ 策略激活/停用测试通过")


def test_policy_summary():
    """测试策略汇总"""
    engine = SecurityPolicyEngine()
    engine.define_policy("p1", "策略1", "描述", [PolicyRule("r1", PolicyEffect.ALLOW, [])])
    engine.define_policy("p2", "策略2", "描述", [PolicyRule("r2", PolicyEffect.ALLOW, [])])
    engine.deactivate_policy("p2")

    summary = engine.get_policy_summary()
    assert summary["total"] == 2
    assert summary["active"] == 1
    assert summary["inactive"] == 1
    print("✓ 策略汇总测试通过")


def test_custom_effect_handler():
    """测试自定义效果处理器"""
    enforcer = PolicyEnforcer()
    called = []
    def custom_handler(decision):
        called.append(decision.policy_id)
        return {}
    enforcer.register_handler(PolicyEffect.AUDIT, custom_handler)

    decisions = [PolicyDecision("p1", "r1", PolicyEffect.AUDIT, True)]
    enforcer.enforce(decisions)
    assert "p1" in called
    print("✓ 自定义效果处理器测试通过")


def main():
    print("=" * 60)
    print("阶段90验证：安全策略引擎模块")
    print("=" * 60)

    test_policy_condition()
    test_policy_rule()
    test_policy_store()
    test_policy_evaluator()
    test_policy_enforcer()
    test_policy_version_manager()
    test_security_policy_engine()
    test_policy_activation()
    test_policy_summary()
    test_custom_effect_handler()

    print("=" * 60)
    print("阶段90验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
