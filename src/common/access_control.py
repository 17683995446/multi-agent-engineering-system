"""
访问控制模块
遵循第一性原理：信息最小熵公理

核心功能：
1. RBAC权限模型
2. 角色管理
3. 权限检查
4. 访问日志
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from common.utils import setup_logger

logger = setup_logger(__name__)


class Permission(Enum):
    """权限枚举"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CREATE = "create"
    UPDATE = "update"
    VIEW = "view"


class Role(Enum):
    """角色枚举"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"
    OPERATOR = "operator"
    AUDITOR = "auditor"


# 角色-权限映射
DEFAULT_ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.EXECUTE, Permission.ADMIN, Permission.CREATE, Permission.UPDATE, Permission.VIEW},
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.CREATE, Permission.UPDATE, Permission.DELETE, Permission.VIEW},
    Role.EDITOR: {Permission.READ, Permission.WRITE, Permission.CREATE, Permission.UPDATE, Permission.VIEW},
    Role.VIEWER: {Permission.READ, Permission.VIEW},
    Role.GUEST: {Permission.VIEW},
    Role.OPERATOR: {Permission.READ, Permission.EXECUTE, Permission.VIEW},
    Role.AUDITOR: {Permission.READ, Permission.VIEW},
}


@dataclass
class AccessLogEntry:
    """访问日志条目"""
    user_id: str
    resource: str
    action: str
    granted: bool
    timestamp: float = field(default_factory=time.time)
    ip_address: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class User:
    """用户数据类"""
    user_id: str
    username: str
    roles: List[Role] = field(default_factory=list)
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_all_permissions(self) -> Set[Permission]:
        """获取用户的所有权限（角色权限+直接权限）"""
        perms = set(self.permissions)
        for role in self.roles:
            perms.update(DEFAULT_ROLE_PERMISSIONS.get(role, set()))
        return perms


class RoleManager:
    """角色管理器"""

    def __init__(self):
        self._custom_roles: Dict[str, Set[Permission]] = {}
        self._role_permissions: Dict[Role, Set[Permission]] = {k: set(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}
        self.logger = setup_logger(__name__ + ".RoleManager")

    def create_role(self, role_name: str, permissions: List[Permission]) -> bool:
        """创建自定义角色"""
        if role_name in self._custom_roles:
            self.logger.warning(f"角色已存在: {role_name}")
            return False
        self._custom_roles[role_name] = set(permissions)
        self.logger.info(f"创建角色: {role_name}")
        return True

    def delete_role(self, role_name: str) -> bool:
        """删除自定义角色"""
        if role_name in self._custom_roles:
            del self._custom_roles[role_name]
            self.logger.info(f"删除角色: {role_name}")
            return True
        return False

    def get_role_permissions(self, role: Union[Role, str]) -> Set[Permission]:
        """获取角色权限"""
        if isinstance(role, Role):
            return self._role_permissions.get(role, set())
        return self._custom_roles.get(role, set())

    def add_permission_to_role(self, role: Role, permission: Permission) -> bool:
        """为角色添加权限"""
        if role not in self._role_permissions:
            return False
        self._role_permissions[role].add(permission)
        self.logger.info(f"为角色 {role.value} 添加权限 {permission.value}")
        return True

    def remove_permission_from_role(self, role: Role, permission: Permission) -> bool:
        """从角色移除权限"""
        if role not in self._role_permissions:
            return False
        self._role_permissions[role].discard(permission)
        self.logger.info(f"从角色 {role.value} 移除权限 {permission.value}")
        return True

    def list_roles(self) -> List[str]:
        """列出所有角色"""
        builtin = [r.value for r in Role]
        custom = list(self._custom_roles.keys())
        return builtin + custom


class AccessLogger:
    """访问日志记录器"""

    def __init__(self, max_entries: int = 10000):
        self._logs: List[AccessLogEntry] = []
        self._max_entries = max_entries
        self.logger = setup_logger(__name__ + ".AccessLogger")

    def log(self, entry: AccessLogEntry):
        """记录访问日志"""
        self._logs.append(entry)
        if len(self._logs) > self._max_entries:
            self._logs = self._logs[-self._max_entries:]
        status = "允许" if entry.granted else "拒绝"
        self.logger.info(f"访问{status}: {entry.user_id} -> {entry.resource}:{entry.action}")

    def get_logs(self, user_id: Optional[str] = None, resource: Optional[str] = None, limit: int = 100) -> List[AccessLogEntry]:
        """查询访问日志"""
        logs = self._logs
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        if resource:
            logs = [log for log in logs if log.resource == resource]
        return logs[-limit:]

    def get_denied_logs(self, limit: int = 100) -> List[AccessLogEntry]:
        """获取被拒绝的访问日志"""
        return [log for log in self._logs if not log.granted][-limit:]

    def clear_logs(self):
        """清空日志"""
        self._logs.clear()
        self.logger.info("访问日志已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取访问统计"""
        total = len(self._logs)
        granted = sum(1 for log in self._logs if log.granted)
        denied = total - granted
        return {
            "total": total,
            "granted": granted,
            "denied": denied,
            "denial_rate": denied / total if total > 0 else 0.0,
        }


class RBACEnforcer:
    """RBAC权限执行器"""

    def __init__(self):
        self.role_manager = RoleManager()
        self.access_logger = AccessLogger()
        self.logger = setup_logger(__name__ + ".RBACEnforcer")

    def check_permission(self, user: User, permission: Permission, resource: str = "") -> bool:
        """检查用户是否有指定权限"""
        if not user.is_active:
            self._log_access(user, resource, permission.value, False, "用户已禁用")
            return False

        user_perms = user.get_all_permissions()
        granted = permission in user_perms

        if not granted:
            self._log_access(user, resource, permission.value, False, "权限不足")
        else:
            self._log_access(user, resource, permission.value, True)

        return granted

    def check_any_permission(self, user: User, permissions: List[Permission], resource: str = "") -> bool:
        """检查用户是否有任一权限"""
        return any(self.check_permission(user, p, resource) for p in permissions)

    def check_all_permissions(self, user: User, permissions: List[Permission], resource: str = "") -> bool:
        """检查用户是否有所有权限"""
        return all(self.check_permission(user, p, resource) for p in permissions)

    def require_permission(self, user: User, permission: Permission, resource: str = ""):
        """要求权限，无权限则抛出异常"""
        if not self.check_permission(user, permission, resource):
            raise PermissionError(f"用户 {user.user_id} 缺少权限: {permission.value}")

    def _log_access(self, user: User, resource: str, action: str, granted: bool, reason: Optional[str] = None):
        """记录访问日志"""
        entry = AccessLogEntry(
            user_id=user.user_id,
            resource=resource,
            action=action,
            granted=granted,
            reason=reason,
        )
        self.access_logger.log(entry)


class AccessControl:
    """访问控制主类"""

    def __init__(self):
        self.enforcer = RBACEnforcer()
        self.users: Dict[str, User] = {}
        self.logger = setup_logger(__name__ + ".AccessControl")

    def create_user(self, user_id: str, username: str, roles: List[Role] = None, permissions: List[Permission] = None) -> User:
        """创建用户"""
        user = User(
            user_id=user_id,
            username=username,
            roles=roles or [],
            permissions=set(permissions or []),
        )
        self.users[user_id] = user
        self.logger.info(f"创建用户: {user_id} ({username})")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        return self.users.get(user_id)

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        if user_id in self.users:
            del self.users[user_id]
            self.logger.info(f"删除用户: {user_id}")
            return True
        return False

    def assign_role(self, user_id: str, role: Role) -> bool:
        """为用户分配角色"""
        user = self.get_user(user_id)
        if not user:
            return False
        if role not in user.roles:
            user.roles.append(role)
            self.logger.info(f"为用户 {user_id} 分配角色 {role.value}")
        return True

    def revoke_role(self, user_id: str, role: Role) -> bool:
        """撤销用户角色"""
        user = self.get_user(user_id)
        if not user:
            return False
        if role in user.roles:
            user.roles.remove(role)
            self.logger.info(f"撤销用户 {user_id} 的角色 {role.value}")
        return True

    def check_access(self, user_id: str, permission: Permission, resource: str = "") -> bool:
        """检查用户访问权限"""
        user = self.get_user(user_id)
        if not user:
            self.logger.warning(f"用户不存在: {user_id}")
            return False
        return self.enforcer.check_permission(user, permission, resource)

    def get_access_logs(self, user_id: Optional[str] = None, limit: int = 100) -> List[AccessLogEntry]:
        """获取访问日志"""
        return self.enforcer.access_logger.get_logs(user_id=user_id, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取访问控制统计"""
        return {
            "users": len(self.users),
            "roles": self.enforcer.role_manager.list_roles(),
            "access_stats": self.enforcer.access_logger.get_stats(),
        }
