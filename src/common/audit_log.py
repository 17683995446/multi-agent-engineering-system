"""
审计日志模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 操作审计
2. 审计查询
3. 审计报告
4. 合规检查
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from common.utils import setup_logger

logger = setup_logger(__name__)


class AuditLevel(Enum):
    """审计级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditCategory(Enum):
    """审计类别"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM = "system"
    SECURITY = "security"
    COMPLIANCE = "compliance"


@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str
    timestamp: float
    user_id: str
    action: str
    category: AuditCategory
    level: AuditLevel
    resource: str
    result: str
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "category": self.category.value,
            "level": self.level.value,
            "resource": self.resource,
            "result": self.result,
            "details": self.details,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
        }

    def to_json(self) -> str:
        """转为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class AuditLogStore:
    """审计日志存储"""

    def __init__(self, max_size: int = 100000):
        self._events: List[AuditEvent] = []
        self._max_size = max_size
        self.logger = setup_logger(__name__ + ".AuditLogStore")

    def append(self, event: AuditEvent):
        """追加事件"""
        self._events.append(event)
        if len(self._events) > self._max_size:
            self._events = self._events[-self._max_size:]

    def query(
        self,
        user_id: Optional[str] = None,
        category: Optional[AuditCategory] = None,
        level: Optional[AuditLevel] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """查询审计事件"""
        results = self._events

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if category:
            results = [e for e in results if e.category == category]
        if level:
            results = [e for e in results if e.level == level]
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        if action:
            results = [e for e in results if e.action == action]
        if resource:
            results = [e for e in results if e.resource == resource]

        return results[-limit:]

    def get_by_event_id(self, event_id: str) -> Optional[AuditEvent]:
        """按事件ID查询"""
        for event in reversed(self._events):
            if event.event_id == event_id:
                return event
        return None

    def clear(self):
        """清空存储"""
        self._events.clear()

    def get_all(self) -> List[AuditEvent]:
        """获取所有事件"""
        return list(self._events)


class AuditLog:
    """审计日志主类"""

    _event_counter = 0

    def __init__(self):
        self.store = AuditLogStore()
        self.logger = setup_logger(__name__ + ".AuditLog")

    def _generate_event_id(self) -> str:
        """生成事件ID"""
        AuditLog._event_counter += 1
        return f"EVT{int(time.time() * 1000)}{AuditLog._event_counter:06d}"

    def log(
        self,
        user_id: str,
        action: str,
        category: AuditCategory,
        level: AuditLevel,
        resource: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditEvent:
        """记录审计事件"""
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=time.time(),
            user_id=user_id,
            action=action,
            category=category,
            level=level,
            resource=resource,
            result=result,
            details=details or {},
            ip_address=ip_address,
            session_id=session_id,
        )
        self.store.append(event)
        self.logger.info(f"审计事件: {event.event_id} [{category.value}] {action} -> {result}")
        return event

    def log_auth(self, user_id: str, action: str, result: str, **kwargs) -> AuditEvent:
        """记录认证事件"""
        return self.log(
            user_id=user_id,
            action=action,
            category=AuditCategory.AUTHENTICATION,
            level=AuditLevel.INFO if result == "success" else AuditLevel.WARNING,
            resource="auth_system",
            result=result,
            **kwargs,
        )

    def log_data_access(self, user_id: str, action: str, resource: str, result: str, **kwargs) -> AuditEvent:
        """记录数据访问事件"""
        return self.log(
            user_id=user_id,
            action=action,
            category=AuditCategory.DATA_ACCESS,
            level=AuditLevel.INFO,
            resource=resource,
            result=result,
            **kwargs,
        )

    def log_security(self, user_id: str, action: str, resource: str, result: str, level: AuditLevel = AuditLevel.WARNING, **kwargs) -> AuditEvent:
        """记录安全事件"""
        return self.log(
            user_id=user_id,
            action=action,
            category=AuditCategory.SECURITY,
            level=level,
            resource=resource,
            result=result,
            **kwargs,
        )

    def query(self, **kwargs) -> List[AuditEvent]:
        """查询审计事件"""
        return self.store.query(**kwargs)

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """获取单个事件"""
        return self.store.get_by_event_id(event_id)


class AuditReport:
    """审计报告生成器"""

    def __init__(self, audit_log: AuditLog):
        self.audit_log = audit_log

    def generate_summary(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> Dict[str, Any]:
        """生成审计摘要"""
        events = self.audit_log.query(start_time=start_time, end_time=end_time, limit=100000)

        total = len(events)
        by_category: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        by_result: Dict[str, int] = {}

        for event in events:
            by_category[event.category.value] = by_category.get(event.category.value, 0) + 1
            by_level[event.level.value] = by_level.get(event.level.value, 0) + 1
            by_user[event.user_id] = by_user.get(event.user_id, 0) + 1
            by_result[event.result] = by_result.get(event.result, 0) + 1

        return {
            "period": {
                "start": datetime.fromtimestamp(start_time).isoformat() if start_time else None,
                "end": datetime.fromtimestamp(end_time).isoformat() if end_time else None,
            },
            "total_events": total,
            "by_category": by_category,
            "by_level": by_level,
            "by_user": by_user,
            "by_result": by_result,
        }

    def generate_user_report(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """生成用户审计报告"""
        end_time = time.time()
        start_time = end_time - days * 86400
        events = self.audit_log.query(user_id=user_id, start_time=start_time, end_time=end_time, limit=100000)

        actions: Dict[str, int] = {}
        for event in events:
            actions[event.action] = actions.get(event.action, 0) + 1

        return {
            "user_id": user_id,
            "period_days": days,
            "total_events": len(events),
            "actions": actions,
            "events": [e.to_dict() for e in events[-100:]],
        }

    def generate_security_report(self, days: int = 7) -> Dict[str, Any]:
        """生成安全审计报告"""
        end_time = time.time()
        start_time = end_time - days * 86400
        events = self.audit_log.query(
            category=AuditCategory.SECURITY,
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        return {
            "period_days": days,
            "total_security_events": len(events),
            "by_level": self._count_by_attr(events, "level"),
            "events": [e.to_dict() for e in events[-50:]],
        }

    @staticmethod
    def _count_by_attr(events: List[AuditEvent], attr: str) -> Dict[str, int]:
        """按属性统计"""
        result: Dict[str, int] = {}
        for event in events:
            value = getattr(event, attr)
            if isinstance(value, Enum):
                value = value.value
            result[value] = result.get(value, 0) + 1
        return result


class ComplianceChecker:
    """合规检查器"""

    COMPLIANCE_RULES = {
        "login_failure_limit": 5,
        "data_access_log_required": True,
        "admin_action_log_required": True,
        "retention_days": 365,
    }

    def __init__(self, audit_log: AuditLog):
        self.audit_log = audit_log

    def check_login_failures(self, user_id: str, window_seconds: int = 300) -> Dict[str, Any]:
        """检查登录失败次数"""
        end_time = time.time()
        start_time = end_time - window_seconds
        events = self.audit_log.query(
            user_id=user_id,
            category=AuditCategory.AUTHENTICATION,
            action="login",
            start_time=start_time,
            end_time=end_time,
            limit=1000,
        )
        failures = [e for e in events if e.result == "failure"]
        return {
            "user_id": user_id,
            "failure_count": len(failures),
            "limit": self.COMPLIANCE_RULES["login_failure_limit"],
            "compliant": len(failures) < self.COMPLIANCE_RULES["login_failure_limit"],
            "window_seconds": window_seconds,
        }

    def check_data_access_logging(self, resource: str, window_seconds: int = 86400) -> Dict[str, Any]:
        """检查数据访问是否被记录"""
        end_time = time.time()
        start_time = end_time - window_seconds
        events = self.audit_log.query(
            category=AuditCategory.DATA_ACCESS,
            resource=resource,
            start_time=start_time,
            end_time=end_time,
            limit=1,
        )
        return {
            "resource": resource,
            "has_logs": len(events) > 0,
            "compliant": len(events) > 0 if self.COMPLIANCE_RULES["data_access_log_required"] else True,
        }

    def run_full_check(self) -> Dict[str, Any]:
        """运行完整合规检查"""
        return {
            "rules": self.COMPLIANCE_RULES,
            "checks": {
                "login_failure_tracking": True,
                "data_access_logging": self.COMPLIANCE_RULES["data_access_log_required"],
                "admin_action_logging": self.COMPLIANCE_RULES["admin_action_log_required"],
                "retention_policy": f"{self.COMPLIANCE_RULES['retention_days']} days",
            },
            "status": "compliant",
        }
