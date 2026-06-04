"""
MVP阶段2: 任务分解HTD算法
遵循第一性原理：任务可分性公理

HTD (Hierarchical Task Decomposition) 层次任务分解
将复杂需求分解为可执行的原子任务
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskNode:
    """
    任务节点 - HTD树的基本单元
    
    属性：
    - task_id: 任务唯一标识
    - name: 任务名称
    - description: 任务描述
    - status: 任务状态
    - priority: 优先级
    - parent: 父任务ID
    - children: 子任务列表
    - dependencies: 依赖任务ID列表
    - assignee: 执行者Agent
    - result: 执行结果
    """
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    parent: Optional[str] = None
    children: List['TaskNode'] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    assignee: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def is_leaf(self) -> bool:
        """是否为叶子节点（原子任务）"""
        return len(self.children) == 0
    
    def is_ready(self) -> bool:
        """是否准备好执行"""
        return self.status == TaskStatus.PENDING and all(
            dep.status in [TaskStatus.COMPLETED, TaskStatus.READY]
            for dep in self.dependencies
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "parent": self.parent,
            "children": [child.to_dict() for child in self.children],
            "dependencies": self.dependencies,
            "assignee": self.assignee,
            "is_leaf": self.is_leaf(),
            "result": self.result
        }


class HTDDecomposer:
    """
    HTD层次任务分解器
    
    核心方法：
    - decompose: 分解任务
    - get_leaf_tasks: 获取所有叶子任务
    - get_ready_tasks: 获取可执行任务
    - update_task_status: 更新任务状态
    """
    
    def __init__(self, name: str = "htd_decomposer"):
        """初始化分解器"""
        self.name = name
        self._task_counter = 0
        logger.info(f"HTD分解器初始化: {name}")
    
    def _next_id(self) -> str:
        """生成下一个任务ID"""
        self._task_counter += 1
        return f"task_{self._task_counter:03d}"
    
    def decompose(self, requirement: str, context: Optional[Dict[str, Any]] = None) -> TaskNode:
        """
        分解需求为任务树
        
        策略：
        1. 识别需求类型（开发/测试/文档/重构）
        2. 根据类型选择分解模板
        3. 生成任务树
        """
        logger.info(f"开始分解需求: {requirement[:50]}...")
        
        context = context or {}
        req_type = self._detect_requirement_type(requirement)
        
        root = TaskNode(
            task_id=self._next_id(),
            name=f"需求: {requirement[:30]}",
            description=requirement,
            priority=TaskPriority.HIGH
        )
        
        if req_type == "development":
            self._decompose_development(root, requirement, context)
        elif req_type == "testing":
            self._decompose_testing(root, requirement, context)
        elif req_type == "documentation":
            self._decompose_documentation(root, requirement, context)
        elif req_type == "refactoring":
            self._decompose_refactoring(root, requirement, context)
        else:
            self._decompose_generic(root, requirement, context)
        
        logger.info(f"分解完成: {self._count_tasks(root)} 个任务")
        return root
    
    def _detect_requirement_type(self, requirement: str) -> str:
        """检测需求类型"""
        req_lower = requirement.lower()
        
        # 优先级：测试 > 文档 > 重构 > 开发
        if any(kw in req_lower for kw in ["测试", "test case", "test suite", "单元测试", "集成测试"]):
            return "testing"
        elif any(kw in req_lower for kw in ["文档", "doc", "说明", "readme", "documentation"]):
            return "documentation"
        elif any(kw in req_lower for kw in ["重构", "refactor", "代码优化", "性能优化"]):
            return "refactoring"
        elif any(kw in req_lower for kw in ["实现", "开发", "创建", "添加", "implement", "create", "add", "build", "开发"]):
            return "development"
        else:
            return "generic"
    
    def _decompose_development(self, root: TaskNode, requirement: str, context: Dict[str, Any]) -> None:
        """分解开发类需求"""
        # 需求分析
        analysis = TaskNode(
            task_id=self._next_id(),
            name="需求分析",
            description="分析需求，明确功能点和边界",
            parent=root.task_id,
            priority=TaskPriority.HIGH
        )
        
        # 架构设计
        design = TaskNode(
            task_id=self._next_id(),
            name="架构设计",
            description="设计模块结构和接口",
            parent=root.task_id,
            priority=TaskPriority.HIGH,
            dependencies=[analysis.task_id]
        )
        
        # 编码实现
        coding = TaskNode(
            task_id=self._next_id(),
            name="编码实现",
            description="编写代码实现功能",
            parent=root.task_id,
            priority=TaskPriority.CRITICAL,
            dependencies=[design.task_id]
        )
        
        # 单元测试
        testing = TaskNode(
            task_id=self._next_id(),
            name="单元测试",
            description="编写并运行单元测试",
            parent=root.task_id,
            priority=TaskPriority.HIGH,
            dependencies=[coding.task_id]
        )
        
        # 代码审查
        review = TaskNode(
            task_id=self._next_id(),
            name="代码审查",
            description="审查代码质量",
            parent=root.task_id,
            priority=TaskPriority.MEDIUM,
            dependencies=[coding.task_id]
        )
        
        root.children = [analysis, design, coding, testing, review]
    
    def _decompose_testing(self, root: TaskNode, requirement: str, context: Dict[str, Any]) -> None:
        """分解测试类需求"""
        # 测试计划
        plan = TaskNode(
            task_id=self._next_id(),
            name="测试计划",
            description="制定测试策略和范围",
            parent=root.task_id,
            priority=TaskPriority.HIGH
        )
        
        # 测试用例设计
        cases = TaskNode(
            task_id=self._next_id(),
            name="测试用例设计",
            description="设计测试用例",
            parent=root.task_id,
            priority=TaskPriority.HIGH,
            dependencies=[plan.task_id]
        )
        
        # 测试执行
        execute = TaskNode(
            task_id=self._next_id(),
            name="测试执行",
            description="执行测试并记录结果",
            parent=root.task_id,
            priority=TaskPriority.CRITICAL,
            dependencies=[cases.task_id]
        )
        
        # 报告生成
        report = TaskNode(
            task_id=self._next_id(),
            name="测试报告",
            description="生成测试报告",
            parent=root.task_id,
            priority=TaskPriority.MEDIUM,
            dependencies=[execute.task_id]
        )
        
        root.children = [plan, cases, execute, report]
    
    def _decompose_documentation(self, root: TaskNode, requirement: str, context: Dict[str, Any]) -> None:
        """分解文档类需求"""
        # 文档规划
        plan = TaskNode(
            task_id=self._next_id(),
            name="文档规划",
            description="确定文档类型和结构",
            parent=root.task_id,
            priority=TaskPriority.HIGH
        )
        
        # 内容编写
        write = TaskNode(
            task_id=self._next_id(),
            name="内容编写",
            description="编写文档内容",
            parent=root.task_id,
            priority=TaskPriority.CRITICAL,
            dependencies=[plan.task_id]
        )
        
        # 审核校对
        review = TaskNode(
            task_id=self._next_id(),
            name="审核校对",
            description="检查文档质量",
            parent=root.task_id,
            priority=TaskPriority.MEDIUM,
            dependencies=[write.task_id]
        )
        
        root.children = [plan, write, review]
    
    def _decompose_refactoring(self, root: TaskNode, requirement: str, context: Dict[str, Any]) -> None:
        """分解重构类需求"""
        # 代码分析
        analysis = TaskNode(
            task_id=self._next_id(),
            name="代码分析",
            description="分析现有代码问题",
            parent=root.task_id,
            priority=TaskPriority.HIGH
        )
        
        # 重构实施
        refactor = TaskNode(
            task_id=self._next_id(),
            name="重构实施",
            description="执行重构操作",
            parent=root.task_id,
            priority=TaskPriority.CRITICAL,
            dependencies=[analysis.task_id]
        )
        
        # 回归测试
        test = TaskNode(
            task_id=self._next_id(),
            name="回归测试",
            description="验证重构后功能正常",
            parent=root.task_id,
            priority=TaskPriority.HIGH,
            dependencies=[refactor.task_id]
        )
        
        root.children = [analysis, refactor, test]
    
    def _decompose_generic(self, root: TaskNode, requirement: str, context: Dict[str, Any]) -> None:
        """通用分解策略"""
        # 分析
        analysis = TaskNode(
            task_id=self._next_id(),
            name="分析",
            description="分析需求和现状",
            parent=root.task_id,
            priority=TaskPriority.HIGH
        )
        
        # 执行
        execute = TaskNode(
            task_id=self._next_id(),
            name="执行",
            description="执行具体任务",
            parent=root.task_id,
            priority=TaskPriority.CRITICAL,
            dependencies=[analysis.task_id]
        )
        
        # 验证
        verify = TaskNode(
            task_id=self._next_id(),
            name="验证",
            description="验证执行结果",
            parent=root.task_id,
            priority=TaskPriority.HIGH,
            dependencies=[execute.task_id]
        )
        
        root.children = [analysis, execute, verify]
    
    def get_leaf_tasks(self, root: TaskNode) -> List[TaskNode]:
        """获取所有叶子任务"""
        leaves = []
        
        def collect(node: TaskNode):
            if node.is_leaf():
                leaves.append(node)
            for child in node.children:
                collect(child)
        
        collect(root)
        return leaves
    
    def get_ready_tasks(self, root: TaskNode) -> List[TaskNode]:
        """获取可执行的任务（状态为PENDING且依赖已完成）"""
        ready = []
        
        def check(node: TaskNode):
            if node.status == TaskStatus.PENDING:
                # 检查依赖是否完成
                deps_completed = all(
                    self._find_task(root, dep_id).status == TaskStatus.COMPLETED
                    for dep_id in node.dependencies
                ) if node.dependencies else True
                
                if deps_completed:
                    ready.append(node)
            
            for child in node.children:
                check(child)
        
        check(root)
        return ready
    
    def _find_task(self, root: TaskNode, task_id: str) -> Optional[TaskNode]:
        """在树中查找任务"""
        if root.task_id == task_id:
            return root
        for child in root.children:
            result = self._find_task(child, task_id)
            if result:
                return result
        return None
    
    def update_task_status(self, root: TaskNode, task_id: str, status: TaskStatus) -> bool:
        """更新任务状态"""
        task = self._find_task(root, task_id)
        if task:
            task.status = status
            logger.info(f"任务状态更新: {task_id} -> {status.value}")
            return True
        return False
    
    def _count_tasks(self, root: TaskNode) -> int:
        """统计任务数量"""
        count = 1
        for child in root.children:
            count += self._count_tasks(child)
        return count
    
    def get_task_tree(self, root: TaskNode) -> Dict[str, Any]:
        """获取任务树结构"""
        return root.to_dict()
