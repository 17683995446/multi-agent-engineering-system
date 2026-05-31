"""
阶段83验证脚本：访问控制模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.access_control import (
    AccessControl,
    AccessLogEntry,
    AccessLogger,
    Permission,
    RBACEnforcer,
    Role,
    RoleManager,
    User,
)


def test_role_permissions():
    """测试角色默认权限"""
    admin_perms = RoleManager().get_role_permissions(Role.ADMIN)
    assert Permission.READ in admin_perms
    assert Permission.WRITE in admin_perms
    assert Permission.DELETE in admin_perms

    viewer_perms = RoleManager().get_role_permissions(Role.VIEWER)
    assert Permission.READ in viewer_perms
    assert Permission.WRITE not in viewer_perms
    print("✓ 角色默认权限测试通过")


def test_user_permissions():
    """测试用户权限聚合"""
    user = User(
        user_id="u1",
        username="test",
        roles=[Role.VIEWER, Role.EDITOR],
    )
    perms = user.get_all_permissions()
    assert Permission.READ in perms
    assert Permission.WRITE in perms
    assert Permission.DELETE not in perms
    print("✓ 用户权限聚合测试通过")


def test_role_manager_custom():
    """测试自定义角色管理"""
    rm = RoleManager()
    assert rm.create_role("custom_role", [Permission.READ, Permission.VIEW]) is True
    assert rm.create_role("custom_role", [Permission.READ]) is False

    perms = rm.get_role_permissions("custom_role")
    assert Permission.READ in perms

    assert rm.delete_role("custom_role") is True
    assert rm.delete_role("custom_role") is False
    print("✓ 自定义角色管理测试通过")


def test_role_permission_modify():
    """测试角色权限修改"""
    rm = RoleManager()
    rm.add_permission_to_role(Role.VIEWER, Permission.WRITE)
    perms = rm.get_role_permissions(Role.VIEWER)
    assert Permission.WRITE in perms

    rm.remove_permission_from_role(Role.VIEWER, Permission.WRITE)
    perms = rm.get_role_permissions(Role.VIEWER)
    assert Permission.WRITE not in perms
    print("✓ 角色权限修改测试通过")


def test_access_logger():
    """测试访问日志"""
    logger = AccessLogger()
    entry1 = AccessLogEntry(user_id="u1", resource="file1", action="read", granted=True)
    entry2 = AccessLogEntry(user_id="u2", resource="file1", action="write", granted=False)
    logger.log(entry1)
    logger.log(entry2)

    logs = logger.get_logs(limit=10)
    assert len(logs) == 2

    u1_logs = logger.get_logs(user_id="u1")
    assert len(u1_logs) == 1

    denied = logger.get_denied_logs()
    assert len(denied) == 1
    assert denied[0].granted is False

    stats = logger.get_stats()
    assert stats["total"] == 2
    assert stats["granted"] == 1
    assert stats["denied"] == 1
    print("✓ 访问日志测试通过")


def test_rbac_enforcer():
    """测试RBAC执行器"""
    enforcer = RBACEnforcer()
    user = User(user_id="u1", username="admin", roles=[Role.ADMIN])

    assert enforcer.check_permission(user, Permission.READ, "doc1") is True
    assert enforcer.check_permission(user, Permission.DELETE, "doc1") is True

    guest = User(user_id="u2", username="guest", roles=[Role.GUEST])
    assert enforcer.check_permission(guest, Permission.WRITE, "doc1") is False
    print("✓ RBAC执行器测试通过")


def test_inactive_user():
    """测试禁用用户"""
    enforcer = RBACEnforcer()
    user = User(user_id="u1", username="admin", roles=[Role.ADMIN], is_active=False)
    assert enforcer.check_permission(user, Permission.READ) is False
    print("✓ 禁用用户测试通过")


def test_check_any_all_permissions():
    """测试任一/所有权限检查"""
    enforcer = RBACEnforcer()
    user = User(user_id="u1", username="viewer", roles=[Role.VIEWER])

    assert enforcer.check_any_permission(user, [Permission.READ, Permission.WRITE]) is True
    assert enforcer.check_all_permissions(user, [Permission.READ, Permission.WRITE]) is False
    assert enforcer.check_all_permissions(user, [Permission.READ, Permission.VIEW]) is True
    print("✓ 任一/所有权限检查测试通过")


def test_require_permission():
    """测试权限要求异常"""
    enforcer = RBACEnforcer()
    user = User(user_id="u1", username="guest", roles=[Role.GUEST])

    try:
        enforcer.require_permission(user, Permission.WRITE)
        assert False, "应抛出异常"
    except PermissionError as e:
        assert "缺少权限" in str(e)
    print("✓ 权限要求异常测试通过")


def test_access_control_full():
    """测试访问控制全流程"""
    ac = AccessControl()
    ac.create_user("u1", "Alice", roles=[Role.EDITOR])
    ac.create_user("u2", "Bob", roles=[Role.VIEWER])

    assert ac.check_access("u1", Permission.WRITE, "doc1") is True
    assert ac.check_access("u2", Permission.WRITE, "doc1") is False
    assert ac.check_access("u999", Permission.READ) is False

    ac.assign_role("u2", Role.EDITOR)
    assert ac.check_access("u2", Permission.WRITE, "doc1") is True

    ac.revoke_role("u2", Role.EDITOR)
    assert ac.check_access("u2", Permission.WRITE, "doc1") is False
    print("✓ 访问控制全流程测试通过")


def test_access_logs_query():
    """测试访问日志查询"""
    ac = AccessControl()
    ac.create_user("u1", "Alice", roles=[Role.ADMIN])
    ac.create_user("u2", "Bob", roles=[Role.GUEST])

    ac.check_access("u1", Permission.READ, "doc1")
    ac.check_access("u2", Permission.WRITE, "doc1")

    logs = ac.get_access_logs(limit=10)
    assert len(logs) >= 2

    u1_logs = ac.get_access_logs(user_id="u1", limit=10)
    assert len(u1_logs) >= 1
    print("✓ 访问日志查询测试通过")


def test_stats():
    """测试统计信息"""
    ac = AccessControl()
    ac.create_user("u1", "Alice", roles=[Role.ADMIN])
    stats = ac.get_stats()
    assert stats["users"] == 1
    assert "super_admin" in stats["roles"]
    assert "access_stats" in stats
    print("✓ 统计信息测试通过")


def main():
    print("=" * 60)
    print("阶段83验证：访问控制模块")
    print("=" * 60)

    test_role_permissions()
    test_user_permissions()
    test_role_manager_custom()
    test_role_permission_modify()
    test_access_logger()
    test_rbac_enforcer()
    test_inactive_user()
    test_check_any_all_permissions()
    test_require_permission()
    test_access_control_full()
    test_access_logs_query()
    test_stats()

    print("=" * 60)
    print("阶段83验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
