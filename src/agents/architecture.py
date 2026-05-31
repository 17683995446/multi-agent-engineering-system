"""
架构Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 可分析工程依赖、识别架构缺陷
3. 可锁定模块边界、输出重构方案
4. 仅做架构设计，不参与编码执行
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path
from src.agents.base import BaseAgent
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class DependencyType(Enum):
    """依赖类型"""
    IMPORT = "import"
    CALL = "call"
    INHERITANCE = "inheritance"


class ArchitectureIssueType(Enum):
    """架构问题类型"""
    CIRCULAR_DEPENDENCY = "circular_dependency"
    CYCLE = "cycle"
    OVERCOUPLED = "overcoupled"
    BOUNDARY_VIOLATION = "boundary_violation"
    GOD_MODULE = "god_module"


@dataclass
class Dependency:
    """依赖关系"""
    from_module: str
    to_module: str
    dep_type: DependencyType
    line_number: int = 0


@dataclass
class ArchitectureIssue:
    """架构问题"""
    issue_id: str
    issue_type: ArchitectureIssueType
    description: str
    severity: str  # "high", "medium", "low"
    affected_modules: List[str]
    suggestion: Optional[str] = None


@dataclass
class ModuleBoundary:
    """模块边界"""
    module_name: str
    public_api: List[str]
    internal_components: List[str]
    dependencies: List[str]
    dependents: List[str]


@dataclass
class RefactorSuggestion:
    """重构建议"""
    refactor_id: str
    title: str
    description: str
    affected_modules: List[str]
    steps: List[str]
    expected_benefit: str


class ArchitectureAgent(BaseAgent):
    """架构Agent"""

    def __init__(self):
        super().__init__("ArchitectureAgent")
        self.is_running = False
        self.dependencies: List[Dependency] = []
        self.issues: List[ArchitectureIssue] = []
        self.boundaries: Dict[str, ModuleBoundary] = {}
        self.refactor_suggestions: List[RefactorSuggestion] = []

    def start(self):
        """启动Agent"""
        self.is_running = True
        logger.info(f"架构Agent {self.name} 已启动")

    def stop(self):
        """停止Agent"""
        self.is_running = False
        logger.info(f"架构Agent {self.name} 已停止")

    def analyze_dependencies(self, module_list: List[str]) -> Dict[str, Any]:
        """分析工程依赖"""
        if not self.is_running:
            self.start()

        logger.info("开始分析工程依赖")

        # 模拟依赖分析（复用常见的依赖分析模式）
        self._generate_mock_dependencies(module_list)

        # 识别架构缺陷
        self._identify_architecture_issues()

        result = {
            "dependencies": [
                {
                    "from": d.from_module,
                    "to": d.to_module,
                    "type": d.dep_type.value
                }
                for d in self.dependencies
            ],
            "issues": [
                {
                    "id": i.issue_id,
                    "type": i.issue_type.value,
                    "description": i.description,
                    "severity": i.severity,
                    "modules": i.affected_modules,
                    "suggestion": i.suggestion
                }
                for i in self.issues
            ],
            "summary": {
                "total_dependencies": len(self.dependencies),
                "total_issues": len(self.issues),
                "high_severity": len([i for i in self.issues if i.severity == "high"]),
                "medium_severity": len([i for i in self.issues if i.severity == "medium"]),
                "low_severity": len([i for i in self.issues if i.severity == "low"])
            }
        }

        logger.info(f"依赖分析完成，发现 {result['summary']['total_issues']} 个问题")
        return result

    def lock_module_boundaries(self, module_list: List[str]) -> Dict[str, Any]:
        """锁定模块边界"""
        if not self.is_running:
            self.start()

        logger.info("开始锁定模块边界")

        # 为每个模块生成边界定义
        for module in module_list:
            self.boundaries[module] = ModuleBoundary(
                module_name=module,
                public_api=[
                    f"{module}.main()",
                    f"{module}.get_{module}_data()",
                    f"{module}.validate_{module}()"
                ],
                internal_components=[
                    f"{module}._internal_helper()",
                    f"{module}._cache_data()"
                ],
                dependencies=[],
                dependents=[]
            )

        # 填充依赖关系
        for dep in self.dependencies:
            if dep.from_module in self.boundaries:
                self.boundaries[dep.from_module].dependencies.append(dep.to_module)
            if dep.to_module in self.boundaries:
                self.boundaries[dep.to_module].dependents.append(dep.from_module)

        result = {
            "boundaries": {
                mod: {
                    "public_api": b.public_api,
                    "internal": b.internal_components,
                    "dependencies": b.dependencies,
                    "dependents": b.dependents
                }
                for mod, b in self.boundaries.items()
            },
            "summary": {
                "total_modules": len(module_list),
                "total_public_apis": sum(len(b.public_api) for b in self.boundaries.values())
            }
        }

        logger.info(f"模块边界锁定完成，共 {len(module_list)} 个模块")
        return result

    def generate_refactor_plan(self) -> Dict[str, Any]:
        """输出重构方案"""
        if not self.is_running:
            self.start()

        logger.info("开始生成重构方案")

        # 基于问题生成重构建议
        self._generate_refactor_suggestions()

        result = {
            "refactor_suggestions": [
                {
                    "id": r.refactor_id,
                    "title": r.title,
                    "description": r.description,
                    "modules": r.affected_modules,
                    "steps": r.steps,
                    "benefit": r.expected_benefit
                }
                for r in self.refactor_suggestions
            ],
            "summary": {
                "total_suggestions": len(self.refactor_suggestions),
                "total_modules_affected": len(
                    set(m for r in self.refactor_suggestions for m in r.affected_modules)
                )
            }
        }

        logger.info(f"重构方案生成完成，共 {result['summary']['total_suggestions']} 条建议")
        return result

    def _generate_mock_dependencies(self, module_list: List[str]):
        """生成模拟依赖关系（用于演示）"""
        self.dependencies.clear()

        if len(module_list) >= 3:
            # 生成一些常见的依赖模式
            self.dependencies.append(
                Dependency(module_list[0], module_list[1], DependencyType.IMPORT, 10)
            )
            self.dependencies.append(
                Dependency(module_list[1], module_list[2], DependencyType.CALL, 25)
            )

            # 可选的循环依赖问题
            if len(module_list) >= 4:
                self.dependencies.append(
                    Dependency(module_list[2], module_list[3], DependencyType.IMPORT, 30)
                )
                self.dependencies.append(
                    Dependency(module_list[3], module_list[2], DependencyType.CALL, 45)
                )

    def _identify_architecture_issues(self):
        """识别架构缺陷"""
        self.issues.clear()

        # 检查循环依赖
        visited: Set[str] = set()
        for dep in self.dependencies:
            # 简单的循环检测
            reverse = [
                d for d in self.dependencies
                if d.from_module == dep.to_module and d.to_module == dep.from_module
            ]
            if reverse:
                issue = ArchitectureIssue(
                    issue_id=f"issue_circular_{len(self.issues) + 1}",
                    issue_type=ArchitectureIssueType.CIRCULAR_DEPENDENCY,
                    description=f"模块 {dep.from_module} 和 {dep.to_module} 之间存在循环依赖",
                    severity="high",
                    affected_modules=[dep.from_module, dep.to_module],
                    suggestion="引入中间层或事件总线来解耦"
                )
                self.issues.append(issue)

        # 检查过度耦合
        module_incoming: Dict[str, int] = {}
        for dep in self.dependencies:
            module_incoming[dep.to_module] = module_incoming.get(dep.to_module, 0) + 1

        for mod, count in module_incoming.items():
            if count > 5:
                issue = ArchitectureIssue(
                    issue_id=f"issue_overcoupled_{len(self.issues) + 1}",
                    issue_type=ArchitectureIssueType.OVERCOUPLED,
                    description=f"模块 {mod} 被 {count} 个模块依赖，可能存在过度耦合",
                    severity="medium",
                    affected_modules=[mod],
                    suggestion="考虑拆分为更小的模块或引入抽象接口"
                )
                self.issues.append(issue)

    def _generate_refactor_suggestions(self):
        """生成重构建议"""
        self.refactor_suggestions.clear()

        # 基于问题生成建议
        for i, issue in enumerate(self.issues):
            if issue.issue_type == ArchitectureIssueType.CIRCULAR_DEPENDENCY:
                self.refactor_suggestions.append(
                    RefactorSuggestion(
                        refactor_id=f"refactor_{i + 1}",
                        title=f"解耦 {issue.affected_modules[0]} 和 {issue.affected_modules[1]}",
                        description="消除循环依赖，引入中间抽象层",
                        affected_modules=issue.affected_modules,
                        steps=[
                            "1. 识别公共接口",
                            "2. 创建中间模块",
                            "3. 将相互依赖移动到中间模块",
                            "4. 更新所有引用"
                        ],
                        expected_benefit="提高模块独立性，简化测试和维护"
                    )
                )
            elif issue.issue_type == ArchitectureIssueType.OVERCOUPLED:
                self.refactor_suggestions.append(
                    RefactorSuggestion(
                        refactor_id=f"refactor_{i + 1}",
                        title=f"拆分 {issue.affected_modules[0]} 模块",
                        description="将过度耦合的模块拆分为职责更单一的子模块",
                        affected_modules=issue.affected_modules,
                        steps=[
                            "1. 分析现有功能",
                            "2. 定义新模块边界",
                            "3. 迁移代码",
                            "4. 更新依赖关系"
                        ],
                        expected_benefit="降低耦合度，提高可维护性"
                    )
                )

    def execute(self, task: Any) -> Any:
        """Agent执行入口（仅做架构设计）"""
        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "analyze_dependencies":
                return self.analyze_dependencies(task.get("modules", []))
            elif action == "lock_boundaries":
                return self.lock_module_boundaries(task.get("modules", []))
            elif action == "generate_refactor_plan":
                return self.generate_refactor_plan()

        return {"error": "Invalid task format for ArchitectureAgent"}


def demo_architecture_agent():
    """演示架构Agent"""
    print("=" * 70)
    print("架构Agent演示")
    print("=" * 70)
    print()

    agent = ArchitectureAgent()
    agent.start()

    modules = ["user", "auth", "order", "payment"]
    print(f"目标模块：{modules}")
    print()

    # 1. 分析依赖
    print("步骤1：分析工程依赖")
    result1 = agent.analyze_dependencies(modules)
    print(f"依赖总数：{result1['summary']['total_dependencies']}")
    print(f"问题总数：{result1['summary']['total_issues']}")
    if result1["issues"]:
        print("问题列表：")
        for issue in result1["issues"]:
            print(f"  [{issue['severity']}] {issue['description']}")
    print()

    # 2. 锁定边界
    print("步骤2：锁定模块边界")
    result2 = agent.lock_module_boundaries(modules)
    for mod, boundary in result2["boundaries"].items():
        print(f"  模块 {mod}:")
        print(f"    公共API：{len(boundary['public_api'])} 个")
        print(f"    内部组件：{len(boundary['internal'])} 个")
    print()

    # 3. 重构方案
    print("步骤3：生成重构方案")
    result3 = agent.generate_refactor_plan()
    print(f"重构建议：{result3['summary']['total_suggestions']} 条")
    if result3["refactor_suggestions"]:
        for s in result3["refactor_suggestions"]:
            print(f"  - {s['title']}")
            print(f"    预期收益：{s['benefit']}")
    print()

    print("=" * 70)
    print("✅ 演示完成")


if __name__ == "__main__":
    demo_architecture_agent()
