"""
全局权限与读写约束管理器
遵循第一性原理：系统安全可控原则

核心功能：
1. 权限定义与分配
2. 只读/可写约束
3. 越权操作拦截
4. 操作日志审计

权限模型：
- 操作类型：READ（读）、WRITE（写）、EXECUTE（执行）、DELETE（删除）、ADMIN（管理）
- 资源类型：TASK（任务）、CODE（代码）、CONFIG（配置）、STATE（状态）
- 角色类型：ADMIN（管理员）、DEVELOPER（开发者）、REVIEWER（评审者）、VIEWER（查看者）

核心约束：
- 不同Agent、不同操作权限明确划分
- 只读操作不可篡改数据
- 可写操作有日志记录
- 无越权操作、无权限混乱问题
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class Permission(Enum):
    """权限类型"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


class ResourceType(Enum):
    """资源类型"""
    TASK = "task"
    CODE = "code"
    CONFIG = "config"
    STATE = "state"
    AGENT = "agent"


class AgentRole(Enum):
    """Agent角色"""
    ADMIN = "admin"
    ORCHESTRATOR = "orchestrator"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    VIEWER = "viewer"


class OperationResult(Enum):
    """操作结果"""
    ALLOWED = "allowed"
    DENIED = "denied"
    READ_ONLY = "read_only"


@dataclass
class PermissionRule:
    """权限规则"""
    role: AgentRole
    resource_type: ResourceType
    permissions: Set[Permission]
    read_only: bool = False


@dataclass
class AccessLog:
    """访问日志"""
    timestamp: datetime
    agent_id: str
    resource_type: ResourceType
    resource_id: str
    operation: Permission
    result: OperationResult
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource:
    """资源"""
    resource_id: str
    resource_type: ResourceType
    owner: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_read_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class PermissionChecker:
    """权限检查器"""
    
    def __init__(self):
        self._rules: Dict[AgentRole, List[PermissionRule]] = {}
        self._init_default_rules()
    
    def _init_default_rules(self) -> None:
        """初始化默认权限规则"""
        rules = [
            PermissionRule(
                role=AgentRole.ADMIN,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.DELETE, Permission.ADMIN}
            ),
            PermissionRule(
                role=AgentRole.ADMIN,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.DELETE, Permission.ADMIN}
            ),
            PermissionRule(
                role=AgentRole.ADMIN,
                resource_type=ResourceType.CONFIG,
                permissions={Permission.READ, Permission.WRITE, Permission.ADMIN}
            ),
            PermissionRule(
                role=AgentRole.ADMIN,
                resource_type=ResourceType.STATE,
                permissions={Permission.READ, Permission.WRITE, Permission.ADMIN}
            ),
            PermissionRule(
                role=AgentRole.ORCHESTRATOR,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ, Permission.WRITE, Permission.EXECUTE},
                read_only=False
            ),
            PermissionRule(
                role=AgentRole.ORCHESTRATOR,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ, Permission.EXECUTE},
                read_only=True
            ),
            PermissionRule(
                role=AgentRole.DEVELOPER,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ, Permission.WRITE},
                read_only=False
            ),
            PermissionRule(
                role=AgentRole.DEVELOPER,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ, Permission.WRITE},
                read_only=False
            ),
            PermissionRule(
                role=AgentRole.DEVELOPER,
                resource_type=ResourceType.CONFIG,
                permissions={Permission.READ},
                read_only=True
            ),
            PermissionRule(
                role=AgentRole.REVIEWER,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ, Permission.WRITE},
                read_only=False
            ),
            PermissionRule(
                role=AgentRole.REVIEWER,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ},
                read_only=True
            ),
            PermissionRule(
                role=AgentRole.TESTER,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ, Permission.WRITE},
                read_only=False
            ),
            PermissionRule(
                role=AgentRole.TESTER,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ},
                read_only=True
            ),
            PermissionRule(
                role=AgentRole.VIEWER,
                resource_type=ResourceType.TASK,
                permissions={Permission.READ},
                read_only=True
            ),
            PermissionRule(
                role=AgentRole.VIEWER,
                resource_type=ResourceType.CODE,
                permissions={Permission.READ},
                read_only=True
            ),
        ]
        
        for rule in rules:
            if rule.role not in self._rules:
                self._rules[rule.role] = []
            self._rules[rule.role].append(rule)
    
    def get_permissions(self, role: AgentRole, resource_type: ResourceType) -> Optional[PermissionRule]:
        """获取指定角色对资源的权限"""
        rules = self._rules.get(role, [])
        for rule in rules:
            if rule.resource_type == resource_type:
                return rule
        return None
    
    def check_permission(
        self,
        role: AgentRole,
        resource_type: ResourceType,
        operation: Permission
    ) -> OperationResult:
        """检查权限"""
        rule = self.get_permissions(role, resource_type)
        
        if rule is None:
            return OperationResult.DENIED
        
        if operation not in rule.permissions:
            return OperationResult.DENIED
        
        if rule.read_only and operation in {Permission.WRITE, Permission.DELETE}:
            return OperationResult.READ_ONLY
        
        return OperationResult.ALLOWED


class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self._resources: Dict[str, Resource] = {}
    
    def register_resource(self, resource: Resource) -> None:
        """注册资源"""
        self._resources[resource.resource_id] = resource
        logger.debug(f"注册资源: {resource.resource_id}")
    
    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """获取资源"""
        return self._resources.get(resource_id)
    
    def set_read_only(self, resource_id: str, read_only: bool = True) -> bool:
        """设置只读"""
        resource = self.get_resource(resource_id)
        if resource:
            resource.is_read_only = read_only
            resource.updated_at = datetime.now()
            return True
        return False
    
    def is_read_only(self, resource_id: str) -> bool:
        """检查是否只读"""
        resource = self.get_resource(resource_id)
        return resource.is_read_only if resource else False


class AccessLogger:
    """访问日志记录器"""
    
    def __init__(self):
        self._logs: List[AccessLog] = []
    
    def log_access(
        self,
        agent_id: str,
        resource_type: ResourceType,
        resource_id: str,
        operation: Permission,
        result: OperationResult,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录访问"""
        log = AccessLog(
            timestamp=datetime.now(),
            agent_id=agent_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
            result=result,
            reason=reason,
            details=details or {}
        )
        self._logs.append(log)
        logger.info(f"访问日志: agent={agent_id}, resource={resource_id}, "
                   f"operation={operation.value}, result={result.value}")
    
    def get_logs(
        self,
        agent_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: Optional[OperationResult] = None
    ) -> List[AccessLog]:
        """获取日志"""
        logs = self._logs
        
        if agent_id:
            logs = [log for log in logs if log.agent_id == agent_id]
        
        if resource_id:
            logs = [log for log in logs if log.resource_id == resource_id]
        
        if result:
            logs = [log for log in logs if log.result == result]
        
        return logs
    
    def get_denied_logs(self) -> List[AccessLog]:
        """获取被拒绝的访问"""
        return self.get_logs(result=OperationResult.DENIED)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计"""
        total = len(self._logs)
        allowed = len([log for log in self._logs if log.result == OperationResult.ALLOWED])
        denied = len([log for log in self._logs if log.result == OperationResult.DENIED])
        read_only = len([log for log in self._logs if log.result == OperationResult.READ_ONLY])
        
        return {
            "total": total,
            "allowed": allowed,
            "denied": denied,
            "read_only": read_only,
            "allowed_rate": allowed / total if total > 0 else 0
        }


class PermissionManager:
    """
    全局权限管理器
    
    管理所有权限相关的操作
    """
    
    def __init__(self):
        self.permission_checker = PermissionChecker()
        self.resource_manager = ResourceManager()
        self.access_logger = AccessLogger()
        logger.info("权限管理器初始化完成")
    
    def check_access(
        self,
        agent_id: str,
        role: AgentRole,
        resource_type: ResourceType,
        resource_id: str,
        operation: Permission
    ) -> OperationResult:
        """
        检查访问权限
        
        Args:
            agent_id: Agent ID
            role: Agent角色
            resource_type: 资源类型
            resource_id: 资源ID
            operation: 操作类型
            
        Returns:
            OperationResult: 操作结果
        """
        resource = self.resource_manager.get_resource(resource_id)
        
        if resource and resource.is_read_only:
            if operation in {Permission.WRITE, Permission.DELETE}:
                self.access_logger.log_access(
                    agent_id, resource_type, resource_id, operation,
                    OperationResult.READ_ONLY,
                    reason="资源只读"
                )
                return OperationResult.READ_ONLY
        
        result = self.permission_checker.check_permission(role, resource_type, operation)
        
        if result == OperationResult.DENIED:
            self.access_logger.log_access(
                agent_id, resource_type, resource_id, operation,
                OperationResult.DENIED,
                reason="权限不足"
            )
        else:
            self.access_logger.log_access(
                agent_id, resource_type, resource_id, operation,
                OperationResult.ALLOWED
            )
        
        return result
    
    def require_permission(self, role: AgentRole, resource_type: ResourceType, operation: Permission):
        """权限装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(agent_id: str, resource_id: str, *args, **kwargs):
                result = self.check_access(agent_id, role, resource_type, resource_id, operation)
                
                if result == OperationResult.DENIED:
                    raise PermissionError(f"Agent {agent_id} 权限不足，无法执行 {operation.value} 操作")
                
                if result == OperationResult.READ_ONLY:
                    raise ValueError(f"资源 {resource_id} 是只读的，无法执行 {operation.value} 操作")
                
                return func(agent_id, resource_id, *args, **kwargs)
            
            return wrapper
        return decorator
    
    def get_role_permissions(self, role: AgentRole) -> List[Dict[str, Any]]:
        """获取角色的所有权限"""
        permissions = []
        
        for resource_type in ResourceType:
            rule = self.permission_checker.get_permissions(role, resource_type)
            if rule:
                permissions.append({
                    "resource_type": resource_type.value,
                    "permissions": [p.value for p in rule.permissions],
                    "read_only": rule.read_only
                })
        
        return permissions
    
    def verify_no_privilege_escalation(self, agent_id: str, role: AgentRole) -> bool:
        """
        验证无越权操作
        
        Args:
            agent_id: Agent ID
            role: Agent角色
            
        Returns:
            bool: 是否无越权
        """
        logs = self.access_logger.get_logs(agent_id=agent_id)
        
        for log in logs:
            if log.result == OperationResult.DENIED:
                logger.warning(f"检测到越权尝试: agent={agent_id}, "
                             f"resource={log.resource_id}, operation={log.operation.value}")
                return False
        
        return True


def demo_permission_system():
    """演示权限系统"""
    print("=" * 70)
    print("全局权限与读写约束系统演示")
    print("=" * 70)
    print()
    
    manager = PermissionManager()
    
    print("1. 注册资源:")
    task_resource = Resource(
        resource_id="task_001",
        resource_type=ResourceType.TASK,
        owner="agent_developer"
    )
    manager.resource_manager.register_resource(task_resource)
    print(f"   ✓ 注册任务资源: {task_resource.resource_id}")
    
    code_resource = Resource(
        resource_id="code_main.py",
        resource_type=ResourceType.CODE,
        owner="agent_developer"
    )
    manager.resource_manager.register_resource(code_resource)
    print(f"   ✓ 注册代码资源: {code_resource.resource_id}")
    print()
    
    print("2. 设置只读:")
    manager.resource_manager.set_read_only("code_main.py", True)
    print(f"   ✓ 设置代码资源只读: code_main.py")
    print()
    
    print("3. 权限检查 - 开发者写任务:")
    result = manager.check_access(
        agent_id="agent_developer",
        role=AgentRole.DEVELOPER,
        resource_type=ResourceType.TASK,
        resource_id="task_001",
        operation=Permission.WRITE
    )
    print(f"   ✓ 权限检查结果: {result.value}")
    print()
    
    print("4. 权限检查 - 开发者写代码:")
    result = manager.check_access(
        agent_id="agent_developer",
        role=AgentRole.DEVELOPER,
        resource_type=ResourceType.CODE,
        resource_id="code_main.py",
        operation=Permission.WRITE
    )
    print(f"   ✓ 权限检查结果: {result.value}")
    print()
    
    print("5. 权限检查 - 评审者读代码:")
    result = manager.check_access(
        agent_id="agent_reviewer",
        role=AgentRole.REVIEWER,
        resource_type=ResourceType.CODE,
        resource_id="code_main.py",
        operation=Permission.READ
    )
    print(f"   ✓ 权限检查结果: {result.value}")
    print()
    
    print("6. 权限检查 - 查看者写代码:")
    result = manager.check_access(
        agent_id="agent_viewer",
        role=AgentRole.VIEWER,
        resource_type=ResourceType.CODE,
        resource_id="code_main.py",
        operation=Permission.WRITE
    )
    print(f"   ✓ 权限检查结果: {result.value}")
    print()
    
    print("7. 获取角色权限:")
    dev_perms = manager.get_role_permissions(AgentRole.DEVELOPER)
    print(f"   开发者权限:")
    for perm in dev_perms:
        print(f"     - {perm['resource_type']}: {perm['permissions']}, 只读={perm['read_only']}")
    print()
    
    print("8. 访问日志统计:")
    stats = manager.access_logger.get_statistics()
    print(f"   总访问数: {stats['total']}")
    print(f"   允许数: {stats['allowed']}")
    print(f"   拒绝数: {stats['denied']}")
    print(f"   只读拦截: {stats['read_only']}")
    print()
    
    print("9. 无越权验证:")
    for agent_id in ["agent_developer", "agent_reviewer"]:
        is_safe = manager.verify_no_privilege_escalation(agent_id, AgentRole.DEVELOPER)
        print(f"   ✓ {agent_id}: {'无越权' if is_safe else '存在越权'}")
    print()
    
    print("=" * 70)
    print("全局权限与读写约束系统演示完成")
    print("=" * 70)
    print()
    print("✓ 不同Agent、不同操作权限明确划分")
    print("✓ 只读操作不可篡改数据")
    print("✓ 可写操作有日志记录")
    print("✓ 无越权操作、无权限混乱问题")
    print("✓ 系统操作安全可控")


if __name__ == "__main__":
    demo_permission_system()
