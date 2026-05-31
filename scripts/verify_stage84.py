"""
阶段84验证脚本：审计日志模块
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.audit_log import (
    AuditCategory,
    AuditEvent,
    AuditLevel,
    AuditLog,
    AuditLogStore,
    AuditReport,
    ComplianceChecker,
)


def test_audit_event_creation():
    """测试审计事件创建"""
    event = AuditEvent(
        event_id="EVT001",
        timestamp=time.time(),
        user_id="user1",
        action="login",
        category=AuditCategory.AUTHENTICATION,
        level=AuditLevel.INFO,
        resource="auth_system",
        result="success",
    )
    assert event.event_id == "EVT001"
    assert event.user_id == "user1"
    print("✓ 审计事件创建测试通过")


def test_audit_event_serialization():
    """测试审计事件序列化"""
    event = AuditEvent(
        event_id="EVT002",
        timestamp=time.time(),
        user_id="user1",
        action="login",
        category=AuditCategory.AUTHENTICATION,
        level=AuditLevel.INFO,
        resource="auth_system",
        result="success",
    )
    d = event.to_dict()
    assert d["event_id"] == "EVT002"
    assert d["category"] == "authentication"
    assert "datetime" in d

    json_str = event.to_json()
    assert "EVT002" in json_str
    print("✓ 审计事件序列化测试通过")


def test_audit_log_store():
    """测试审计日志存储"""
    store = AuditLogStore()
    event = AuditEvent(
        event_id="EVT003",
        timestamp=time.time(),
        user_id="user1",
        action="read",
        category=AuditCategory.DATA_ACCESS,
        level=AuditLevel.INFO,
        resource="file1",
        result="success",
    )
    store.append(event)
    assert len(store.get_all()) == 1

    result = store.query(user_id="user1")
    assert len(result) == 1

    result = store.query(category=AuditCategory.SECURITY)
    assert len(result) == 0
    print("✓ 审计日志存储测试通过")


def test_audit_log_store_time_range():
    """测试时间范围查询"""
    store = AuditLogStore()
    now = time.time()
    store.append(AuditEvent("EVT1", now - 100, "u1", "a1", AuditCategory.SYSTEM, AuditLevel.INFO, "r1", "ok"))
    store.append(AuditEvent("EVT2", now - 50, "u1", "a2", AuditCategory.SYSTEM, AuditLevel.INFO, "r1", "ok"))
    store.append(AuditEvent("EVT3", now, "u1", "a3", AuditCategory.SYSTEM, AuditLevel.INFO, "r1", "ok"))

    results = store.query(start_time=now - 60, end_time=now)
    assert len(results) == 2
    print("✓ 时间范围查询测试通过")


def test_audit_log_logging():
    """测试审计日志记录"""
    log = AuditLog()
    event = log.log(
        user_id="user1",
        action="delete",
        category=AuditCategory.DATA_MODIFICATION,
        level=AuditLevel.WARNING,
        resource="database",
        result="success",
        details={"table": "users", "rows": 1},
    )
    assert event.event_id.startswith("EVT")
    assert event.details["table"] == "users"

    retrieved = log.get_event(event.event_id)
    assert retrieved is not None
    assert retrieved.action == "delete"
    print("✓ 审计日志记录测试通过")


def test_log_auth():
    """测试认证日志快捷方法"""
    log = AuditLog()
    event = log.log_auth("user1", "login", "success", ip_address="192.168.1.1")
    assert event.category == AuditCategory.AUTHENTICATION
    assert event.level == AuditLevel.INFO
    assert event.ip_address == "192.168.1.1"

    event2 = log.log_auth("user1", "login", "failure")
    assert event2.level == AuditLevel.WARNING
    print("✓ 认证日志测试通过")


def test_log_data_access():
    """测试数据访问日志"""
    log = AuditLog()
    event = log.log_data_access("user1", "read", "customer_db", "success")
    assert event.category == AuditCategory.DATA_ACCESS
    assert event.resource == "customer_db"
    print("✓ 数据访问日志测试通过")


def test_log_security():
    """测试安全日志"""
    log = AuditLog()
    event = log.log_security("user1", "intrusion_detected", "firewall", "blocked", level=AuditLevel.CRITICAL)
    assert event.category == AuditCategory.SECURITY
    assert event.level == AuditLevel.CRITICAL
    print("✓ 安全日志测试通过")


def test_audit_report_summary():
    """测试审计摘要报告"""
    log = AuditLog()
    log.log_auth("u1", "login", "success")
    log.log_auth("u1", "login", "failure")
    log.log_data_access("u1", "read", "db1", "success")
    log.log_security("u2", "alert", "fw", "detected")

    report = AuditReport(log)
    summary = report.generate_summary()
    assert summary["total_events"] == 4
    assert "authentication" in summary["by_category"]
    assert "data_access" in summary["by_category"]
    print("✓ 审计摘要报告测试通过")


def test_audit_report_user():
    """测试用户审计报告"""
    log = AuditLog()
    log.log_auth("u1", "login", "success")
    log.log_data_access("u1", "read", "db1", "success")

    report = AuditReport(log)
    user_report = report.generate_user_report("u1", days=1)
    assert user_report["user_id"] == "u1"
    assert user_report["total_events"] == 2
    assert "login" in user_report["actions"]
    print("✓ 用户审计报告测试通过")


def test_audit_report_security():
    """测试安全审计报告"""
    log = AuditLog()
    log.log_security("u1", "alert1", "fw", "detected", level=AuditLevel.WARNING)
    log.log_security("u2", "alert2", "fw", "blocked", level=AuditLevel.CRITICAL)

    report = AuditReport(log)
    sec_report = report.generate_security_report(days=1)
    assert sec_report["total_security_events"] == 2
    assert "warning" in sec_report["by_level"]
    assert "critical" in sec_report["by_level"]
    print("✓ 安全审计报告测试通过")


def test_compliance_login_failures():
    """测试登录失败合规检查"""
    log = AuditLog()
    checker = ComplianceChecker(log)

    for _ in range(3):
        log.log_auth("u1", "login", "failure")

    result = checker.check_login_failures("u1")
    assert result["failure_count"] == 3
    assert result["compliant"] is True

    for _ in range(3):
        log.log_auth("u1", "login", "failure")

    result = checker.check_login_failures("u1")
    assert result["failure_count"] == 6
    assert result["compliant"] is False
    print("✓ 登录失败合规检查测试通过")


def test_compliance_data_access():
    """测试数据访问日志合规检查"""
    log = AuditLog()
    checker = ComplianceChecker(log)

    result = checker.check_data_access_logging("db1")
    assert result["has_logs"] is False
    assert result["compliant"] is False

    log.log_data_access("u1", "read", "db1", "success")
    result = checker.check_data_access_logging("db1")
    assert result["has_logs"] is True
    assert result["compliant"] is True
    print("✓ 数据访问日志合规检查测试通过")


def test_compliance_full():
    """测试完整合规检查"""
    log = AuditLog()
    checker = ComplianceChecker(log)
    result = checker.run_full_check()
    assert result["status"] == "compliant"
    assert "rules" in result
    assert "checks" in result
    print("✓ 完整合规检查测试通过")


def main():
    print("=" * 60)
    print("阶段84验证：审计日志模块")
    print("=" * 60)

    test_audit_event_creation()
    test_audit_event_serialization()
    test_audit_log_store()
    test_audit_log_store_time_range()
    test_audit_log_logging()
    test_log_auth()
    test_log_data_access()
    test_log_security()
    test_audit_report_summary()
    test_audit_report_user()
    test_audit_report_security()
    test_compliance_login_failures()
    test_compliance_data_access()
    test_compliance_full()

    print("=" * 60)
    print("阶段84验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
