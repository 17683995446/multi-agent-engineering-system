"""
HTD（Hierarchical Task Decomposition）层级任务拆解模块
遵循第一性原理：复用开源HTD思路，无自研核心算法
核心功能：
1. 将复杂任务逐层拆解为原子任务
2. 自动管理任务依赖关系
3. 支持多种拆解策略
4. 确保任务层级清晰、无遗漏冗余
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Callable
from datetime import datetime
from uuid import uuid4
import logging
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class TaskType(Enum):
    """任务类型"""
    REQUIREMENT = "requirement"  # 需求任务
    DESIGN = "design"  # 设计任务
    IMPLEMENTATION = "implementation"  # 实现任务
    TESTING = "testing"  # 测试任务
    DOCUMENTATION = "documentation"  # 文档任务
    REVIEW = "review"  # 评审任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"  # 待处理
    READY = "ready"  # 就绪
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成
    BLOCKED = "blocked"  # 阻塞


@dataclass
class HTDTask:
    """HTD任务"""
    entity_id: str
    name: str
    description: str
    task_type: TaskType
    level: int  # 层级深度，从0开始
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children: List["HTDTask"] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    status: TaskStatus = TaskStatus.PENDING
    is_atomic: bool = False  # 是否为原子任务
    estimated_effort: float = 1.0  # 预估工作量（小时）
    assigned_agent: Optional[str] = None
    tags: Set[str] = field(default_factory=set)


@dataclass
class DecompositionStrategy:
    """拆解策略"""
    name: str
    description: str
    decomposer: Callable[[HTDTask, int], List[HTDTask]]
    max_depth: int = 4
    min_subtasks: int = 2
    max_subtasks: int = 6


class HTDDecomposer:
    """
    HTD层级任务拆解器
    复用开源HTD算法思路，无自研核心逻辑
    """

    def __init__(self):
        self.decomposition_strategies: Dict[str, DecompositionStrategy] = {}
        self._register_default_strategies()
        logger.info("HTD层级任务拆解器初始化完成")

    def _register_default_strategies(self):
        """注册默认拆解策略"""
        # 策略1: 瀑布式拆解（需求→设计→实现→测试）
        self.decomposition_strategies["waterfall"] = DecompositionStrategy(
            name="waterfall",
            description="瀑布式拆解：需求→设计→实现→测试→文档",
            decomposer=self._waterfall_decompose,
            max_depth=4,
            min_subtasks=4,
            max_subtasks=6
        )

        # 策略2: 功能模块拆解
        self.decomposition_strategies["feature"] = DecompositionStrategy(
            name="feature",
            description="功能模块拆解：按功能模块分解",
            decomposer=self._feature_decompose,
            max_depth=3,
            min_subtasks=2,
            max_subtasks=8
        )

        # 策略3: 软件工程标准拆解
        self.decomposition_strategies["standard"] = DecompositionStrategy(
            name="standard",
            description="软件工程标准拆解：分析→设计→实现→测试→部署→文档",
            decomposer=self._standard_decompose,
            max_depth=5,
            min_subtasks=5,
            max_subtasks=8
        )

    def decompose(
        self,
        task: HTDTask,
        strategy_name: str = "standard",
        max_depth: Optional[int] = None
    ) -> HTDTask:
        """
        执行HTD层级任务拆解
        参数：
            task: 根任务
            strategy_name: 使用的拆解策略
            max_depth: 最大拆解深度（覆盖策略默认值）
        返回：
            完整的层级任务树
        """
        if strategy_name not in self.decomposition_strategies:
            raise ValueError(f"未知的拆解策略：{strategy_name}")

        strategy = self.decomposition_strategies[strategy_name]
        actual_max_depth = max_depth if max_depth is not None else strategy.max_depth

        logger.info(f"开始HTD拆解：{task.name}，策略：{strategy_name}，深度：{actual_max_depth}")

        # 从根任务开始递归拆解
        self._decompose_recursive(task, strategy, 0, actual_max_depth)

        # 自动建立依赖关系
        self._establish_dependencies(task)

        logger.info(f"HTD拆解完成：任务总数 {self._count_tasks(task)}")
        return task

    def _decompose_recursive(
        self,
        task: HTDTask,
        strategy: DecompositionStrategy,
        current_depth: int,
        max_depth: int
    ):
        """递归分解任务"""
        # 检查是否达到最大深度 - 此时将任务标记为原子
        if current_depth >= max_depth:
            task.is_atomic = True
            return

        # 使用策略拆解
        subtasks = strategy.decomposer(task, current_depth)

        # 验证子任务数量
        if len(subtasks) < strategy.min_subtasks:
            logger.warning(f"子任务数量过少：{len(subtasks)} < {strategy.min_subtasks}")
        if len(subtasks) > strategy.max_subtasks:
            subtasks = subtasks[:strategy.max_subtasks]
            logger.warning(f"子任务数量过多，截取前{strategy.max_subtasks}个")

        # 如果没有子任务，将当前任务标记为原子
        if not subtasks:
            task.is_atomic = True
            return

        # 关联子任务
        for subtask in subtasks:
            subtask.parent_id = task.entity_id
            subtask.level = current_depth + 1
            task.children.append(subtask)

        # 递归拆解子任务
        for subtask in task.children:
            self._decompose_recursive(subtask, strategy, current_depth + 1, max_depth)

    def _waterfall_decompose(self, task: HTDTask, current_depth: int) -> List[HTDTask]:
        """瀑布式拆解策略"""
        if current_depth == 0:
            return [
                HTDTask(
                    entity_id=f"{task.entity_id}_req",
                    name=f"需求分析：{task.name}",
                    description=f"分析需求：{task.description}",
                    task_type=TaskType.REQUIREMENT,
                    level=1,
                    tags={"analysis", "requirement"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_design",
                    name=f"系统设计：{task.name}",
                    description=f"设计系统架构：{task.description}",
                    task_type=TaskType.DESIGN,
                    level=1,
                    tags={"design", "architecture"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_impl",
                    name=f"代码实现：{task.name}",
                    description=f"实现功能：{task.description}",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"implementation", "coding"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_test",
                    name=f"测试验证：{task.name}",
                    description=f"测试功能：{task.description}",
                    task_type=TaskType.TESTING,
                    level=1,
                    tags={"testing", "validation"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_doc",
                    name=f"文档编写：{task.name}",
                    description=f"编写文档：{task.description}",
                    task_type=TaskType.DOCUMENTATION,
                    level=1,
                    tags={"documentation"}
                )
            ]
        elif current_depth == 1:
            if task.task_type == TaskType.REQUIREMENT:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_collect",
                        name="收集需求细节",
                        description="收集并整理详细需求",
                        task_type=TaskType.REQUIREMENT,
                        level=2,
                        is_atomic=True,
                        tags={"collection"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_constraints",
                        name="识别约束条件",
                        description="识别技术和业务约束",
                        task_type=TaskType.REQUIREMENT,
                        level=2,
                        is_atomic=True,
                        tags={"constraints"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_acceptance",
                        name="定义验收标准",
                        description="定义验收测试标准",
                        task_type=TaskType.REQUIREMENT,
                        level=2,
                        is_atomic=True,
                        tags={"acceptance"}
                    )
                ]
            elif task.task_type == TaskType.DESIGN:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_arch",
                        name="架构设计",
                        description="设计系统架构",
                        task_type=TaskType.DESIGN,
                        level=2,
                        is_atomic=True,
                        tags={"architecture"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_interface",
                        name="接口设计",
                        description="设计API接口",
                        task_type=TaskType.DESIGN,
                        level=2,
                        is_atomic=True,
                        tags={"interface", "api"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_data",
                        name="数据模型设计",
                        description="设计数据模型",
                        task_type=TaskType.DESIGN,
                        level=2,
                        is_atomic=True,
                        tags={"data", "model"}
                    )
                ]
            elif task.task_type == TaskType.IMPLEMENTATION:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_core",
                        name="核心代码实现",
                        description="编写核心功能代码",
                        task_type=TaskType.IMPLEMENTATION,
                        level=2,
                        is_atomic=True,
                        tags={"core"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_utils",
                        name="辅助功能实现",
                        description="实现辅助工具函数",
                        task_type=TaskType.IMPLEMENTATION,
                        level=2,
                        is_atomic=True,
                        tags={"utils"}
                    )
                ]
            elif task.task_type == TaskType.TESTING:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_unit",
                        name="单元测试",
                        description="编写单元测试",
                        task_type=TaskType.TESTING,
                        level=2,
                        is_atomic=True,
                        tags={"unit-test"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_integration",
                        name="集成测试",
                        description="编写集成测试",
                        task_type=TaskType.TESTING,
                        level=2,
                        is_atomic=True,
                        tags={"integration-test"}
                    )
                ]
        return []

    def _feature_decompose(self, task: HTDTask, current_depth: int) -> List[HTDTask]:
        """功能模块拆解策略"""
        if current_depth == 0:
            # 第一层：按功能模块拆分
            return [
                HTDTask(
                    entity_id=f"{task.entity_id}_ui",
                    name="用户界面模块",
                    description="开发用户界面组件",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"ui", "frontend"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_backend",
                    name="后端逻辑模块",
                    description="开发后端业务逻辑",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"backend", "logic"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_db",
                    name="数据模块",
                    description="开发数据访问层",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"database", "persistence"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_api",
                    name="API模块",
                    description="开发API接口",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"api", "integration"}
                )
            ]
        return []

    def _standard_decompose(self, task: HTDTask, current_depth: int) -> List[HTDTask]:
        """软件工程标准拆解策略"""
        if current_depth == 0:
            return [
                HTDTask(
                    entity_id=f"{task.entity_id}_analysis",
                    name="问题分析",
                    description="分析问题并确定范围",
                    task_type=TaskType.REQUIREMENT,
                    level=1,
                    tags={"analysis"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_design",
                    name="方案设计",
                    description="设计解决方案",
                    task_type=TaskType.DESIGN,
                    level=1,
                    tags={"design"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_implement",
                    name="编码实现",
                    description="编写代码实现",
                    task_type=TaskType.IMPLEMENTATION,
                    level=1,
                    tags={"coding"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_test",
                    name="测试验证",
                    description="全面测试验证",
                    task_type=TaskType.TESTING,
                    level=1,
                    tags={"testing"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_review",
                    name="代码评审",
                    description="进行代码评审",
                    task_type=TaskType.REVIEW,
                    level=1,
                    tags={"review"}
                ),
                HTDTask(
                    entity_id=f"{task.entity_id}_doc",
                    name="文档记录",
                    description="编写相关文档",
                    task_type=TaskType.DOCUMENTATION,
                    level=1,
                    tags={"documentation"}
                )
            ]
        elif current_depth == 1:
            # 第二级继续拆解
            if task.task_type == TaskType.REQUIREMENT:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_req1",
                        name="收集需求",
                        description="收集并整理需求",
                        task_type=TaskType.REQUIREMENT,
                        level=2,
                        is_atomic=True,
                        tags={"collection"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_req2",
                        name="定义范围",
                        description="定义项目范围",
                        task_type=TaskType.REQUIREMENT,
                        level=2,
                        is_atomic=True,
                        tags={"scope"}
                    )
                ]
            elif task.task_type == TaskType.DESIGN:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_des1",
                        name="架构设计",
                        description="设计系统架构",
                        task_type=TaskType.DESIGN,
                        level=2,
                        is_atomic=True,
                        tags={"architecture"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_des2",
                        name="接口设计",
                        description="设计API接口",
                        task_type=TaskType.DESIGN,
                        level=2,
                        is_atomic=True,
                        tags={"interface"}
                    )
                ]
            elif task.task_type == TaskType.IMPLEMENTATION:
                return [
                    HTDTask(
                        entity_id=f"{task.entity_id}_impl1",
                        name="核心功能",
                        description="实现核心功能",
                        task_type=TaskType.IMPLEMENTATION,
                        level=2,
                        is_atomic=True,
                        tags={"core"}
                    ),
                    HTDTask(
                        entity_id=f"{task.entity_id}_impl2",
                        name="辅助功能",
                        description="实现辅助功能",
                        task_type=TaskType.IMPLEMENTATION,
                        level=2,
                        is_atomic=True,
                        tags={"utils"}
                    )
                ]
        return []

    def _establish_dependencies(self, root: HTDTask):
        """建立任务间的依赖关系"""
        # 策略：子任务依赖父任务完成
        # 同一层级的任务，按顺序建立依赖
        all_tasks = self._flatten_tasks(root)

        # 按层级分组
        tasks_by_level: Dict[int, List[HTDTask]] = {}
        for task in all_tasks:
            if task.level not in tasks_by_level:
                tasks_by_level[task.level] = []
            tasks_by_level[task.level].append(task)

        # 同一层级内建立顺序依赖
        for level, tasks in tasks_by_level.items():
            for i in range(1, len(tasks)):
                tasks[i].dependencies.append(tasks[i - 1].entity_id)

        logger.debug(f"依赖关系建立完成")

    def _count_tasks(self, task: HTDTask) -> int:
        """统计任务总数"""
        count = 1
        for child in task.children:
            count += self._count_tasks(child)
        return count

    def _flatten_tasks(self, task: HTDTask) -> List[HTDTask]:
        """扁平化任务树"""
        result = [task]
        for child in task.children:
            result.extend(self._flatten_tasks(child))
        return result

    def get_task(self, root: HTDTask, task_id: str) -> Optional[HTDTask]:
        """获取指定ID的任务"""
        all_tasks = self._flatten_tasks(root)
        for task in all_tasks:
            if task.entity_id == task_id:
                return task
        return None

    def get_atomic_tasks(self, root: HTDTask) -> List[HTDTask]:
        """获取所有原子任务"""
        all_tasks = self._flatten_tasks(root)
        return [t for t in all_tasks if t.is_atomic]

    def get_ready_tasks(self, root: HTDTask) -> List[HTDTask]:
        """获取就绪的任务"""
        all_tasks = self._flatten_tasks(root)
        ready_tasks = []

        for task in all_tasks:
            if task.status == TaskStatus.PENDING:
                # 检查所有依赖是否完成
                all_deps_completed = True
                for dep_id in task.dependencies:
                    dep_task = self.get_task(root, dep_id)
                    if dep_task and dep_task.status != TaskStatus.COMPLETED:
                        all_deps_completed = False
                        break

                if all_deps_completed:
                    task.status = TaskStatus.READY
                    ready_tasks.append(task)

        return ready_tasks

    def to_dict(self, task: HTDTask) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "entity_id": task.entity_id,
            "name": task.name,
            "description": task.description,
            "task_type": task.task_type.value,
            "level": task.level,
            "parent_id": task.parent_id,
            "dependencies": task.dependencies,
            "status": task.status.value,
            "is_atomic": task.is_atomic,
            "estimated_effort": task.estimated_effort,
            "assigned_agent": task.assigned_agent,
            "tags": list(task.tags),
            "children": [self.to_dict(child) for child in task.children]
        }

    def to_flat_list(self, task: HTDTask) -> List[Dict[str, Any]]:
        """转换为扁平化列表"""
        result = [self.to_dict(task)]
        for child in task.children:
            result.extend(self.to_flat_list(child))
        return result


# 便捷函数
def create_htd_task(
    name: str,
    description: str,
    task_type: TaskType = TaskType.REQUIREMENT
) -> HTDTask:
    """创建HTD任务"""
    return HTDTask(
        entity_id=f"task_{uuid4().hex[:8]}",
        name=name,
        description=description,
        task_type=task_type,
        level=0
    )


def decompose_task(
    requirement: str,
    strategy: str = "standard",
    max_depth: int = 3
) -> Dict[str, Any]:
    """
    便捷函数：直接拆解需求
    参数：
        requirement: 需求描述
        strategy: 拆解策略
        max_depth: 最大深度
    返回：
        拆解结果字典
    """
    decomposer = HTDDecomposer()
    task = create_htd_task(requirement, requirement, TaskType.REQUIREMENT)
    result_task = decomposer.decompose(task, strategy, max_depth)

    atomic_tasks = decomposer.get_atomic_tasks(result_task)

    return {
        "root": decomposer.to_dict(result_task),
        "all_tasks": decomposer.to_flat_list(result_task),
        "atomic_tasks": [decomposer.to_dict(t) for t in atomic_tasks],
        "summary": {
            "total_tasks": len(decomposer.to_flat_list(result_task)),
            "atomic_count": len(atomic_tasks),
            "strategy_used": strategy,
            "max_depth_used": max_depth
        }
    }
