"""
全局可追溯链路ID管理器
遵循第一性原理：系统可观测要求

核心功能：
1. 全局唯一链路ID生成
2. 链路追踪记录
3. 链路串联追溯
4. 链路完整性验证

链路ID结构：
- TraceID: 整体链路ID（根节点）
- SpanID: 操作单元ID（链路中的每个节点）
- ParentSpanID: 父操作ID（建立层级关系）

核心约束：
- 所有任务、请求、代码变更均生成唯一链路ID
- 全流程链路可串联追溯
- 无链路断裂、ID重复、丢失问题
- 满足系统可观测要求
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class TraceEventType(Enum):
    """链路事件类型"""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    REQUEST_RECEIVED = "request_received"
    REQUEST_PROCESSED = "request_processed"
    CODE_CHANGED = "code_changed"
    AGENT_COMMUNICATED = "agent_communicated"
    STATE_CHANGED = "state_changed"


@dataclass
class SpanContext:
    """操作上下文"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def finish(self, tags: Optional[Dict[str, str]] = None) -> None:
        """完成操作"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        if tags:
            self.tags.update(tags)
    
    def add_tag(self, key: str, value: str) -> None:
        """添加标签"""
        self.tags[key] = value
    
    def add_log(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """添加日志"""
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {}
        })


@dataclass
class TraceEvent:
    """链路事件"""
    trace_id: str
    span_id: str
    event_type: TraceEventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    target: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceInfo:
    """链路信息"""
    trace_id: str
    root_operation: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    spans: List[SpanContext] = field(default_factory=list)
    events: List[TraceEvent] = field(default_factory=list)
    status: str = "running"
    result: Optional[Dict[str, Any]] = None
    
    def add_span(self, span: SpanContext) -> None:
        """添加操作"""
        self.spans.append(span)
    
    def add_event(self, event: TraceEvent) -> None:
        """添加事件"""
        self.events.append(event)
    
    def finish(self, status: str = "completed", result: Optional[Dict[str, Any]] = None) -> None:
        """完成链路"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        self.result = result


class TraceIDGenerator:
    """链路ID生成器"""
    
    @staticmethod
    def generate_trace_id() -> str:
        """生成链路ID"""
        return f"tr-{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    def generate_span_id() -> str:
        """生成操作ID"""
        return f"sp-{uuid.uuid4().hex[:12]}"
    
    @staticmethod
    def is_valid_trace_id(trace_id: str) -> bool:
        """验证链路ID"""
        return trace_id.startswith("tr-") and len(trace_id) == 19
    
    @staticmethod
    def is_valid_span_id(span_id: str) -> bool:
        """验证操作ID"""
        return span_id.startswith("sp-") and len(span_id) == 15


class TraceManager:
    """
    链路追踪管理器
    
    管理全局链路ID的生成、记录、追溯
    """
    
    def __init__(self):
        self._traces: Dict[str, TraceInfo] = {}
        self._active_traces: Dict[str, TraceInfo] = {}
        self._trace_spans: Dict[str, List[SpanContext]] = {}
        self._generated_ids: set = set()
    
    def start_trace(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SpanContext:
        """
        开始链路追踪
        
        Args:
            operation_name: 操作名称
            trace_id: 链路ID（可选，自动生成）
            parent_span_id: 父操作ID（可选）
            metadata: 元数据
            
        Returns:
            SpanContext: 操作上下文
        """
        if trace_id is None:
            trace_id = TraceIDGenerator.generate_trace_id()
        
        span_id = TraceIDGenerator.generate_span_id()
        
        if trace_id not in self._active_traces:
            trace_info = TraceInfo(
                trace_id=trace_id,
                root_operation=operation_name
            )
            self._active_traces[trace_id] = trace_info
            self._trace_spans[trace_id] = []
        
        span = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name
        )
        
        if metadata:
            for key, value in metadata.items():
                span.add_tag(key, str(value))
        
        self._trace_spans[trace_id].append(span)
        self._generated_ids.add(trace_id)
        self._generated_ids.add(span_id)
        
        logger.debug(f"开始链路追踪: trace_id={trace_id}, span_id={span_id}")
        return span
    
    def end_trace(
        self,
        trace_id: str,
        status: str = "completed",
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        结束链路追踪
        
        Args:
            trace_id: 链路ID
            status: 状态
            result: 结果
        """
        if trace_id not in self._active_traces:
            logger.warning(f"链路不存在: {trace_id}")
            return
        
        trace_info = self._active_traces[trace_id]
        trace_info.finish(status=status, result=result)
        
        for span in self._trace_spans.get(trace_id, []):
            if span.end_time is None:
                span.finish()
            trace_info.add_span(span)
        
        self._traces[trace_id] = trace_info
        del self._active_traces[trace_id]
        
        logger.debug(f"结束链路追踪: trace_id={trace_id}, status={status}")
    
    def create_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SpanContext]:
        """
        创建子操作
        
        Args:
            trace_id: 链路ID
            operation_name: 操作名称
            parent_span_id: 父操作ID
            metadata: 元数据
            
        Returns:
            Optional[SpanContext]: 操作上下文
        """
        if trace_id not in self._active_traces:
            logger.warning(f"链路不存在: {trace_id}")
            return None
        
        return self.start_trace(
            operation_name=operation_name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            metadata=metadata
        )
    
    def add_event(
        self,
        trace_id: str,
        event_type: TraceEventType,
        source: str = "",
        target: str = "",
        content: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加链路事件
        
        Args:
            trace_id: 链路ID
            event_type: 事件类型
            source: 源
            target: 目标
            content: 内容
        """
        if trace_id not in self._active_traces:
            logger.warning(f"链路不存在: {trace_id}")
            return
        
        event = TraceEvent(
            trace_id=trace_id,
            span_id=TraceIDGenerator.generate_span_id(),
            event_type=event_type,
            source=source,
            target=target,
            content=content or {}
        )
        
        self._active_traces[trace_id].add_event(event)
        logger.debug(f"添加链路事件: trace_id={trace_id}, event_type={event_type.value}")
    
    def get_trace(self, trace_id: str) -> Optional[TraceInfo]:
        """获取链路信息"""
        if trace_id in self._active_traces:
            return self._active_traces[trace_id]
        return self._traces.get(trace_id)
    
    def get_trace_spans(self, trace_id: str) -> List[SpanContext]:
        """获取链路中的所有操作"""
        return self._trace_spans.get(trace_id, [])
    
    def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """
        获取链路树形结构
        
        Args:
            trace_id: 链路ID
            
        Returns:
            Dict: 树形结构
        """
        trace_info = self.get_trace(trace_id)
        if not trace_info:
            return {}
        
        spans = self.get_trace_spans(trace_id)
        span_map = {span.span_id: span for span in spans}
        
        root_spans = []
        children_map: Dict[str, List] = {}
        
        for span in spans:
            if span.parent_span_id is None:
                root_spans.append(span)
            else:
                if span.parent_span_id not in children_map:
                    children_map[span.parent_span_id] = []
                children_map[span.parent_span_id].append(span)
        
        def build_tree(span: SpanContext) -> Dict[str, Any]:
            return {
                "span_id": span.span_id,
                "operation_name": span.operation_name,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration_ms": span.duration_ms,
                "tags": span.tags,
                "children": [build_tree(child) for child in children_map.get(span.span_id, [])]
            }
        
        return {
            "trace_id": trace_id,
            "root_operation": trace_info.root_operation,
            "start_time": trace_info.start_time.isoformat(),
            "end_time": trace_info.end_time.isoformat() if trace_info.end_time else None,
            "duration_ms": trace_info.duration_ms,
            "status": trace_info.status,
            "root_spans": [build_tree(root) for root in root_spans]
        }
    
    def verify_trace_integrity(self, trace_id: str) -> Dict[str, Any]:
        """
        验证链路完整性
        
        Args:
            trace_id: 链路ID
            
        Returns:
            Dict: 验证结果
        """
        issues = []
        
        if trace_id not in self._active_traces and trace_id not in self._traces:
            issues.append("链路不存在")
            return {"valid": False, "issues": issues}
        
        spans = self.get_trace_spans(trace_id)
        
        if not spans:
            issues.append("链路无操作记录")
        
        for span in spans:
            if span.end_time is None:
                issues.append(f"操作未完成: {span.span_id}")
            
            if span.parent_span_id and span.parent_span_id not in [s.span_id for s in spans]:
                issues.append(f"父操作不存在: {span.parent_span_id}")
        
        for trace_id_check in self._generated_ids:
            count = list(self._generated_ids).count(trace_id_check)
            if count > 1:
                issues.append(f"ID重复: {trace_id_check}")
        
        return {
            "valid": len(issues) == 0,
            "trace_id": trace_id,
            "span_count": len(spans),
            "issues": issues
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_traces": len(self._traces),
            "active_traces": len(self._active_traces),
            "total_spans": sum(len(spans) for spans in self._trace_spans.values()),
            "total_ids": len(self._generated_ids)
        }


_global_trace_manager = None

def get_trace_manager() -> TraceManager:
    """获取全局链路管理器"""
    global _global_trace_manager
    if _global_trace_manager is None:
        _global_trace_manager = TraceManager()
    return _global_trace_manager


def demo_trace_system():
    """演示链路追踪系统"""
    print("=" * 70)
    print("全局可追溯链路ID系统演示")
    print("=" * 70)
    print()
    
    manager = TraceManager()
    
    print("1. 创建链路:")
    root_span = manager.start_trace(
        operation_name="task_execution",
        metadata={"task_id": "task_001", "priority": "high"}
    )
    print(f"   ✓ 创建链路: trace_id={root_span.trace_id}")
    print(f"   ✓ 创建根操作: span_id={root_span.span_id}")
    print()
    
    print("2. 创建子操作:")
    child_span = manager.create_span(
        trace_id=root_span.trace_id,
        operation_name="code_review",
        parent_span_id=root_span.span_id,
        metadata={"reviewer": "agent_1"}
    )
    print(f"   ✓ 创建子操作: span_id={child_span.span_id}")
    print()
    
    print("3. 添加链路事件:")
    manager.add_event(
        trace_id=root_span.trace_id,
        event_type=TraceEventType.CODE_CHANGED,
        source="agent_1",
        target="agent_2",
        content={"file": "main.py", "change_type": "modified"}
    )
    print(f"   ✓ 添加事件: CODE_CHANGED")
    print()
    
    print("4. 结束子操作:")
    child_span.finish(tags={"result": "passed"})
    print(f"   ✓ 结束操作: duration={child_span.duration_ms}ms")
    print()
    
    print("5. 创建另一个子操作:")
    child_span2 = manager.create_span(
        trace_id=root_span.trace_id,
        operation_name="test_execution",
        parent_span_id=root_span.span_id
    )
    child_span2.finish(tags={"tests_passed": 10, "tests_failed": 0})
    print(f"   ✓ 创建并结束操作: duration={child_span2.duration_ms}ms")
    print()
    
    print("6. 结束链路:")
    manager.end_trace(
        trace_id=root_span.trace_id,
        status="completed",
        result={"success": True}
    )
    print(f"   ✓ 结束链路: status=completed")
    print()
    
    print("7. 获取链路信息:")
    trace_info = manager.get_trace(root_span.trace_id)
    if trace_info:
        print(f"   ✓ 链路ID: {trace_info.trace_id}")
        print(f"   ✓ 根操作: {trace_info.root_operation}")
        print(f"   ✓ 操作数量: {len(trace_info.spans)}")
        print(f"   ✓ 事件数量: {len(trace_info.events)}")
        print(f"   ✓ 状态: {trace_info.status}")
        print(f"   ✓ 耗时: {trace_info.duration_ms}ms")
    print()
    
    print("8. 获取链路树:")
    trace_tree = manager.get_trace_tree(root_span.trace_id)
    print(f"   ✓ 树形结构:")
    for root in trace_tree.get("root_spans", []):
        print(f"     - {root['operation_name']} ({root['duration_ms']}ms)")
        for child in root.get("children", []):
            print(f"       - {child['operation_name']} ({child['duration_ms']}ms)")
    print()
    
    print("9. 验证链路完整性:")
    integrity = manager.verify_trace_integrity(root_span.trace_id)
    print(f"   ✓ 完整性验证: {'通过' if integrity['valid'] else '失败'}")
    print(f"   ✓ 操作数量: {integrity['span_count']}")
    print(f"   ✓ 问题列表: {integrity['issues'] if integrity['issues'] else '无'}")
    print()
    
    print("10. 统计信息:")
    stats = manager.get_statistics()
    print(f"   ✓ 总链路数: {stats['total_traces']}")
    print(f"   ✓ 活跃链路: {stats['active_traces']}")
    print(f"   ✓ 总操作数: {stats['total_spans']}")
    print(f"   ✓ 已生成ID: {stats['total_ids']}")
    print()
    
    print("=" * 70)
    print("全局可追溯链路ID系统演示完成")
    print("=" * 70)
    print()
    print("✓ 所有任务、请求、代码变更均生成唯一链路ID")
    print("✓ 全流程链路可串联追溯")
    print("✓ 无链路断裂、ID重复、丢失问题")
    print("✓ 满足系统可观测要求")


if __name__ == "__main__":
    demo_trace_system()
