"""
MVP阶段4: 中央控制Agent
遵循第一性原理：单一职责、状态分离、可扩展性

核心组件：
- CentralControlAgent: 中央控制Agent，负责任务接收、分解、分发、跟踪、汇总
- TaskDispatcher: 任务分发器，根据任务类型选择Agent，管理Agent注册
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import threading

from src.mvp_core.agent_base import AgentBase, MessageBus, Message, MessageType, AgentStatus
from src.mvp_core.htd_decomposer import HTDDecomposer, TaskNode, TaskStatus
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class TaskType(Enum):
    """任务类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    GENERIC = "generic"


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    READY = "ready"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskExecutionRecord:
    """
    任务执行记录

    属性：
    - execution_id: 执行唯一标识
    - requirement: 原始需求
    - task_tree: 任务树
    - status: 执行状态
    - start_time: 开始时间
    - end_time: 结束时间
    - results: 各Agent执行结果
    - errors: 错误记录
    """
    execution_id: str
    requirement: str
    task_tree: Optional[TaskNode] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "requirement": self.requirement,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "results": self.results,
            "errors": self.errors,
            "task_count": self._count_tasks(self.task_tree) if self.task_tree else 0
        }

    def _count_tasks(self, node: TaskNode) -> int:
        """统计任务数量"""
        count = 1
        for child in node.children:
            count += self._count_tasks(child)
        return count


class TaskDispatcher:
    """
    任务分发器

    职责：
    - 根据任务类型选择Agent
    - 管理Agent注册
    - 维护任务类型到Agent的映射
    """

    def __init__(self):
        """初始化任务分发器"""
        self._agents: Dict[str, AgentBase] = {}
        self._task_type_map: Dict[TaskType, List[str]] = {
            task_type: [] for task_type in TaskType
        }
        self._default_agents: List[str] = []
        self._lock = threading.RLock()
        logger.info("任务分发器初始化完成")

    def register_agent(
        self,
        agent: AgentBase,
        task_types: Optional[List[TaskType]] = None,
        is_default: bool = False
    ) -> bool:
        """
        注册Agent

        Args:
            agent: Agent实例
            task_types: 可处理的任务类型列表
            is_default: 是否作为默认Agent
        """
        with self._lock:
            if agent.name in self._agents:
                logger.warning(f"Agent已注册: {agent.name}")
                return False

            self._agents[agent.name] = agent

            if task_types:
                for task_type in task_types:
                    if agent.name not in self._task_type_map[task_type]:
                        self._task_type_map[task_type].append(agent.name)

            if is_default:
                self._default_agents.append(agent.name)

            logger.info(f"Agent注册成功: {agent.name}, 类型: {[t.value for t in (task_types or [])]}")
            return True

    def unregister_agent(self, agent_name: str) -> bool:
        """注销Agent"""
        with self._lock:
            if agent_name not in self._agents:
                return False

            del self._agents[agent_name]

            for task_type in self._task_type_map:
                if agent_name in self._task_type_map[task_type]:
                    self._task_type_map[task_type].remove(agent_name)

            if agent_name in self._default_agents:
                self._default_agents.remove(agent_name)

            logger.info(f"Agent注销成功: {agent_name}")
            return True

    def dispatch(self, task: Optional[TaskNode], task_type: TaskType) -> Optional[str]:
        """
        分发任务到合适的Agent

        Args:
            task: 任务节点
            task_type: 任务类型

        Returns:
            选中的Agent名称，无可用Agent返回None
        """
        with self._lock:
            # 优先选择专门处理该类型的Agent
            candidates = self._task_type_map.get(task_type, [])

            # 如果没有专门Agent，使用默认Agent
            if not candidates:
                candidates = self._default_agents

            # 仍然没有，使用所有已注册Agent
            if not candidates:
                candidates = list(self._agents.keys())

            if not candidates:
                task_name = task.name if task else "unknown"
                logger.error(f"没有可用Agent处理任务: {task_name}")
                return None

            # 选择策略：选择状态为IDLE的Agent，否则选第一个
            selected = None
            for agent_name in candidates:
                agent = self._agents.get(agent_name)
                if agent and agent.status == AgentStatus.IDLE:
                    selected = agent_name
                    break

            if not selected:
                selected = candidates[0]

            # 更新任务分配信息
            if task:
                task.assignee = selected
                logger.info(f"任务分发: {task.name} -> {selected}")
            else:
                logger.info(f"任务分发: unknown -> {selected}")
            return selected

    def get_agent(self, agent_name: str) -> Optional[AgentBase]:
        """获取Agent实例"""
        with self._lock:
            return self._agents.get(agent_name)

    def get_registered_agents(self) -> List[str]:
        """获取已注册的Agent列表"""
        with self._lock:
            return list(self._agents.keys())

    def get_agents_by_type(self, task_type: TaskType) -> List[str]:
        """获取处理特定类型的Agent列表"""
        with self._lock:
            return self._task_type_map.get(task_type, []).copy()


class CentralControlAgent(AgentBase):
    """
    中央控制Agent

    职责：
    - 接收任务需求
    - 调用HTDDecomposer分解任务
    - 根据任务类型分发给合适的Agent
    - 跟踪任务执行状态
    - 汇总执行结果
    """

    def __init__(
        self,
        name: str = "central_control",
        message_bus: Optional[MessageBus] = None,
        decomposer: Optional[HTDDecomposer] = None,
        dispatcher: Optional[TaskDispatcher] = None
    ):
        """初始化中央控制Agent"""
        super().__init__(name, message_bus)
        self.decomposer = decomposer or HTDDecomposer()
        self.dispatcher = dispatcher or TaskDispatcher()
        self._executions: Dict[str, TaskExecutionRecord] = {}
        self._execution_lock = threading.RLock()
        logger.info(f"中央控制Agent初始化: {name}")

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务 - 中央控制的核心流程

        流程：
        1. 接收需求
        2. 分解任务
        3. 分发任务
        4. 跟踪执行
        5. 汇总结果
        """
        requirement = task.get("requirement", "")
        if not requirement:
            return {"success": False, "error": "需求不能为空"}

        execution_id = str(uuid.uuid4())[:8]
        record = TaskExecutionRecord(
            execution_id=execution_id,
            requirement=requirement
        )

        with self._execution_lock:
            self._executions[execution_id] = record

        try:
            # 阶段1: 任务分解
            record.status = ExecutionStatus.DECOMPOSING
            context = task.get("context", {})
            task_tree = self.decomposer.decompose(requirement, context)
            record.task_tree = task_tree
            logger.info(f"[{execution_id}] 任务分解完成")

            # 阶段2: 任务分发
            record.status = ExecutionStatus.DISPATCHING
            task_type = self._detect_task_type(requirement)
            leaf_tasks = self.decomposer.get_leaf_tasks(task_tree)

            for leaf in leaf_tasks:
                agent_name = self.dispatcher.dispatch(leaf, task_type)
                if agent_name:
                    # 发送任务执行消息
                    self.send_message(
                        receiver=agent_name,
                        content={
                            "action": "execute_task",
                            "task_id": leaf.task_id,
                            "task_name": leaf.name,
                            "task_description": leaf.description,
                            "execution_id": execution_id
                        },
                        msg_type=MessageType.REQUEST,
                        correlation_id=execution_id
                    )
                else:
                    record.errors.append(f"无法分发任务: {leaf.name}")

            logger.info(f"[{execution_id}] 任务分发完成")

            # 阶段3: 跟踪执行（简化版：等待消息响应）
            record.status = ExecutionStatus.RUNNING
            self._track_execution(record)

            # 阶段4: 汇总结果
            record.status = ExecutionStatus.COMPLETED
            record.end_time = datetime.now()
            summary = self._summarize_results(record)
            logger.info(f"[{execution_id}] 执行完成")

            return summary

        except Exception as e:
            record.status = ExecutionStatus.FAILED
            record.end_time = datetime.now()
            record.errors.append(str(e))
            logger.error(f"[{execution_id}] 执行失败: {e}")
            return {
                "success": False,
                "execution_id": execution_id,
                "error": str(e),
                "errors": record.errors
            }

    def receive_task(self, requirement: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        接收任务需求

        Args:
            requirement: 任务需求描述
            context: 上下文信息

        Returns:
            执行ID
        """
        execution_id = str(uuid.uuid4())[:8]
        record = TaskExecutionRecord(
            execution_id=execution_id,
            requirement=requirement
        )

        with self._execution_lock:
            self._executions[execution_id] = record

        logger.info(f"[{execution_id}] 接收到任务需求: {requirement[:50]}...")
        return execution_id

    def decompose_task(self, execution_id: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        分解任务

        Args:
            execution_id: 执行ID
            context: 上下文信息

        Returns:
            是否成功
        """
        record = self._get_execution(execution_id)
        if not record:
            logger.error(f"执行记录不存在: {execution_id}")
            return False

        try:
            record.status = ExecutionStatus.DECOMPOSING
            task_tree = self.decomposer.decompose(record.requirement, context)
            record.task_tree = task_tree
            record.status = ExecutionStatus.READY
            logger.info(f"[{execution_id}] 任务分解完成，共 {self._count_leaf_tasks(task_tree)} 个叶子任务")
            return True
        except Exception as e:
            record.status = ExecutionStatus.FAILED
            record.errors.append(f"分解失败: {str(e)}")
            logger.error(f"[{execution_id}] 任务分解失败: {e}")
            return False

    def dispatch_tasks(self, execution_id: str) -> Dict[str, str]:
        """
        分发任务

        Args:
            execution_id: 执行ID

        Returns:
            任务ID到Agent名称的映射
        """
        record = self._get_execution(execution_id)
        if not record or not record.task_tree:
            logger.error(f"执行记录或任务树不存在: {execution_id}")
            return {}

        record.status = ExecutionStatus.DISPATCHING
        task_type = self._detect_task_type(record.requirement)
        leaf_tasks = self.decomposer.get_leaf_tasks(record.task_tree)

        dispatch_map: Dict[str, str] = {}
        for leaf in leaf_tasks:
            agent_name = self.dispatcher.dispatch(leaf, task_type)
            if agent_name:
                dispatch_map[leaf.task_id] = agent_name
                self.send_message(
                    receiver=agent_name,
                    content={
                        "action": "execute_task",
                        "task_id": leaf.task_id,
                        "task_name": leaf.name,
                        "task_description": leaf.description,
                        "execution_id": execution_id
                    },
                    msg_type=MessageType.REQUEST,
                    correlation_id=execution_id
                )
            else:
                record.errors.append(f"无法分发任务: {leaf.name}")

        record.status = ExecutionStatus.RUNNING
        logger.info(f"[{execution_id}] 任务分发完成")
        return dispatch_map

    def track_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        跟踪任务执行状态

        Args:
            execution_id: 执行ID

        Returns:
            当前执行状态
        """
        record = self._get_execution(execution_id)
        if not record:
            return {"error": "执行记录不存在"}

        if not record.task_tree:
            return {
                "execution_id": execution_id,
                "status": record.status.value,
                "progress": 0.0
            }

        # 计算进度
        leaf_tasks = self.decomposer.get_leaf_tasks(record.task_tree)
        total = len(leaf_tasks)
        completed = sum(1 for t in leaf_tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in leaf_tasks if t.status == TaskStatus.FAILED)
        progress = completed / total if total > 0 else 0.0

        # 检查是否全部完成
        if completed + failed == total and total > 0:
            if failed > 0:
                record.status = ExecutionStatus.FAILED
            else:
                record.status = ExecutionStatus.COMPLETED
            if not record.end_time:
                record.end_time = datetime.now()

        status_info = {
            "execution_id": execution_id,
            "status": record.status.value,
            "progress": progress,
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "errors": record.errors
        }

        logger.debug(f"[{execution_id}] 执行跟踪: {status_info}")
        return status_info

    def update_task_result(
        self,
        execution_id: str,
        task_id: str,
        result: Dict[str, Any],
        success: bool = True
    ) -> bool:
        """
        更新任务执行结果

        Args:
            execution_id: 执行ID
            task_id: 任务ID
            result: 执行结果
            success: 是否成功

        Returns:
            是否更新成功
        """
        record = self._get_execution(execution_id)
        if not record or not record.task_tree:
            return False

        task = self.decomposer._find_task(record.task_tree, task_id)
        if not task:
            return False

        task.result = result
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        record.results[task_id] = result

        if not success:
            record.errors.append(f"任务失败 {task_id}: {result.get('error', '未知错误')}")

        logger.info(f"[{execution_id}] 任务结果更新: {task_id} -> {'成功' if success else '失败'}")
        return True

    def summarize_results(self, execution_id: str) -> Dict[str, Any]:
        """
        汇总执行结果

        Args:
            execution_id: 执行ID

        Returns:
            汇总结果
        """
        record = self._get_execution(execution_id)
        if not record:
            return {"success": False, "error": "执行记录不存在"}

        summary = self._summarize_results(record)
        logger.info(f"[{execution_id}] 结果汇总完成")
        return summary

    def _summarize_results(self, record: TaskExecutionRecord) -> Dict[str, Any]:
        """内部汇总逻辑"""
        if not record.task_tree:
            return {
                "success": record.status == ExecutionStatus.COMPLETED,
                "execution_id": record.execution_id,
                "status": record.status.value,
                "requirement": record.requirement,
                "errors": record.errors
            }

        leaf_tasks = self.decomposer.get_leaf_tasks(record.task_tree)
        total = len(leaf_tasks)
        completed = sum(1 for t in leaf_tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in leaf_tasks if t.status == TaskStatus.FAILED)

        success = record.status == ExecutionStatus.COMPLETED and failed == 0

        return {
            "success": success,
            "execution_id": record.execution_id,
            "status": record.status.value,
            "requirement": record.requirement,
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "results": record.results,
            "errors": record.errors,
            "task_tree": record.task_tree.to_dict(),
            "duration_seconds": (
                (record.end_time - record.start_time).total_seconds()
                if record.end_time else None
            )
        }

    def _track_execution(self, record: TaskExecutionRecord) -> None:
        """简化版执行跟踪（实际场景中会监听消息）"""
        # 简化实现：标记所有叶子任务为完成
        if record.task_tree:
            leaf_tasks = self.decomposer.get_leaf_tasks(record.task_tree)
            for leaf in leaf_tasks:
                if leaf.status == TaskStatus.PENDING:
                    leaf.status = TaskStatus.COMPLETED
                    leaf.result = {"status": "completed", "agent": leaf.assignee or "unknown"}
                    record.results[leaf.task_id] = leaf.result

    def _detect_task_type(self, requirement: str) -> TaskType:
        """检测任务类型"""
        req_lower = requirement.lower()
        if any(kw in req_lower for kw in ["测试", "test case", "test suite", "单元测试", "集成测试"]):
            return TaskType.TESTING
        elif any(kw in req_lower for kw in ["文档", "doc", "说明", "readme", "documentation"]):
            return TaskType.DOCUMENTATION
        elif any(kw in req_lower for kw in ["重构", "refactor", "代码优化", "性能优化"]):
            return TaskType.REFACTORING
        elif any(kw in req_lower for kw in ["实现", "开发", "创建", "添加", "implement", "create", "add", "build", "开发"]):
            return TaskType.DEVELOPMENT
        else:
            return TaskType.GENERIC

    def _get_execution(self, execution_id: str) -> Optional[TaskExecutionRecord]:
        """获取执行记录"""
        with self._execution_lock:
            return self._executions.get(execution_id)

    def _count_leaf_tasks(self, node: TaskNode) -> int:
        """统计叶子任务数量"""
        if node.is_leaf():
            return 1
        return sum(self._count_leaf_tasks(child) for child in node.children)

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        with self._execution_lock:
            return [record.to_dict() for record in self._executions.values()]

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        base_status = super().get_status()
        with self._execution_lock:
            base_status.update({
                "executions_count": len(self._executions),
                "dispatcher_agents": self.dispatcher.get_registered_agents(),
                "decomposer": self.decomposer.name
            })
        return base_status
