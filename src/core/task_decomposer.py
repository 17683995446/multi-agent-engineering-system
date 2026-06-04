"""
任务分解模块
遵循项目规范
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """任务优先级枚举"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskNode:
    """任务节点

    Args:
        task_id: 任务唯一标识
        name: 任务名称
        description: 任务描述
        status: 任务状态
        priority: 优先级
        parent: 父任务ID
        children: 子任务列表
        dependencies: 依赖任务ID列表

    Returns:
        TaskNode实例
    """
    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    parent: Optional[str] = None
    children: List['TaskNode'] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def is_leaf(self) -> bool:
        """是否为叶子节点

        Returns:
            是否为叶子
        """
        return len(self.children) == 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            字典表示
        """
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "is_leaf": self.is_leaf()
        }


class TaskDecomposer:
    """任务分解器

    将需求分解为可执行任务树
    """

    def __init__(self, name: str) -> None:
        """初始化分解器

        Args:
            name: 分解器名称
        """
        self.name = name
        self._counter = 0

    def _next_id(self) -> str:
        """生成下一个任务ID

        Returns:
            新任务ID
        """
        self._counter += 1
        return f"task_{self._counter:03d}"

    def decompose(self, requirement: str) -> TaskNode:
        """分解需求为任务树

        Args:
            requirement: 需求描述

        Returns:
            任务树根节点
        """
        root = TaskNode(
            task_id=self._next_id(),
            name=f"需求: {requirement[:30]}",
            description=requirement
        )
        self._add_analysis_task(root)
        self._add_design_task(root)
        self._add_coding_task(root)
        self._add_testing_task(root)
        self._add_review_task(root)
        return root

    def _add_analysis_task(self, root: TaskNode) -> None:
        """添加分析任务

        Args:
            root: 根节点
        """
        task = TaskNode(
            task_id=self._next_id(),
            name="需求分析",
            description="分析需求明确功能点",
            parent=root.task_id
        )
        root.children.append(task)

    def _add_design_task(self, root: TaskNode) -> None:
        """添加设计任务

        Args:
            root: 根节点
        """
        task = TaskNode(
            task_id=self._next_id(),
            name="架构设计",
            description="设计模块结构和接口",
            parent=root.task_id,
            dependencies=[root.children[0].task_id]
        )
        root.children.append(task)

    def _add_coding_task(self, root: TaskNode) -> None:
        """添加编码任务

        Args:
            root: 根节点
        """
        task = TaskNode(
            task_id=self._next_id(),
            name="编码实现",
            description="编写代码实现功能",
            parent=root.task_id,
            dependencies=[root.children[1].task_id]
        )
        root.children.append(task)

    def _add_testing_task(self, root: TaskNode) -> None:
        """添加测试任务

        Args:
            root: 根节点
        """
        task = TaskNode(
            task_id=self._next_id(),
            name="单元测试",
            description="编写并运行单元测试",
            parent=root.task_id,
            dependencies=[root.children[2].task_id]
        )
        root.children.append(task)

    def _add_review_task(self, root: TaskNode) -> None:
        """添加审查任务

        Args:
            root: 根节点
        """
        task = TaskNode(
            task_id=self._next_id(),
            name="代码审查",
            description="审查代码质量",
            parent=root.task_id,
            dependencies=[root.children[2].task_id]
        )
        root.children.append(task)

    def get_leaf_tasks(self, root: TaskNode) -> List[TaskNode]:
        """获取所有叶子任务

        Args:
            root: 根节点

        Returns:
            叶子任务列表
        """
        leaves = []
        self._collect_leaves(root, leaves)
        return leaves

    def _collect_leaves(
        self,
        node: TaskNode,
        leaves: List[TaskNode]
    ) -> None:
        """递归收集叶子节点

        Args:
            node: 当前节点
            leaves: 收集列表
        """
        if node.is_leaf():
            leaves.append(node)
        for child in node.children:
            self._collect_leaves(child, leaves)
