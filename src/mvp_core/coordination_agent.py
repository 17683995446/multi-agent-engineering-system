"""
MVP阶段6: 协调Agent与工作流
遵循第一性原理：责任正交性、状态分离

核心组件：
- CoordinationAgent: 协调Agent，继承AgentBase
- Workflow: 工作流定义与管理
- WorkflowExecutor: 工作流执行器，支持拓扑排序与并行/串行执行
"""

from abc import ABC
from typing import Dict, Any, Optional, List, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque
import threading
import uuid
import concurrent.futures

from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus, Message, MessageType
from src.mvp_core.htd_decomposer import HTDDecomposer, TaskNode, TaskStatus
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowTask:
    """
    工作流任务节点

    属性：
    - task_id: 任务唯一标识
    - name: 任务名称
    - description: 任务描述
    - agent_name: 执行Agent名称
    - input_data: 输入数据
    - output_data: 输出数据
    - dependencies: 依赖任务ID列表
    - status: 任务状态
    - error: 错误信息
    """
    task_id: str
    name: str
    description: str
    agent_name: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "agent_name": self.agent_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Workflow:
    """
    工作流类

    核心能力：
    - 任务节点定义与管理
    - 依赖关系管理
    - 执行顺序控制（基于拓扑排序）
    """

    def __init__(self, name: str, description: str = ""):
        """初始化工作流"""
        self.workflow_id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.tasks: Dict[str, WorkflowTask] = {}
        self.status = WorkflowStatus.PENDING
        self.created_at = datetime.now()
        self._lock = threading.RLock()
        logger.info(f"工作流初始化: {name} ({self.workflow_id})")

    def add_task(
        self,
        task_id: str,
        name: str,
        description: str = "",
        agent_name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> WorkflowTask:
        """添加任务节点"""
        with self._lock:
            if task_id in self.tasks:
                raise ValueError(f"任务已存在: {task_id}")

            task = WorkflowTask(
                task_id=task_id,
                name=name,
                description=description,
                agent_name=agent_name,
                input_data=input_data or {},
                dependencies=dependencies or [],
            )
            self.tasks[task_id] = task
            logger.debug(f"工作流添加任务: {task_id} -> {name}")
            return task

    def remove_task(self, task_id: str) -> bool:
        """移除任务节点"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            # 检查是否有其他任务依赖此任务
            for task in self.tasks.values():
                if task_id in task.dependencies:
                    logger.warning(f"无法移除任务 {task_id}: 存在依赖")
                    return False
            del self.tasks[task_id]
            logger.debug(f"工作流移除任务: {task_id}")
            return True

    def add_dependency(self, task_id: str, dependency_id: str) -> bool:
        """添加任务依赖"""
        with self._lock:
            if task_id not in self.tasks or dependency_id not in self.tasks:
                logger.error("任务不存在")
                return False
            if dependency_id == task_id:
                logger.error("任务不能依赖自身")
                return False
            if dependency_id not in self.tasks[task_id].dependencies:
                self.tasks[task_id].dependencies.append(dependency_id)
                logger.debug(f"添加依赖: {task_id} -> {dependency_id}")
            return True

    def get_task(self, task_id: str) -> Optional[WorkflowTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_ready_tasks(self) -> List[WorkflowTask]:
        """获取可执行的任务（依赖已完成）"""
        with self._lock:
            ready = []
            for task in self.tasks.values():
                if task.status != TaskStatus.PENDING:
                    continue
                deps_completed = all(
                    self.tasks.get(dep_id) and self.tasks[dep_id].status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if deps_completed:
                    ready.append(task)
            return ready

    def topological_sort(self) -> List[List[str]]:
        """
        拓扑排序，返回按层级分组的任务ID列表
        同一层级的任务可以并行执行
        """
        with self._lock:
            in_degree = {tid: 0 for tid in self.tasks}
            adjacency: Dict[str, List[str]] = {tid: [] for tid in self.tasks}

            for task in self.tasks.values():
                for dep in task.dependencies:
                    if dep in self.tasks:
                        adjacency[dep].append(task.task_id)
                        in_degree[task.task_id] += 1

            # Kahn算法
            levels: List[List[str]] = []
            current_level = [tid for tid, deg in in_degree.items() if deg == 0]

            while current_level:
                levels.append(current_level)
                next_level = []
                for tid in current_level:
                    for neighbor in adjacency[tid]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            next_level.append(neighbor)
                current_level = next_level

            # 检查是否有环
            all_sorted = set()
            for level in levels:
                all_sorted.update(level)
            if len(all_sorted) != len(self.tasks):
                raise ValueError("工作流中存在循环依赖")

            return levels

    def validate(self) -> Tuple[bool, Optional[str]]:
        """验证工作流是否有效"""
        try:
            self.topological_sort()
            return True, None
        except ValueError as e:
            return False, str(e)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "tasks": {tid: task.to_dict() for tid, task in self.tasks.items()},
        }


class WorkflowExecutor:
    """
    工作流执行器

    核心能力：
    - 拓扑排序确定执行顺序
    - 支持并行/串行执行
    - 结果收集与状态跟踪
    """

    def __init__(self, max_workers: int = 4):
        """初始化执行器"""
        self.max_workers = max_workers
        self._execution_results: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        logger.info(f"工作流执行器初始化: max_workers={max_workers}")

    def execute(
        self,
        workflow: Workflow,
        agent_resolver: Optional[Callable[[str], Optional[AgentBase]]] = None,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow: 要执行的工作流
            agent_resolver: Agent解析函数，根据agent_name返回Agent实例
            parallel: 是否并行执行同一层级的任务

        Returns:
            执行结果汇总
        """
        valid, error = workflow.validate()
        if not valid:
            logger.error(f"工作流验证失败: {error}")
            return {"success": False, "error": error, "results": {}}

        workflow.status = WorkflowStatus.RUNNING
        logger.info(f"开始执行工作流: {workflow.name}")

        try:
            levels = workflow.topological_sort()
        except ValueError as e:
            workflow.status = WorkflowStatus.FAILED
            return {"success": False, "error": str(e), "results": {}}

        all_success = True

        for level in levels:
            if parallel and len(level) > 1:
                level_results = self._execute_level_parallel(
                    workflow, level, agent_resolver
                )
            else:
                level_results = self._execute_level_serial(
                    workflow, level, agent_resolver
                )

            for task_id, result in level_results.items():
                self._execution_results[task_id] = result
                if not result.get("success", False):
                    all_success = False
                    workflow.status = WorkflowStatus.FAILED
                    logger.error(f"任务执行失败: {task_id}")
                    # 失败时可以选择中断或继续，这里选择继续执行不依赖此任务的其他分支

        if all_success:
            workflow.status = WorkflowStatus.COMPLETED
            logger.info(f"工作流执行完成: {workflow.name}")
        else:
            workflow.status = WorkflowStatus.FAILED
            logger.error(f"工作流执行失败: {workflow.name}")

        return {
            "success": all_success,
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.name,
            "results": self._execution_results,
        }

    def _execute_level_serial(
        self,
        workflow: Workflow,
        level: List[str],
        agent_resolver: Optional[Callable[[str], Optional[AgentBase]]],
    ) -> Dict[str, Dict[str, Any]]:
        """串行执行一层任务"""
        results = {}
        for task_id in level:
            result = self._execute_single_task(workflow, task_id, agent_resolver)
            results[task_id] = result
        return results

    def _execute_level_parallel(
        self,
        workflow: Workflow,
        level: List[str],
        agent_resolver: Optional[Callable[[str], Optional[AgentBase]]],
    ) -> Dict[str, Dict[str, Any]]:
        """并行执行一层任务"""
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(
                    self._execute_single_task, workflow, task_id, agent_resolver
                ): task_id
                for task_id in level
            }
            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    results[task_id] = future.result()
                except Exception as e:
                    logger.error(f"并行任务异常: {task_id} - {e}")
                    results[task_id] = {"success": False, "error": str(e)}
        return results

    def _execute_single_task(
        self,
        workflow: Workflow,
        task_id: str,
        agent_resolver: Optional[Callable[[str], Optional[AgentBase]]],
    ) -> Dict[str, Any]:
        """执行单个任务"""
        task = workflow.get_task(task_id)
        if not task:
            return {"success": False, "error": f"任务不存在: {task_id}"}

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        logger.info(f"执行任务: {task_id} ({task.name})")

        try:
            # 收集依赖任务的输出作为输入
            task_input = dict(task.input_data)
            for dep_id in task.dependencies:
                dep_result = self._execution_results.get(dep_id, {}).get("output")
                if dep_result:
                    task_input[f"dep_{dep_id}"] = dep_result

            agent = None
            if agent_resolver and task.agent_name:
                agent = agent_resolver(task.agent_name)

            if agent:
                # 通过Agent执行
                agent.status = AgentStatus.BUSY
                try:
                    output = agent.execute({
                        "task_id": task_id,
                        "name": task.name,
                        "description": task.description,
                        "input": task_input,
                    })
                finally:
                    agent.status = AgentStatus.IDLE
            else:
                # 模拟执行（无Agent时）
                output = self._mock_execute(task, task_input)

            task.output_data = output
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            logger.info(f"任务完成: {task_id}")
            return {"success": True, "output": output, "task_id": task_id}

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            logger.error(f"任务失败: {task_id} - {e}")
            return {"success": False, "error": str(e), "task_id": task_id}

    def _mock_execute(self, task: WorkflowTask, task_input: Dict[str, Any]) -> Dict[str, Any]:
        """模拟执行任务（当无Agent可用时）"""
        return {
            "task_id": task.task_id,
            "name": task.name,
            "executed_by": "mock",
            "input_summary": list(task_input.keys()),
            "status": "completed",
        }

    def get_execution_results(self) -> Dict[str, Dict[str, Any]]:
        """获取执行结果"""
        with self._lock:
            return dict(self._execution_results)


class CoordinationAgent(AgentBase):
    """
    协调Agent - 负责多Agent协调与工作流执行

    核心能力：
    - 工作流定义与执行
    - 多Agent协调
    - 任务依赖管理
    - 执行状态跟踪
    """

    def __init__(self, name: str = "coordination_agent", message_bus: Optional[MessageBus] = None):
        """初始化协调Agent"""
        super().__init__(name, message_bus)
        self.decomposer = HTDDecomposer(name=f"{name}_decomposer")
        self.executor = WorkflowExecutor()
        self.workflows: Dict[str, Workflow] = {}
        self._agents: Dict[str, AgentBase] = {}
        self._workflow_lock = threading.RLock()
        self._register_default_handlers()
        logger.info(f"协调Agent初始化: {name}")

    def _register_default_handlers(self) -> None:
        """注册默认消息处理器"""
        self.register_handler(MessageType.REQUEST, self._handle_coordination_request)
        self.register_handler(MessageType.EVENT, self._handle_workflow_event)

    def register_agent(self, agent: AgentBase) -> bool:
        """注册可协调的Agent"""
        with self._workflow_lock:
            if agent.name in self._agents:
                logger.warning(f"Agent已注册: {agent.name}")
                return False
            self._agents[agent.name] = agent
            logger.info(f"注册Agent到协调器: {agent.name}")
            return True

    def unregister_agent(self, agent_name: str) -> bool:
        """注销Agent"""
        with self._workflow_lock:
            if agent_name not in self._agents:
                return False
            del self._agents[agent_name]
            logger.info(f"从协调器注销Agent: {agent_name}")
            return True

    def get_registered_agents(self) -> List[str]:
        """获取已注册的Agent列表"""
        with self._workflow_lock:
            return list(self._agents.keys())

    def create_workflow(self, name: str, description: str = "") -> Workflow:
        """创建工作流"""
        workflow = Workflow(name=name, description=description)
        with self._workflow_lock:
            self.workflows[workflow.workflow_id] = workflow
        logger.info(f"创建工作流: {name} ({workflow.workflow_id})")
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流"""
        return self.workflows.get(workflow_id)

    def decompose_to_workflow(self, requirement: str, context: Optional[Dict[str, Any]] = None) -> Workflow:
        """
        将需求分解为工作流

        使用HTDDecomposer分解需求，然后转换为Workflow
        """
        task_tree = self.decomposer.decompose(requirement, context)
        workflow = self.create_workflow(
            name=f"workflow_{task_tree.task_id}",
            description=requirement,
        )

        # 将HTD任务树转换为WorkflowTask
        self._convert_task_node(workflow, task_tree)

        logger.info(f"需求分解为工作流: {workflow.workflow_id}")
        return workflow

    def _convert_task_node(self, workflow: Workflow, node: TaskNode, parent_deps: Optional[List[str]] = None) -> None:
        """递归转换TaskNode为WorkflowTask"""
        deps = list(node.dependencies)
        if parent_deps:
            deps.extend(parent_deps)

        workflow.add_task(
            task_id=node.task_id,
            name=node.name,
            description=node.description,
            agent_name=node.assignee,
            dependencies=deps,
        )

        for child in node.children:
            # 子任务依赖父任务
            child_deps = list(child.dependencies)
            if node.task_id not in child_deps:
                child_deps.append(node.task_id)
            self._convert_task_node(workflow, child, child_deps)

    def execute_workflow(
        self,
        workflow: Workflow,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow: 要执行的工作流
            parallel: 是否并行执行
        """
        logger.info(f"协调Agent执行工作流: {workflow.name}")

        def agent_resolver(agent_name: str) -> Optional[AgentBase]:
            return self._agents.get(agent_name)

        result = self.executor.execute(workflow, agent_resolver=agent_resolver, parallel=parallel)
        return result

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务 - AgentBase抽象方法实现

        支持的任务类型：
        - create_workflow: 创建工作流
        - execute_workflow: 执行工作流
        - decompose_requirement: 分解需求
        - get_status: 获取状态
        """
        task_type = task.get("type", "unknown")
        logger.info(f"协调Agent执行任务: {task_type}")

        if task_type == "create_workflow":
            workflow = self.create_workflow(
                name=task.get("name", "unnamed"),
                description=task.get("description", ""),
            )
            return {"success": True, "workflow_id": workflow.workflow_id}

        elif task_type == "execute_workflow":
            workflow_id = task.get("workflow_id")
            workflow = self.get_workflow(workflow_id) if workflow_id else None
            if not workflow:
                return {"success": False, "error": f"工作流不存在: {workflow_id}"}
            result = self.execute_workflow(workflow, parallel=task.get("parallel", True))
            return result

        elif task_type == "decompose_requirement":
            requirement = task.get("requirement", "")
            if not requirement:
                return {"success": False, "error": "需求不能为空"}
            workflow = self.decompose_to_workflow(requirement, task.get("context"))
            return {"success": True, "workflow_id": workflow.workflow_id, "workflow": workflow.to_dict()}

        elif task_type == "get_status":
            return self.get_status()

        else:
            return {"success": False, "error": f"未知任务类型: {task_type}"}

    def get_status(self) -> Dict[str, Any]:
        """获取协调Agent状态"""
        base_status = super().get_status()
        with self._workflow_lock:
            base_status.update({
                "workflows": list(self.workflows.keys()),
                "workflow_count": len(self.workflows),
                "agents": list(self._agents.keys()),
                "agent_count": len(self._agents),
                "executor_results": len(self.executor.get_execution_results()),
            })
        return base_status

    def _handle_coordination_request(self, message: Message) -> None:
        """处理协调请求消息"""
        content = message.content
        action = content.get("action")
        logger.debug(f"处理协调请求: {action} from {message.sender}")

        if action == "register_agent":
            agent_name = content.get("agent_name")
            # 注意：这里只是记录请求，实际Agent实例需要通过register_agent方法注册
            self.send_message(
                receiver=message.sender,
                content={"action": "register_agent_ack", "agent_name": agent_name},
                msg_type=MessageType.RESPONSE,
                correlation_id=message.correlation_id,
            )
        elif action == "execute_workflow":
            workflow_id = content.get("workflow_id")
            workflow = self.get_workflow(workflow_id)
            if workflow:
                result = self.execute_workflow(workflow)
                self.send_message(
                    receiver=message.sender,
                    content={"action": "workflow_result", "result": result},
                    msg_type=MessageType.RESPONSE,
                    correlation_id=message.correlation_id,
                )

    def _handle_workflow_event(self, message: Message) -> None:
        """处理工作流事件消息"""
        content = message.content
        event_type = content.get("event_type")
        logger.debug(f"处理工作流事件: {event_type} from {message.sender}")

        if event_type == "task_completed":
            task_id = content.get("task_id")
            workflow_id = content.get("workflow_id")
            logger.info(f"任务完成事件: {task_id} in {workflow_id}")
