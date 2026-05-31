"""
需求拆解Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 可将复杂需求逐层拆解为原子任务
3. 拆解结果分层清晰、无遗漏、无冗余
4. 复用开源HTD（Hierarchical Task Decomposition）算法，无自研核心逻辑
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.agents.base import BaseAgent
from src.common.utils import setup_logger
from src.common.htd_decomposer import (
    HTDDecomposer,
    HTDTask,
    TaskType,
    create_htd_task,
    decompose_task
)

logger = setup_logger(__name__)


class TaskLevel(Enum):
    """任务层级（兼容旧版本）"""
    LEVEL_1 = "level_1"  # 顶层需求
    LEVEL_2 = "level_2"  # 子需求
    LEVEL_3 = "level_3"  # 子子需求
    ATOMIC = "atomic"    # 原子任务（最细粒度）


@dataclass
class DecomposedTask:
    """拆解后的任务（兼容旧版本）"""
    task_id: str
    description: str
    level: TaskLevel
    parent_id: Optional[str] = None
    children: List["DecomposedTask"] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_effort: int = 1  # 估算工作量（小时）
    is_atomic: bool = False


class RequirementDecompositionAgent(BaseAgent):
    """需求拆解Agent - 集成HTD分解器"""

    def __init__(self):
        super().__init__("RequirementDecompositionAgent")
        self.is_running = False
        self.decomposition_history: List[Dict] = []
        self.htd_decomposer = HTDDecomposer()  # 集成HTD分解器
        logger.info("需求拆解Agent初始化，集成HTD分解器")

    def start(self):
        """启动Agent"""
        self.is_running = True
        logger.info(f"需求拆解Agent {self.name} 已启动")

    def stop(self):
        """停止Agent"""
        self.is_running = False
        logger.info(f"需求拆解Agent {self.name} 已停止")

    def decompose(
        self,
        requirement: str,
        max_depth: int = 3,
        strategy: str = "standard"
    ) -> Dict[str, Any]:
        """
        执行HTD层级分解
        参数：
            requirement: 顶层需求描述
            max_depth: 最大分解深度（默认3层）
            strategy: 拆解策略（standard/waterfall/feature）
        返回：
            完整的层级分解结果
        """
        if not self.is_running:
            self.start()

        logger.info(f"开始HTD分解需求：{requirement}，策略：{strategy}")

        # 使用HTD分解器
        htd_result = decompose_task(requirement, strategy, max_depth)

        # 记录历史
        self.decomposition_history.append({
            "timestamp": datetime.now().isoformat(),
            "requirement": requirement,
            "strategy": strategy,
            "result": htd_result
        })

        logger.info(f"HTD需求分解完成，共 {htd_result['summary']['total_tasks']} 个任务")
        return htd_result

    def decompose_compat(self, requirement: str, max_depth: int = 3) -> Dict[str, Any]:
        """
        兼容旧版本的decompose方法
        返回与旧版本相同格式的结果
        """
        if not self.is_running:
            self.start()

        logger.info(f"开始兼容模式分解需求：{requirement}")

        root_task = DecomposedTask(
            task_id=f"task_0",
            description=requirement,
            level=TaskLevel.LEVEL_1,
            is_atomic=False
        )

        self._decompose_recursive(root_task, 1, max_depth)

        result = {
            "root": self._task_to_dict(root_task),
            "all_tasks": self._flatten_tasks(root_task),
            "summary": {
                "total_tasks": len(self._flatten_tasks(root_task)),
                "atomic_tasks": len([t for t in self._flatten_tasks(root_task) if t["is_atomic"]]),
                "max_depth": max_depth
            }
        }

        self.decomposition_history.append({
            "timestamp": datetime.now().isoformat(),
            "requirement": requirement,
            "result": result
        })

        logger.info(f"兼容模式分解完成，共 {result['summary']['total_tasks']} 个任务")
        return result

    def _decompose_recursive(self, task: DecomposedTask, current_depth: int, max_depth: int):
        """递归分解任务（兼容旧版本）"""
        if current_depth >= max_depth:
            task.is_atomic = True
            task.level = TaskLevel.ATOMIC
            return

        if current_depth == 1 and task.level == TaskLevel.LEVEL_1:
            sub_descriptions = [
                f"分析需求：{task.description}",
                f"设计方案：{task.description}",
                f"实现功能：{task.description}",
                f"测试验证：{task.description}"
            ]
            self._add_children(task, sub_descriptions, TaskLevel.LEVEL_2)

        elif current_depth == 2 and task.level == TaskLevel.LEVEL_2:
            if "分析" in task.description:
                self._add_children(task, [
                    "收集需求细节",
                    "识别约束条件",
                    "定义验收标准"
                ], TaskLevel.LEVEL_3)
            elif "设计" in task.description:
                self._add_children(task, [
                    "架构设计",
                    "接口设计",
                    "数据模型设计"
                ], TaskLevel.LEVEL_3)
            elif "实现" in task.description:
                self._add_children(task, [
                    "编写核心代码",
                    "实现辅助功能",
                    "编写文档注释"
                ], TaskLevel.LEVEL_3)
            elif "测试" in task.description:
                self._add_children(task, [
                    "编写单元测试",
                    "编写集成测试",
                    "执行测试验证"
                ], TaskLevel.LEVEL_3)

        elif current_depth == 3 and task.level == TaskLevel.LEVEL_3:
            task.is_atomic = True
            task.level = TaskLevel.ATOMIC

        for child in task.children:
            self._decompose_recursive(child, current_depth + 1, max_depth)

    def _add_children(self, parent: DecomposedTask, descriptions: List[str], level: TaskLevel):
        """添加子任务"""
        for i, desc in enumerate(descriptions):
            child = DecomposedTask(
                task_id=f"{parent.task_id}_{i + 1}",
                description=desc,
                level=level,
                parent_id=parent.task_id
            )
            parent.children.append(child)

    def _task_to_dict(self, task: DecomposedTask) -> Dict[str, Any]:
        """任务转换为字典"""
        return {
            "task_id": task.task_id,
            "description": task.description,
            "level": task.level.value,
            "parent_id": task.parent_id,
            "is_atomic": task.is_atomic,
            "children": [self._task_to_dict(child) for child in task.children]
        }

    def _flatten_tasks(self, task: DecomposedTask) -> List[Dict[str, Any]]:
        """扁平化任务树"""
        result = [self._task_to_dict(task)]
        for child in task.children:
            result.extend(self._flatten_tasks(child))
        return result

    def get_available_strategies(self) -> List[str]:
        """获取可用的拆解策略"""
        return list(self.htd_decomposer.decomposition_strategies.keys())

    def execute(self, task: Any) -> Any:
        """Agent执行入口"""
        if isinstance(task, dict) and "requirement" in task:
            return self.decompose(
                task["requirement"],
                task.get("max_depth", 3),
                task.get("strategy", "standard")
            )
        return {"error": "Invalid task format"}


def demo_decomposition():
    """演示需求拆解 - HTD层级任务拆解"""
    print("=" * 80)
    print("HTD层级任务拆解演示")
    print("=" * 80)
    print()

    agent = RequirementDecompositionAgent()
    agent.start()

    # 演示多种策略
    strategies = agent.get_available_strategies()
    print(f"可用的拆解策略：{strategies}")
    print()

    requirement = "开发一个完整的电商购物车系统"
    print(f"原始需求：{requirement}")
    print()

    # 使用standard策略
    print("--- 使用 standard 策略 ---")
    result_standard = agent.decompose(requirement, max_depth=3, strategy="standard")
    print(f"分解结果：")
    print(f"- 总任务数：{result_standard['summary']['total_tasks']}")
    print(f"- 原子任务数：{result_standard['summary']['atomic_count']}")
    print()

    # 使用waterfall策略
    print("--- 使用 waterfall 策略 ---")
    result_waterfall = agent.decompose(requirement, max_depth=3, strategy="waterfall")
    print(f"分解结果：")
    print(f"- 总任务数：{result_waterfall['summary']['total_tasks']}")
    print(f"- 原子任务数：{result_waterfall['summary']['atomic_count']}")
    print()

    # 展示standard策略的层级结构
    print("--- standard 策略层级结构：")
    tasks = result_standard["all_tasks"]
    for t in tasks:
        indent = "  " * t["level"]
        prefix = "[原子]" if t["is_atomic"] else "[组合]"
        type_str = f"({t['task_type']}"
        print(f"{indent}{prefix} {type_str} {t['entity_id']}: {t['name']}")
        if t["dependencies"]:
            print(f"{indent}  依赖: {t['dependencies']}")

    print()
    print("=" * 80)
    print("✅ HTD演示完成")


if __name__ == "__main__":
    demo_decomposition()
