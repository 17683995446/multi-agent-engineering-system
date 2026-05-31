"""
评审Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 全覆盖校验四级代码原子规范
3. 可检出规范问题、性能风险、安全隐患
4. 评审结果客观、可量化、可整改
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path
import ast
from datetime import datetime
from src.agents.base import BaseAgent
from src.common.utils import setup_logger
from src.code.unified_atom_scanner import UnifiedAtomScanner

logger = setup_logger(__name__)


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    """问题类别"""
    ATOMIC_COMPLIANCE = "atomic_compliance"
    PERFORMANCE_RISK = "performance_risk"
    SECURITY_VULNERABILITY = "security_vulnerability"
    CODE_STYLE = "code_style"
    BEST_PRACTICE = "best_practice"


class AtomicLevel(Enum):
    """原子级别"""
    VARIABLE = "variable"
    METHOD = "method"
    CLASS = "class"
    MODULE = "module"


@dataclass
class ReviewIssue:
    """评审问题"""
    issue_id: str
    file: str
    line: int
    level: AtomicLevel
    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    suggestion: str
    confidence: float  # 0.0 - 1.0


@dataclass
class LevelScore:
    """某级别的分数"""
    level: AtomicLevel
    total_issues: int
    critical_issues: int
    score: float  # 0.0 - 1.0
    passed: bool


@dataclass
class ReviewResult:
    """评审结果"""
    review_id: str
    files_checked: int
    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    level_scores: List[LevelScore]
    issues: List[ReviewIssue]
    overall_score: float  # 0.0 - 100.0
    passed: bool
    summary: str
    actionable_fixes: List[Dict[str, Any]]
    timestamp: str


class CodeReviewAgent(BaseAgent):
    """代码评审Agent"""

    def __init__(self):
        super().__init__("CodeReviewAgent")
        self.is_running = False
        self.review_history: List[ReviewResult] = []
        self.scanner = UnifiedAtomScanner()

    def start(self):
        """启动Agent"""
        self.is_running = True
        logger.info(f"代码评审Agent {self.name} 已启动")

    def stop(self):
        """停止Agent"""
        self.is_running = False
        logger.info(f"代码评审Agent {self.name} 已停止")

    def review_file(self, file_path: str) -> ReviewResult:
        """评审单个文件"""
        if not self.is_running:
            self.start()

        review_id = f"review_{len(self.review_history) + 1}"
        logger.info(f"开始评审文件：{file_path}")

        issues: List[ReviewIssue] = []

        # 1. 检查变量级原子规范
        var_issues = self._check_variable_atomic(file_path)
        issues.extend(var_issues)

        # 2. 检查方法级原子规范
        method_issues = self._check_method_atomic(file_path)
        issues.extend(method_issues)

        # 3. 检查类级原子规范
        class_issues = self._check_class_atomic(file_path)
        issues.extend(class_issues)

        # 4. 检查模块级原子规范
        module_issues = self._check_module_atomic(file_path)
        issues.extend(module_issues)

        # 5. 检查性能风险
        perf_issues = self._check_performance_risks(file_path)
        issues.extend(perf_issues)

        # 6. 检查安全隐患
        security_issues = self._check_security_vulnerabilities(file_path)
        issues.extend(security_issues)

        # 生成评审结果
        result = self._aggregate_results(review_id, [file_path], issues)
        self.review_history.append(result)
        logger.info(f"评审完成：{review_id}，得分：{result.overall_score}")
        return result

    def review_directory(self, directory: str) -> ReviewResult:
        """评审整个目录"""
        if not self.is_running:
            self.start()

        review_id = f"review_{len(self.review_history) + 1}"
        logger.info(f"开始评审目录：{directory}")

        all_issues: List[ReviewIssue] = []
        files_checked = 0

        for file_path in Path(directory).rglob("*.py"):
            if file_path.name.startswith("_"):
                continue
            all_issues.extend(self._review_single_file(str(file_path)))
            files_checked += 1

        result = self._aggregate_results(review_id, [directory], all_issues)
        result.files_checked = files_checked
        self.review_history.append(result)
        logger.info(f"目录评审完成：{review_id}，检查 {files_checked} 个文件")
        return result

    def _review_single_file(self, file_path: str) -> List[ReviewIssue]:
        """内部：评审单个文件"""
        issues: List[ReviewIssue] = []
        issues.extend(self._check_variable_atomic(file_path))
        issues.extend(self._check_method_atomic(file_path))
        issues.extend(self._check_class_atomic(file_path))
        issues.extend(self._check_module_atomic(file_path))
        issues.extend(self._check_performance_risks(file_path))
        issues.extend(self._check_security_vulnerabilities(file_path))
        return issues

    def _check_variable_atomic(self, file_path: str) -> List[ReviewIssue]:
        """检查变量级原子规范"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'temp' in line and '=' in line:
                    issues.append(ReviewIssue(
                        issue_id=f"var_{len(issues)+1}",
                        file=file_path,
                        line=i+1,
                        level=AtomicLevel.VARIABLE,
                        category=IssueCategory.ATOMIC_COMPLIANCE,
                        severity=IssueSeverity.LOW,
                        title="模糊变量名",
                        description="使用了模糊变量名'temp'",
                        suggestion="建议使用更有语义的变量名",
                        confidence=0.8
                    ))
        except Exception as e:
            logger.warning(f"检查变量规范失败：{e}")
        return issues

    def _check_method_atomic(self, file_path: str) -> List[ReviewIssue]:
        """检查方法级原子规范"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 检查方法长度
                    if hasattr(node, 'body') and len(node.body) > 20:
                        issues.append(ReviewIssue(
                            issue_id=f"meth_{len(issues)+1}",
                            file=file_path,
                            line=node.lineno,
                            level=AtomicLevel.METHOD,
                            category=IssueCategory.ATOMIC_COMPLIANCE,
                            severity=IssueSeverity.MEDIUM,
                            title="方法过长",
                            description=f"方法{node.name}长度超过20行",
                            suggestion="建议拆分为更小的方法",
                            confidence=0.9
                        ))
                    # 检查参数数量
                    if hasattr(node, 'args') and len(node.args.args) > 5:
                        issues.append(ReviewIssue(
                            issue_id=f"meth_{len(issues)+1}",
                            file=file_path,
                            line=node.lineno,
                            level=AtomicLevel.METHOD,
                            category=IssueCategory.ATOMIC_COMPLIANCE,
                            severity=IssueSeverity.HIGH,
                            title="方法参数过多",
                            description=f"方法{node.name}有{len(node.args.args)}个参数",
                            suggestion="建议使用字典或数据类传递参数",
                            confidence=0.95
                        ))
        except Exception as e:
            logger.warning(f"检查方法规范失败：{e}")
        return issues

    def _check_class_atomic(self, file_path: str) -> List[ReviewIssue]:
        """检查类级原子规范"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 检查类方法数量
                    method_count = sum(1 for n in node.body if isinstance(n, ast.FunctionDef))
                    if method_count > 10:
                        issues.append(ReviewIssue(
                            issue_id=f"cls_{len(issues)+1}",
                            file=file_path,
                            line=node.lineno,
                            level=AtomicLevel.CLASS,
                            category=IssueCategory.ATOMIC_COMPLIANCE,
                            severity=IssueSeverity.MEDIUM,
                            title="类方法过多",
                            description=f"类{node.name}有{method_count}个方法",
                            suggestion="建议拆分为更小的类",
                            confidence=0.85
                        ))
        except Exception as e:
            logger.warning(f"检查类规范失败：{e}")
        return issues

    def _check_module_atomic(self, file_path: str) -> List[ReviewIssue]:
        """检查模块级原子规范"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            # 检查模块长度
            if len(content) > 2000:
                issues.append(ReviewIssue(
                    issue_id=f"mod_{len(issues)+1}",
                    file=file_path,
                    line=1,
                    level=AtomicLevel.MODULE,
                    category=IssueCategory.ATOMIC_COMPLIANCE,
                    severity=IssueSeverity.HIGH,
                    title="模块文件过大",
                    description="模块文件超过2000字符",
                    suggestion="建议拆分为多个模块",
                    confidence=0.9
                ))
        except Exception as e:
            logger.warning(f"检查模块规范失败：{e}")
        return issues

    def _check_performance_risks(self, file_path: str) -> List[ReviewIssue]:
        """检查性能风险"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            # 检查嵌套循环
            if 'for' in content and 'for' in content.split('for')[1]:
                issues.append(ReviewIssue(
                    issue_id=f"perf_{len(issues)+1}",
                    file=file_path,
                    line=1,
                    level=AtomicLevel.METHOD,
                    category=IssueCategory.PERFORMANCE_RISK,
                    severity=IssueSeverity.HIGH,
                    title="嵌套循环",
                    description="检测到嵌套循环，可能存在性能问题",
                    suggestion="考虑优化算法复杂度",
                    confidence=0.75
                ))
        except Exception as e:
            logger.warning(f"检查性能风险失败：{e}")
        return issues

    def _check_security_vulnerabilities(self, file_path: str) -> List[ReviewIssue]:
        """检查安全隐患"""
        issues = []
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            # 简单的安全检查
            if 'eval(' in content:
                issues.append(ReviewIssue(
                    issue_id=f"sec_{len(issues)+1}",
                    file=file_path,
                    line=content.split('eval(')[0].count('\n') + 1,
                    level=AtomicLevel.METHOD,
                    category=IssueCategory.SECURITY_VULNERABILITY,
                    severity=IssueSeverity.CRITICAL,
                    title="使用eval",
                    description="使用eval可能存在安全风险",
                    suggestion="建议使用更安全的替代方案",
                    confidence=0.95
                ))
            if 'os.system' in content:
                issues.append(ReviewIssue(
                    issue_id=f"sec_{len(issues)+1}",
                    file=file_path,
                    line=content.split('os.system')[0].count('\n') + 1,
                    level=AtomicLevel.METHOD,
                    category=IssueCategory.SECURITY_VULNERABILITY,
                    severity=IssueSeverity.CRITICAL,
                    title="使用os.system",
                    description="使用os.system可能存在安全风险",
                    suggestion="建议使用subprocess.run并设置shell=False",
                    confidence=0.95
                ))
        except Exception as e:
            logger.warning(f"检查安全隐患失败：{e}")
        return issues

    def _aggregate_results(self, review_id: str, paths: List[str], issues: List[ReviewIssue]) -> ReviewResult:
        """聚合评审结果"""
        critical = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)
        medium = sum(1 for i in issues if i.severity == IssueSeverity.MEDIUM)
        low = sum(1 for i in issues if i.severity == IssueSeverity.LOW)

        # 计算各级别分数
        level_scores = []
        for level in AtomicLevel:
            level_issues = [i for i in issues if i.level == level]
            total_level = len(level_issues)
            critical_level = sum(1 for i in level_issues if i.severity == IssueSeverity.CRITICAL)
            high_level = sum(1 for i in level_issues if i.severity == IssueSeverity.HIGH)
            score = max(0.0, 1.0 - (critical_level * 0.2 + high_level * 0.1 + total_level * 0.05))
            passed = score >= 0.6
            level_scores.append(LevelScore(
                level=level,
                total_issues=total_level,
                critical_issues=critical_level,
                score=score,
                passed=passed
            ))

        # 计算总分
        overall_score = 100.0 - (critical * 10 + high * 5 + medium * 2 + low * 1)
        overall_score = max(0.0, min(100.0, overall_score))
        overall_passed = overall_score >= 60.0 and critical == 0

        # 生成可整改建议
        actionable_fixes = []
        for issue in issues:
            actionable_fixes.append({
                "priority": issue.severity.value,
                "issue_id": issue.issue_id,
                "title": issue.title,
                "description": issue.description,
                "file": issue.file,
                "line": issue.line,
                "suggestion": issue.suggestion
            })
        actionable_fixes.sort(key=lambda x: ["critical", "high", "medium", "low", "info"].index(x["priority"]))

        return ReviewResult(
            review_id=review_id,
            files_checked=len(paths),
            total_issues=len(issues),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            level_scores=level_scores,
            issues=issues,
            overall_score=overall_score,
            passed=overall_passed,
            summary=f"评审完成，发现{len(issues)}个问题，{critical}个严重，{high}个高危",
            actionable_fixes=actionable_fixes[:10],  # 前10个优先问题
            timestamp=datetime.now().isoformat()
        )

    def execute(self, task: Any) -> Any:
        """Agent执行入口"""
        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "review_file":
                result = self.review_file(task["file_path"])
                return {
                    "review_id": result.review_id,
                    "score": result.overall_score,
                    "passed": result.passed,
                    "total_issues": result.total_issues,
                    "critical": result.critical_count
                }
            elif action == "review_dir":
                result = self.review_directory(task["directory"])
                return {
                    "review_id": result.review_id,
                    "score": result.overall_score,
                    "passed": result.passed,
                    "total_issues": result.total_issues,
                    "files_checked": result.files_checked
                }
        return {"error": "Invalid task format"}


def demo_code_review():
    """演示代码评审"""
    print("=" * 70)
    print("代码评审Agent演示")
    print("=" * 70)
    print()

    agent = CodeReviewAgent()
    agent.start()

    import tempfile
    import os

    test_file = os.path.join(tempfile.mkdtemp(), "test_review.py")
    with open(test_file, "w") as f:
        f.write("""temp = 42
data = {'key': 'value'}

def process_input(a, b, c, d, e, f):
    if a > b:
        return a + c
    return d + e + f

for i in range(10):
    for j in range(10):
        print(i, j)

def run_cmd():
    import os
    os.system('rm -rf /tmp')
""")

    print(f"评审文件：{test_file}")
    print()

    result = agent.review_file(test_file)

    print("评审结果：")
    print(f"  评审ID：{result.review_id}")
    print(f"  总得分：{result.overall_score:.1f}")
    print(f"  是否通过：{'✅' if result.passed else '❌'}")
    print(f"  问题总数：{result.total_issues}")
    print(f"  严重问题：{result.critical_count}")
    print(f"  高危问题：{result.high_count}")
    print(f"  中危问题：{result.medium_count}")
    print(f"  低危问题：{result.low_count}")
    print()

    print("各级别得分：")
    for ls in result.level_scores:
        print(f"  {ls.level.value:10} - {ls.score*100:.0f}分 - {'✅' if ls.passed else '❌'} - {ls.total_issues}个问题")
    print()

    print("主要问题（前5）：")
    for i, fix in enumerate(result.actionable_fixes[:5], 1):
        print(f"  {i}. [{fix['priority']}] {fix['title']}")
        print(f"     {fix['file']}:{fix['line']}")
        print(f"     {fix['suggestion']}")
        if i < len(result.actionable_fixes[:5]):
            print()

    print()
    print("=" * 70)
    print("✅ 演示完成")


if __name__ == "__main__":
    demo_code_review()
