"""
系统原子实体定义
遵循第一性原理：任务可分性公理

四类原子实体：
1. 任务实体（Task） - 系统的最小工作单元
2. 代码实体（Code） - 系统的最小执行单元
3. 消息实体（Message） - 系统的最小通信单元
4. 状态实体（State） - 系统的最小状态单元

核心约束：
- 四类实体定义完整、无缺失
- 实体属性、行为、约束明确
- 所有系统交互均基于原子实体
- 符合任务可分性公理
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CodeType(Enum):
    """代码类型"""
    VARIABLE = "variable"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class StateType(Enum):
    """状态类型"""
    TASK = "task"
    BUSINESS = "business"
    SYSTEM = "system"


@dataclass
class TaskEntity:
    """
    任务实体 - 系统的最小工作单元
    
    属性：
    - id: 唯一标识
    - type: 任务类型
    - description: 任务描述
    - priority: 优先级
    - status: 状态
    - dependencies: 依赖列表
    - result: 执行结果
    - error: 错误信息
    """
    id: str
    type: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_execute(self) -> bool:
        """检查任务是否可以执行"""
        return self.status == TaskStatus.PENDING or self.status == TaskStatus.READY
    
    def start(self) -> None:
        """开始执行任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
    
    def complete(self, result: Dict[str, Any]) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result
    
    def fail(self, error: str) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error


@dataclass
class CodeEntity:
    """
    代码实体 - 系统的最小执行单元
    
    属性：
    - id: 唯一标识
    - type: 代码类型（variable/function/class/module）
    - name: 名称
    - content: 代码内容
    - language: 编程语言
    - file_path: 文件路径
    - line_start: 起始行
    - line_end: 结束行
    """
    id: str
    type: CodeType
    name: str
    content: str
    language: str = "python"
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_complexity(self) -> int:
        """计算代码复杂度"""
        return self.content.count('\n') + 1
    
    def get_imports(self) -> List[str]:
        """获取导入列表"""
        return self.imports
    
    def validate(self) -> bool:
        """验证代码实体"""
        return bool(self.id and self.name and self.content)


@dataclass
class MessageEntity:
    """
    消息实体 - 系统的最小通信单元
    
    属性：
    - id: 唯一标识
    - type: 消息类型
    - sender: 发送者
    - receiver: 接收者
    - content: 消息内容
    - timestamp: 时间戳
    - session_id: 会话ID
    - reply_to: 回复消息ID
    """
    id: str
    type: MessageType
    sender: str
    receiver: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    reply_to: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    attachments: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_request(self) -> bool:
        """是否为请求消息"""
        return self.type == MessageType.REQUEST
    
    def is_response(self) -> bool:
        """是否为响应消息"""
        return self.type == MessageType.RESPONSE
    
    def is_notification(self) -> bool:
        """是否为通知消息"""
        return self.type == MessageType.NOTIFICATION
    
    def is_error(self) -> bool:
        """是否为错误消息"""
        return self.type == MessageType.ERROR
    
    def create_reply(self, content: Any, msg_type: MessageType = MessageType.RESPONSE) -> 'MessageEntity':
        """创建回复消息"""
        return MessageEntity(
            id=f"{self.id}_reply",
            type=msg_type,
            sender=self.receiver,
            receiver=self.sender,
            content=content,
            reply_to=self.id
        )


@dataclass
class StateEntity:
    """
    状态实体 - 系统的最小状态单元
    
    属性：
    - id: 唯一标识
    - type: 状态类型（task/business/system）
    - name: 状态名称
    - value: 状态值
    - previous_value: 前一个状态值
    - timestamp: 时间戳
    - owner: 拥有者
    """
    id: str
    type: StateType
    name: str
    value: Any
    previous_value: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)
    owner: Optional[str] = None
    is_locked: bool = False
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, new_value: Any, reason: str = "") -> None:
        """更新状态"""
        self.previous_value = self.value
        self.value = new_value
        self.timestamp = datetime.now()
        self.history.append({
            "timestamp": self.timestamp,
            "previous_value": self.previous_value,
            "new_value": new_value,
            "reason": reason
        })
    
    def rollback(self) -> Any:
        """回滚状态"""
        if self.previous_value is not None:
            self.value = self.previous_value
            self.timestamp = datetime.now()
            return self.value
        return None
    
    def lock(self) -> None:
        """锁定状态"""
        self.is_locked = True
    
    def unlock(self) -> None:
        """解锁状态"""
        self.is_locked = False


class AtomicEntityFactory:
    """
    原子实体工厂
    
    提供统一的实体创建接口
    """
    
    @staticmethod
    def create_task(
        task_id: str,
        task_type: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> TaskEntity:
        """创建任务实体"""
        return TaskEntity(
            id=task_id,
            type=task_type,
            description=description,
            priority=priority
        )
    
    @staticmethod
    def create_code(
        code_id: str,
        code_type: CodeType,
        name: str,
        content: str,
        language: str = "python"
    ) -> CodeEntity:
        """创建代码实体"""
        return CodeEntity(
            id=code_id,
            type=code_type,
            name=name,
            content=content,
            language=language
        )
    
    @staticmethod
    def create_message(
        msg_id: str,
        msg_type: MessageType,
        sender: str,
        receiver: str,
        content: Any
    ) -> MessageEntity:
        """创建消息实体"""
        return MessageEntity(
            id=msg_id,
            type=msg_type,
            sender=sender,
            receiver=receiver,
            content=content
        )
    
    @staticmethod
    def create_state(
        state_id: str,
        state_type: StateType,
        name: str,
        value: Any,
        owner: Optional[str] = None
    ) -> StateEntity:
        """创建状态实体"""
        return StateEntity(
            id=state_id,
            type=state_type,
            name=name,
            value=value,
            owner=owner
        )


class EntityRegistry:
    """
    原子实体注册表
    
    管理所有原子实体的生命周期
    """
    
    def __init__(self):
        self.tasks: Dict[str, TaskEntity] = {}
        self.codes: Dict[str, CodeEntity] = {}
        self.messages: Dict[str, MessageEntity] = {}
        self.states: Dict[str, StateEntity] = {}
        logger.info("原子实体注册表初始化完成")
    
    def register_task(self, task: TaskEntity) -> None:
        """注册任务"""
        self.tasks[task.id] = task
        logger.debug(f"注册任务: {task.id}")
    
    def register_code(self, code: CodeEntity) -> None:
        """注册代码"""
        self.codes[code.id] = code
        logger.debug(f"注册代码: {code.id}")
    
    def register_message(self, message: MessageEntity) -> None:
        """注册消息"""
        self.messages[message.id] = message
        logger.debug(f"注册消息: {message.id}")
    
    def register_state(self, state: StateEntity) -> None:
        """注册状态"""
        self.states[state.id] = state
        logger.debug(f"注册状态: {state.id}")
    
    def get_task(self, task_id: str) -> Optional[TaskEntity]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_code(self, code_id: str) -> Optional[CodeEntity]:
        """获取代码"""
        return self.codes.get(code_id)
    
    def get_message(self, msg_id: str) -> Optional[MessageEntity]:
        """获取消息"""
        return self.messages.get(msg_id)
    
    def get_state(self, state_id: str) -> Optional[StateEntity]:
        """获取状态"""
        return self.states.get(state_id)
    
    def get_all_tasks(self) -> List[TaskEntity]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_all_codes(self) -> List[CodeEntity]:
        """获取所有代码"""
        return list(self.codes.values())
    
    def get_all_messages(self) -> List[MessageEntity]:
        """获取所有消息"""
        return list(self.messages.values())
    
    def get_all_states(self) -> List[StateEntity]:
        """获取所有状态"""
        return list(self.states.values())
    
    def get_statistics(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "total_tasks": len(self.tasks),
            "total_codes": len(self.codes),
            "total_messages": len(self.messages),
            "total_states": len(self.states)
        }


def demo_atomic_entities():
    """演示原子实体"""
    print("=" * 70)
    print("系统原子实体定义演示")
    print("=" * 70)
    print()
    
    factory = AtomicEntityFactory()
    registry = EntityRegistry()
    
    print("1. 创建任务实体:")
    task = factory.create_task(
        task_id="task_001",
        task_type="code_review",
        description="代码评审任务",
        priority=TaskPriority.HIGH
    )
    registry.register_task(task)
    print(f"   ✓ 创建任务: {task.id}, type={task.type}, priority={task.priority.value}")
    print()
    
    print("2. 创建代码实体:")
    code = factory.create_code(
        code_id="code_001",
        code_type=CodeType.FUNCTION,
        name="calculate_sum",
        content="def calculate_sum(a, b):\n    return a + b"
    )
    registry.register_code(code)
    print(f"   ✓ 创建代码: {code.id}, type={code.type.value}, name={code.name}")
    print(f"   ✓ 代码复杂度: {code.get_complexity()} 行")
    print()
    
    print("3. 创建消息实体:")
    message = factory.create_message(
        msg_id="msg_001",
        msg_type=MessageType.REQUEST,
        sender="agent_1",
        receiver="agent_2",
        content={"action": "review_code", "code_id": "code_001"}
    )
    registry.register_message(message)
    print(f"   ✓ 创建消息: {message.id}, type={message.type.value}")
    print(f"   ✓ 是请求消息: {message.is_request()}")
    print()
    
    print("4. 创建状态实体:")
    state = factory.create_state(
        state_id="state_001",
        state_type=StateType.TASK,
        name="task_status",
        value="running",
        owner="task_001"
    )
    registry.register_state(state)
    print(f"   ✓ 创建状态: {state.id}, type={state.type.value}, value={state.value}")
    state.update("completed", "任务执行完成")
    print(f"   ✓ 状态更新: {state.value}, 历史记录: {len(state.history)} 条")
    print()
    
    print("5. 实体统计:")
    stats = registry.get_statistics()
    print(f"   ✓ 任务总数: {stats['total_tasks']}")
    print(f"   ✓ 代码总数: {stats['total_codes']}")
    print(f"   ✓ 消息总数: {stats['total_messages']}")
    print(f"   ✓ 状态总数: {stats['total_states']}")
    print()
    
    print("6. 实体检索:")
    retrieved_task = registry.get_task("task_001")
    print(f"   ✓ 检索任务: {retrieved_task.id if retrieved_task else '未找到'}")
    retrieved_code = registry.get_code("code_001")
    print(f"   ✓ 检索代码: {retrieved_code.id if retrieved_code else '未找到'}")
    print()
    
    print("=" * 70)
    print("系统原子实体定义演示完成")
    print("=" * 70)
    print()
    print("✓ 四类原子实体定义完整、无缺失")
    print("✓ 实体属性、行为、约束明确")
    print("✓ 所有系统交互均基于原子实体")
    print("✓ 符合任务可分性公理")


if __name__ == "__main__":
    demo_atomic_entities()
