"""
协调Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 多Agent工作流编排
3. Agent间消息传递
4. 工作流状态跟踪和异常处理
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Set
from datetime import datetime
from uuid import uuid4
import threading
import queue
import time
from pathlib import Path
from src.agents.base import BaseAgent
from src.common.utils import setup_logger
from src.common.contract_net import ContractNetProtocol, TaskRequirement

# 可选导入yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

logger = setup_logger(__name__)


class AgentCapability(Enum):
    """Agent能力标签"""
    TASK_DISPATCH = "task_dispatch"
    PRIORITY_CONTROL = "priority_control"
    WORKFLOW_MANAGEMENT = "workflow_management"
    CODE_GENERATION = "code_generation"
    REFACTORING = "refactoring"
    BUG_FIX = "bug_fix"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    MODULE_BOUNDARY = "module_boundary"
    ARCHITECTURE_DESIGN = "architecture_design"
    CODE_REVIEW = "code_review"
    QUALITY_CHECK = "quality_check"
    SECURITY_SCAN = "security_scan"
    TEST_GENERATION = "test_generation"
    REGRESSION_TEST = "regression_test"
    COVERAGE_ANALYSIS = "coverage_analysis"
    DOC_GENERATION = "doc_generation"
    CHANGE_TRACKING = "change_tracking"
    ARCHIVING = "archiving"


class AgentPermission(Enum):
    """Agent权限类型"""
    READ_CODE = "read_code"
    WRITE_CODE = "write_code"
    MODIFY_ARCHITECTURE = "modify_architecture"
    EXECUTE_TASK = "execute_task"
    SEND_MESSAGE = "send_message"
    RECEIVE_MESSAGE = "receive_message"
    MANAGE_WORKFLOW = "manage_workflow"
    CONFIGURE_SYSTEM = "configure_system"


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """任务状态"""
    WAITING = "waiting"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class AgentMessage:
    """Agent消息"""
    msg_id: str
    sender: str
    receiver: str
    msg_type: MessageType
    content: Any
    timestamp: str
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowTask:
    """工作流任务"""
    task_id: str
    agent_name: str
    action: str
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.WAITING
    result: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class AgentIdentity:
    """Agent身份信息"""
    agent_id: str
    name: str
    role: str
    capabilities: List[AgentCapability]
    permissions: List[AgentPermission]
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    """工作流定义"""
    workflow_id: str
    name: str
    description: str
    tasks: List[WorkflowTask]
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_task_index: int = 0


class MessageQueue:
    """消息队列"""
    
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._subscribers: Dict[str, Callable] = {}
    
    def publish(self, message: AgentMessage):
        """发布消息"""
        with self._lock:
            self._queue.put(message)
            logger.debug(f"消息发布: {message.sender} -> {message.receiver}")
            
            if message.receiver in self._subscribers:
                self._subscribers[message.receiver](message)
    
    def subscribe(self, agent_name: str, callback: Callable[[AgentMessage], None]):
        """订阅消息"""
        with self._lock:
            self._subscribers[agent_name] = callback
            logger.debug(f"Agent订阅消息: {agent_name}")
    
    def unsubscribe(self, agent_name: str):
        """取消订阅"""
        with self._lock:
            if agent_name in self._subscribers:
                del self._subscribers[agent_name]
                logger.debug(f"Agent取消订阅: {agent_name}")
    
    def get_message(self, timeout: float = 1.0) -> Optional[AgentMessage]:
        """获取消息"""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


class CoordinationAgent(BaseAgent):
    """协调Agent - 多Agent工作流协调器"""
    
    def __init__(self):
        super().__init__("CoordinationAgent")
        self.is_running = False
        self.registered_agents: Dict[str, Any] = {}
        self.agent_identities: Dict[str, AgentIdentity] = {}
        self.active_workflows: Dict[str, Workflow] = {}
        self.message_queue = MessageQueue()
        self.message_history: List[AgentMessage] = []
        self._coordination_lock = threading.Lock()
        self.capability_action_map: Dict[AgentCapability, List[str]] = {}
        self.contract_net = ContractNetProtocol()  # 合同网协议
        self._init_capability_mapping()
    
    def _init_capability_mapping(self):
        """初始化能力与方法映射"""
        self.capability_action_map = {
            AgentCapability.TASK_DISPATCH: ["execute_task", "dispatch"],
            AgentCapability.PRIORITY_CONTROL: ["set_priority"],
            AgentCapability.WORKFLOW_MANAGEMENT: ["create_workflow", "execute_workflow", "manage_workflow"],
            AgentCapability.CODE_GENERATION: ["generate_code", "create_code"],
            AgentCapability.REFACTORING: ["refactor_code"],
            AgentCapability.BUG_FIX: ["fix_bug"],
            AgentCapability.DEPENDENCY_ANALYSIS: ["analyze_dependencies"],
            AgentCapability.MODULE_BOUNDARY: ["define_boundaries"],
            AgentCapability.ARCHITECTURE_DESIGN: ["design_architecture"],
            AgentCapability.CODE_REVIEW: ["review_code", "review_file"],
            AgentCapability.QUALITY_CHECK: ["check_quality"],
            AgentCapability.SECURITY_SCAN: ["scan_security"],
            AgentCapability.TEST_GENERATION: ["generate_tests", "generate_unit_tests"],
            AgentCapability.REGRESSION_TEST: ["run_regression_tests"],
            AgentCapability.COVERAGE_ANALYSIS: ["analyze_coverage"],
            AgentCapability.DOC_GENERATION: ["generate_doc", "generate_document"],
            AgentCapability.CHANGE_TRACKING: ["track_changes"],
            AgentCapability.ARCHIVING: ["archive"]
        }
        logger.debug("能力-方法映射初始化完成")
    
    def start(self):
        """启动Agent"""
        self.is_running = True
        logger.info(f"协调Agent {self.name} 已启动")
    
    def stop(self):
        """停止Agent"""
        self.is_running = False
        for workflow in self.active_workflows.values():
            if workflow.status == WorkflowStatus.RUNNING:
                workflow.status = WorkflowStatus.CANCELLED
        logger.info(f"协调Agent {self.name} 已停止")
    
    def register_agent_with_identity(
        self, 
        agent_name: str, 
        agent_instance: Any,
        role: str,
        capabilities: List[AgentCapability],
        permissions: List[AgentPermission],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentIdentity:
        """注册Agent并创建身份信息"""
        with self._coordination_lock:
            if agent_name in self.agent_identities:
                logger.warning(f"Agent已注册: {agent_name}")
                return self.agent_identities[agent_name]
            
            agent_id = f"agent_{uuid4().hex[:8]}"
            
            identity = AgentIdentity(
                agent_id=agent_id,
                name=agent_name,
                role=role,
                capabilities=capabilities,
                permissions=permissions,
                metadata=metadata or {}
            )
            
            self.agent_identities[agent_name] = identity
            self.registered_agents[agent_name] = agent_instance
            self.message_queue.subscribe(agent_name, self._handle_agent_message)
            
            # 同时注册到合同网协议
            capability_strings = {c.value for c in capabilities}
            self.contract_net.register_agent_capabilities(
                agent_name, 
                capability_strings,
                max_capacity=10.0
            )
            
            logger.info(f"Agent注册成功: {agent_name} (ID: {agent_id}, Role: {role})")
            logger.debug(f"  能力: {[c.value for c in capabilities]}")
            logger.debug(f"  权限: {[p.value for p in permissions]}")
            
            return identity
    
    def register_agent(self, agent_name: str, agent_instance: Any):
        """简化版注册（兼容旧代码）"""
        default_capabilities = [AgentCapability.EXECUTE_TASK]
        default_permissions = [
            AgentPermission.EXECUTE_TASK,
            AgentPermission.SEND_MESSAGE,
            AgentPermission.RECEIVE_MESSAGE
        ]
        self.register_agent_with_identity(
            agent_name,
            agent_instance,
            "generic",
            default_capabilities,
            default_permissions
        )
    
    def load_agents_from_config(self, config_path: str = "configs/agents.yaml"):
        """从配置文件加载Agent"""
        if not HAS_YAML:
            logger.warning("PyYAML未安装，无法从配置文件加载Agent")
            return
            
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.warning(f"配置文件不存在: {config_path}")
                return
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if 'agents' in config:
                for agent_config in config['agents'].values():
                    logger.info(f"从配置加载Agent: {agent_config['name']}")
            
            logger.info(f"配置文件加载完成: {config_path}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
    
    def unregister_agent(self, agent_name: str):
        """注销Agent"""
        with self._coordination_lock:
            if agent_name in self.registered_agents:
                self.message_queue.unsubscribe(agent_name)
                del self.registered_agents[agent_name]
                if agent_name in self.agent_identities:
                    del self.agent_identities[agent_name]
                logger.info(f"Agent注销成功: {agent_name}")
    
    def get_agent_identity(self, agent_name: str) -> Optional[AgentIdentity]:
        """获取Agent身份信息"""
        return self.agent_identities.get(agent_name)
    
    def has_capability(self, agent_name: str, capability: AgentCapability) -> bool:
        """检查Agent是否具有指定能力"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            return False
        return capability in identity.capabilities
    
    def has_permission(self, agent_name: str, permission: AgentPermission) -> bool:
        """检查Agent是否具有指定权限"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            return False
        return permission in identity.permissions
    
    def can_execute_action(self, agent_name: str, action: str) -> bool:
        """检查Agent是否可以执行指定动作（基于能力）"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            return False
        
        for capability in identity.capabilities:
            if capability in self.capability_action_map:
                if action in self.capability_action_map[capability]:
                    return True
        return False
    
    def find_agents_by_capability(self, capability: AgentCapability) -> List[AgentIdentity]:
        """查找具有指定能力的所有Agent"""
        return [
            identity for identity in self.agent_identities.values()
            if capability in identity.capabilities and identity.status == "active"
        ]
    
    def find_agents_by_role(self, role: str) -> List[AgentIdentity]:
        """查找具有指定角色的所有Agent"""
        return [
            identity for identity in self.agent_identities.values()
            if identity.role == role and identity.status == "active"
        ]
    
    def get_all_registered_agents(self) -> List[AgentIdentity]:
        """获取所有注册的Agent"""
        return list(self.agent_identities.values())
    
    def update_agent_capabilities(
        self, 
        agent_name: str, 
        new_capabilities: List[AgentCapability]
    ) -> bool:
        """更新Agent能力"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            logger.warning(f"Agent不存在: {agent_name}")
            return False
        
        with self._coordination_lock:
            identity.capabilities = new_capabilities
            logger.info(f"Agent能力更新: {agent_name} -> {[c.value for c in new_capabilities]}")
            return True
    
    def update_agent_permissions(
        self, 
        agent_name: str, 
        new_permissions: List[AgentPermission]
    ) -> bool:
        """更新Agent权限"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            logger.warning(f"Agent不存在: {agent_name}")
            return False
        
        with self._coordination_lock:
            identity.permissions = new_permissions
            logger.info(f"Agent权限更新: {agent_name} -> {[p.value for p in new_permissions]}")
            return True
    
    def set_agent_status(self, agent_name: str, status: str) -> bool:
        """设置Agent状态"""
        identity = self.get_agent_identity(agent_name)
        if not identity:
            logger.warning(f"Agent不存在: {agent_name}")
            return False
        
        with self._coordination_lock:
            identity.status = status
            logger.info(f"Agent状态变更: {agent_name} -> {status}")
            return True
    
    def send_message(
        self,
        sender: str,
        receiver: str,
        msg_type: MessageType,
        content: Any,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """发送消息"""
        message = AgentMessage(
            msg_id=str(uuid4())[:8],
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            content=content,
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        
        self.message_queue.publish(message)
        self.message_history.append(message)
        logger.info(f"消息发送: {sender} -> {receiver} [{msg_type.value}]")
        
        return message
    
    def _handle_agent_message(self, message: AgentMessage):
        """处理Agent消息"""
        logger.debug(f"消息处理: {message.msg_id}")
    
    def create_workflow(
        self,
        name: str,
        description: str,
        tasks: List[Dict[str, Any]]
    ) -> Workflow:
        """创建工作流"""
        workflow_id = f"wf_{len(self.active_workflows) + 1}"
        
        workflow_tasks = []
        for task_def in tasks:
            task = WorkflowTask(
                task_id=f"{workflow_id}_task_{len(workflow_tasks) + 1}",
                agent_name=task_def["agent_name"],
                action=task_def["action"],
                params=task_def.get("params", {}),
                dependencies=task_def.get("dependencies", [])
            )
            workflow_tasks.append(task)
        
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            tasks=workflow_tasks
        )
        
        self.active_workflows[workflow_id] = workflow
        logger.info(f"工作流创建: {name} (ID: {workflow_id})")
        
        return workflow
    
    def execute_workflow(self, workflow_id: str) -> Workflow:
        """执行工作流"""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        workflow = self.active_workflows[workflow_id]
        
        if workflow.status != WorkflowStatus.PENDING:
            raise ValueError(f"工作流状态不允许执行: {workflow.status.value}")
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now().isoformat()
        logger.info(f"工作流开始执行: {workflow.name}")
        
        try:
            self._execute_tasks(workflow)
            
            failed_tasks = [t for t in workflow.tasks if t.status == TaskStatus.FAILED]
            if failed_tasks:
                workflow.status = WorkflowStatus.FAILED
                logger.error(f"工作流执行失败: {len(failed_tasks)} 个任务失败")
            else:
                workflow.status = WorkflowStatus.COMPLETED
                logger.info(f"工作流执行完成: {workflow.name}")
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            logger.error(f"工作流执行异常: {str(e)}")
        
        workflow.completed_at = datetime.now().isoformat()
        return workflow
    
    def _execute_tasks(self, workflow: Workflow):
        """执行工作流任务"""
        for i, task in enumerate(workflow.tasks):
            workflow.current_task_index = i
            
            if not self._check_dependencies(task, workflow.tasks):
                task.status = TaskStatus.FAILED
                task.error = "依赖任务未完成"
                continue
            
            task.status = TaskStatus.READY
            logger.info(f"开始执行任务: {task.task_id} [{task.agent_name}.{task.action}]")
            
            task.started_at = datetime.now().isoformat()
            task.status = TaskStatus.RUNNING
            
            result = self._execute_task(task)
            
            if result["success"]:
                task.status = TaskStatus.SUCCESS
                task.result = result["data"]
                logger.info(f"任务执行成功: {task.task_id}")
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error", "未知错误")
                logger.error(f"任务执行失败: {task.task_id} - {task.error}")
            
            task.completed_at = datetime.now().isoformat()
    
    def _check_dependencies(self, task: WorkflowTask, all_tasks: List[WorkflowTask]) -> bool:
        """检查任务依赖"""
        if not task.dependencies:
            return True
        
        for dep_id in task.dependencies:
            dep_task = next((t for t in all_tasks if t.task_id == dep_id), None)
            if not dep_task:
                return False
            if dep_task.status != TaskStatus.SUCCESS:
                return False
        
        return True
    
    def _execute_task(self, task: WorkflowTask) -> Dict[str, Any]:
        """执行单个任务（权限和能力检查）"""
        if task.agent_name not in self.registered_agents:
            return {
                "success": False,
                "error": f"Agent未注册: {task.agent_name}"
            }
        
        if not self.has_permission(task.agent_name, AgentPermission.EXECUTE_TASK):
            return {
                "success": False,
                "error": f"Agent {task.agent_name} 无执行任务权限"
            }
        
        if not self.can_execute_action(task.agent_name, task.action):
            return {
                "success": False,
                "error": f"Agent {task.agent_name} 无执行 {task.action} 的能力"
            }
        
        agent = self.registered_agents[task.agent_name]
        
        if not hasattr(agent, task.action):
            return {
                "success": False,
                "error": f"Agent没有该方法: {task.agent_name}.{task.action}"
            }
        
        try:
            action_method = getattr(agent, task.action)
            result = action_method(**task.params)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流状态"""
        return self.active_workflows.get(workflow_id)
    
    def pause_workflow(self, workflow_id: str) -> bool:
        """暂停工作流"""
        if workflow_id not in self.active_workflows:
            return False
        
        workflow = self.active_workflows[workflow_id]
        if workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            logger.info(f"工作流已暂停: {workflow.name}")
            return True
        return False
    
    def resume_workflow(self, workflow_id: str) -> bool:
        """恢复工作流"""
        if workflow_id not in self.active_workflows:
            return False
        
        workflow = self.active_workflows[workflow_id]
        if workflow.status == WorkflowStatus.PAUSED:
            workflow.status = WorkflowStatus.RUNNING
            logger.info(f"工作流已恢复: {workflow.name}")
            return True
        return False
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        if workflow_id not in self.active_workflows:
            return False
        
        workflow = self.active_workflows[workflow_id]
        workflow.status = WorkflowStatus.CANCELLED
        logger.info(f"工作流已取消: {workflow.name}")
        return True
    
    def send_message(
        self,
        sender: str,
        receiver: str,
        msg_type: MessageType,
        content: Any,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """发送消息（权限检查）"""
        if sender != "System" and not self.has_permission(sender, AgentPermission.SEND_MESSAGE):
            logger.warning(f"Agent {sender} 无发送消息权限")
            raise PermissionError(f"Agent {sender} 无发送消息权限")
        
        message = AgentMessage(
            msg_id=str(uuid4())[:8],
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            content=content,
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        
        self.message_queue.publish(message)
        self.message_history.append(message)
        logger.info(f"消息发送: {sender} -> {receiver} [{msg_type.value}]")
        
        return message
    
    # ========== 合同网协议方法 ==========
    
    def announce_task_for_bidding(
        self, 
        task_description: str, 
        required_capabilities: List[str], 
        estimated_effort: float = 1.0
    ) -> str:
        """
        发布任务招标
        """
        from uuid import uuid4
        
        task_id = f"task_{uuid4().hex[:8]}"
        
        requirement = TaskRequirement(
            task_id=task_id,
            description=task_description,
            required_capabilities=set(required_capabilities),
            estimated_effort=estimated_effort
        )
        
        return self.contract_net.announce_task(requirement)
    
    def run_contract_net_cycle(
        self, 
        task_description: str, 
        required_capabilities: List[str], 
        estimated_effort: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        运行完整的合同网协议流程：招标→投标→评标→授标
        """
        from uuid import uuid4
        
        task_id = f"task_{uuid4().hex[:8]}"
        
        requirement = TaskRequirement(
            task_id=task_id,
            description=task_description,
            required_capabilities=set(required_capabilities),
            estimated_effort=estimated_effort
        )
        
        assignment = self.contract_net.full_cnp_cycle(requirement)
        
        if assignment:
            return {
                "task_id": assignment.task_id,
                "assigned_agent": assignment.assigned_agent,
                "proposed_cost": assignment.bid.proposed_cost if assignment.bid else None,
                "assigned_at": assignment.assigned_at
            }
        
        return None
    
    def get_load_balancing_info(self) -> Dict[str, Any]:
        """
        获取负载均衡信息
        """
        return self.contract_net.check_load_balancing_info()
    
    def complete_assigned_task(self, task_id: str):
        """
        标记已分配的任务完成
        """
        self.contract_net.complete_task(task_id)
    
    # ========== 原有执行入口 ==========
    
    def execute(self, task: Any) -> Any:
        """Agent执行入口"""
        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "create_workflow":
                wf = self.create_workflow(
                    task["name"],
                    task["description"],
                    task["tasks"]
                )
                return {"workflow_id": wf.workflow_id}
            elif action == "execute_workflow":
                wf = self.execute_workflow(task["workflow_id"])
                return {
                    "workflow_id": wf.workflow_id,
                    "status": wf.status.value
                }
            elif action == "send_message":
                msg = self.send_message(
                    task["sender"],
                    task["receiver"],
                    MessageType[task["msg_type"].upper()],
                    task["content"]
                )
                return {"msg_id": msg.msg_id}
            elif action == "get_agents":
                agents = self.get_all_registered_agents()
                return {
                    "agents": [
                        {
                            "agent_id": a.agent_id,
                            "name": a.name,
                            "role": a.role,
                            "capabilities": [c.value for c in a.capabilities],
                            "status": a.status
                        }
                        for a in agents
                    ]
                }
            elif action == "run_contract_net":
                # 运行合同网协议
                result = self.run_contract_net_cycle(
                    task.get("description", ""),
                    task.get("required_capabilities", []),
                    task.get("estimated_effort", 1.0)
                )
                return result
            elif action == "get_load_balancing":
                return self.get_load_balancing_info()
        return {"error": "Invalid task format"}


def demo_coordination_agent():
    """演示协调Agent - Agent身份、能力、权限注册体系"""
    print("=" * 80)
    print("第40阶段演示: Agent身份、能力、权限注册体系")
    print("=" * 80)
    print()

    coordinator = CoordinationAgent()
    coordinator.start()

    from src.agents.testing import TestingAgent
    from src.agents.code_review import CodeReviewAgent
    from src.agents.development import DevelopmentAgent
    from src.agents.central_control import CentralControlAgent

    print("=" * 80)
    print("步骤1: 注册Agent（带身份、能力、权限）")
    print("-" * 80)
    
    # 测试Agent
    test_agent = TestingAgent()
    test_agent.start()
    test_identity = coordinator.register_agent_with_identity(
        "TestingAgent",
        test_agent,
        "测试验证",
        [
            AgentCapability.TEST_GENERATION,
            AgentCapability.REGRESSION_TEST,
            AgentCapability.COVERAGE_ANALYSIS
        ],
        [
            AgentPermission.READ_CODE,
            AgentPermission.EXECUTE_TASK,
            AgentPermission.SEND_MESSAGE,
            AgentPermission.RECEIVE_MESSAGE
        ]
    )
    print(f"✅ 测试Agent注册: ID={test_identity.agent_id}, Role={test_identity.role}")
    
    # 评审Agent
    review_agent = CodeReviewAgent()
    review_agent.start()
    review_identity = coordinator.register_agent_with_identity(
        "CodeReviewAgent",
        review_agent,
        "代码评审",
        [
            AgentCapability.CODE_REVIEW,
            AgentCapability.QUALITY_CHECK,
            AgentCapability.SECURITY_SCAN
        ],
        [
            AgentPermission.READ_CODE,
            AgentPermission.EXECUTE_TASK,
            AgentPermission.SEND_MESSAGE,
            AgentPermission.RECEIVE_MESSAGE
        ]
    )
    print(f"✅ 评审Agent注册: ID={review_identity.agent_id}, Role={review_identity.role}")
    
    # 开发Agent
    dev_agent = DevelopmentAgent()
    dev_agent.start()
    dev_identity = coordinator.register_agent_with_identity(
        "DevelopmentAgent",
        dev_agent,
        "开发编码",
        [
            AgentCapability.CODE_GENERATION,
            AgentCapability.REFACTORING,
            AgentCapability.BUG_FIX
        ],
        [
            AgentPermission.READ_CODE,
            AgentPermission.WRITE_CODE,
            AgentPermission.EXECUTE_TASK,
            AgentPermission.SEND_MESSAGE,
            AgentPermission.RECEIVE_MESSAGE
        ]
    )
    print(f"✅ 开发Agent注册: ID={dev_identity.agent_id}, Role={dev_identity.role}")
    
    # 总控Agent
    cc_agent = CentralControlAgent()
    cc_agent.start()
    cc_identity = coordinator.register_agent_with_identity(
        "CentralControlAgent",
        cc_agent,
        "总控调度",
        [
            AgentCapability.TASK_DISPATCH,
            AgentCapability.PRIORITY_CONTROL,
            AgentCapability.WORKFLOW_MANAGEMENT
        ],
        [
            AgentPermission.READ_CODE,
            AgentPermission.EXECUTE_TASK,
            AgentPermission.SEND_MESSAGE,
            AgentPermission.RECEIVE_MESSAGE,
            AgentPermission.MANAGE_WORKFLOW,
            AgentPermission.CONFIGURE_SYSTEM
        ]
    )
    print(f"✅ 总控Agent注册: ID={cc_identity.agent_id}, Role={cc_identity.role}")
    
    print(f"\n✅ 总计注册 {len(coordinator.get_all_registered_agents())} 个Agent")
    print()

    print("=" * 80)
    print("步骤2: 能力和权限验证")
    print("-" * 80)
    
    has_test_gen = coordinator.has_capability("TestingAgent", AgentCapability.TEST_GENERATION)
    print(f"测试Agent是否有TEST_GENERATION能力: {has_test_gen}")
    
    has_write_code = coordinator.has_permission("CodeReviewAgent", AgentPermission.WRITE_CODE)
    print(f"评审Agent是否有WRITE_CODE权限: {has_write_code}")
    
    can_review = coordinator.can_execute_action("CodeReviewAgent", "review_file")
    print(f"评审Agent是否可以执行review_file: {can_review}")
    
    can_refactor = coordinator.can_execute_action("TestingAgent", "refactor_code")
    print(f"测试Agent是否可以执行refactor_code: {can_refactor}")
    print()

    print("=" * 80)
    print("步骤3: 按能力和角色查找Agent")
    print("-" * 80)
    
    code_review_agents = coordinator.find_agents_by_capability(AgentCapability.CODE_REVIEW)
    print(f"具有CODE_REVIEW能力的Agent: {[a.name for a in code_review_agents]}")
    
    dev_agents = coordinator.find_agents_by_role("开发编码")
    print(f"角色为'开发编码'的Agent: {[a.name for a in dev_agents]}")
    print()

    print("=" * 80)
    print("步骤4: 能力和权限动态更新")
    print("-" * 80)
    
    update_success = coordinator.update_agent_capabilities(
        "TestingAgent",
        [
            AgentCapability.TEST_GENERATION,
            AgentCapability.REGRESSION_TEST,
            AgentCapability.COVERAGE_ANALYSIS,
            AgentCapability.QUALITY_CHECK
        ]
    )
    print(f"测试Agent能力更新: {update_success}")
    
    identity = coordinator.get_agent_identity("TestingAgent")
    print(f"测试Agent当前能力: {[c.value for c in identity.capabilities]}")
    print()

    print("=" * 80)
    print("步骤5: 创建工作流（带能力检查）")
    print("-" * 80)
    
    workflow = coordinator.create_workflow(
        "代码开发测试评审流程",
        "开发 -> 测试 -> 评审的完整流程",
        [
            {
                "agent_name": "DevelopmentAgent",
                "action": "generate_code",
                "params": {"prompt": "实现一个简单的计算器", "file_path": "/calculator.py"}
            },
            {
                "agent_name": "TestingAgent",
                "action": "generate_unit_tests",
                "params": {"source_file": "/calculator.py", "function_names": ["add", "subtract"]}
            },
            {
                "agent_name": "CodeReviewAgent",
                "action": "review_file",
                "params": {"file_path": "/calculator.py"}
            }
        ]
    )
    print(f"✅ 工作流创建: {workflow.name}")
    print(f"   任务数: {len(workflow.tasks)}")
    print()

    print("=" * 80)
    print("步骤6: 执行工作流（带权限和能力验证）")
    print("-" * 80)
    
    result = coordinator.execute_workflow(workflow.workflow_id)
    print(f"✅ 工作流执行完成")
    print(f"   状态: {result.status.value}")
    print(f"   完成任务: {sum(1 for t in result.tasks if t.status == TaskStatus.SUCCESS)}")
    print(f"   失败任务: {sum(1 for t in result.tasks if t.status == TaskStatus.FAILED)}")
    print()

    print("=" * 80)
    print("步骤7: 查看所有注册Agent详细信息")
    print("-" * 80)
    
    all_agents = coordinator.get_all_registered_agents()
    for agent in all_agents:
        print(f"\nAgent: {agent.name}")
        print(f"  ID: {agent.agent_id}")
        print(f"  角色: {agent.role}")
        print(f"  状态: {agent.status}")
        print(f"  能力: {[c.value for c in agent.capabilities]}")
        print(f"  权限: {[p.value for p in agent.permissions]}")
    print()

    print("=" * 80)
    print("步骤8: Agent状态管理")
    print("-" * 80)
    
    coordinator.set_agent_status("TestingAgent", "inactive")
    print(f"测试Agent状态设为 inactive")
    
    inactive_agent = coordinator.get_agent_identity("TestingAgent")
    print(f"测试Agent当前状态: {inactive_agent.status}")
    print()

    print("=" * 80)
    print("✅ 第40阶段演示完成 - Agent身份、能力、权限注册体系")
    print("=" * 80)


if __name__ == "__main__":
    demo_coordination_agent()
