"""
MVP阶段3: 代码原子扫描器
遵循第一性原理：四级原子化检查

核心功能：
1. 变量原子扫描 - 命名规范、语义清晰性
2. 方法原子扫描 - 四段式结构、单一职责、行数限制
3. 类原子扫描 - 单一职责、三区分离
4. 模块原子扫描 - 模块粒度、接口清晰度

使用Python AST模块进行静态分析。
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from src.common.utils import setup_logger

logger = setup_logger(__name__)


# ==================== 公共枚举与数据类 ====================

class IssueSeverity(Enum):
    """问题严重级别"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AtomIssue:
    """原子化问题"""
    issue_type: str
    message: str
    line: int
    column: int
    severity: IssueSeverity = IssueSeverity.WARNING
    suggestion: Optional[str] = None


@dataclass
class AtomScanResult:
    """原子扫描结果"""
    target_name: str
    target_type: str
    issues: List[AtomIssue] = field(default_factory=list)
    passed: bool = True
    metrics: Dict[str, Any] = field(default_factory=dict)


# ==================== 1. 变量原子扫描器 ====================

class VariableCategory(Enum):
    """变量类别"""
    CONSTANT = "constant"
    STATE = "state"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


@dataclass
class VariableInfo:
    """变量信息"""
    name: str
    category: VariableCategory
    line: int
    column: int
    is_assigned: bool
    issues: List[AtomIssue] = field(default_factory=list)


class VariableAtomScanner(ast.NodeVisitor):
    """变量原子扫描器

    检查项：
    - snake_case命名规范
    - 语义清晰性（避免模糊命名）
    - 常量全大写规范
    """

    # 模糊命名黑名单
    VAGUE_NAMES = {
        "temp", "tmp", "data", "info", "val", "value",
        "result", "res", "x", "y", "z", "i", "j", "k",
        "a", "b", "c", "obj", "object", "item",
        "things", "stuff", "foo", "bar", "baz",
    }

    # 常量模式：全大写下划线
    CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

    # 状态变量前缀
    STATE_PREFIXES = ("is_", "has_", "can_", "should_", "needs_", "will_")
    STATE_SUFFIXES = ("_state", "_status", "_flag")

    def __init__(self):
        self.variables: List[VariableInfo] = []
        self.assigned_names: Set[str] = set()
        self._current_function_vars: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._current_function_vars = set()
        for arg in node.args.args:
            self._add_variable(arg.arg, node.lineno, node.col_offset, is_assigned=True)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add_variable(target.id, node.lineno, node.col_offset, is_assigned=True)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._add_variable(node.target.id, node.lineno, node.col_offset, is_assigned=True)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            self._add_variable(node.target.id, node.lineno, node.col_offset, is_assigned=True)
        self.generic_visit(node)

    def _add_variable(self, name: str, line: int, col: int, is_assigned: bool) -> None:
        if name.startswith("__") and name.endswith("__"):
            return
        if name == "self":
            return

        category = self._classify_variable(name)
        issues = self._check_variable_issues(name, category, line, col)

        var_info = VariableInfo(
            name=name,
            category=category,
            line=line,
            column=col,
            is_assigned=is_assigned,
            issues=issues,
        )
        self.variables.append(var_info)
        if is_assigned:
            self.assigned_names.add(name)

    def _classify_variable(self, name: str) -> VariableCategory:
        if self.CONSTANT_PATTERN.match(name):
            return VariableCategory.CONSTANT
        if name.startswith("_") or "temp" in name.lower() or "tmp" in name.lower():
            return VariableCategory.TEMPORARY
        if name.startswith(self.STATE_PREFIXES) or name.endswith(self.STATE_SUFFIXES):
            return VariableCategory.STATE
        return VariableCategory.UNKNOWN

    def _check_variable_issues(self, name: str, category: VariableCategory, line: int, col: int) -> List[AtomIssue]:
        issues: List[AtomIssue] = []

        # 1. snake_case 检查（常量除外）
        if category != VariableCategory.CONSTANT:
            if not re.match(r"^[a-z][a-z0-9_]*$", name):
                issues.append(AtomIssue(
                    issue_type="naming_violation",
                    message=f"变量 '{name}' 不符合 snake_case 命名规范",
                    line=line,
                    column=col,
                    severity=IssueSeverity.ERROR,
                    suggestion=f"建议改为 '{self._to_snake_case(name)}'",
                ))

        # 2. 语义清晰性检查
        base_name = name.lstrip("_").lower()
        if base_name in self.VAGUE_NAMES:
            issues.append(AtomIssue(
                issue_type="vague_naming",
                message=f"变量 '{name}' 命名过于模糊，缺乏语义",
                line=line,
                column=col,
                severity=IssueSeverity.WARNING,
                suggestion="建议使用能表达具体含义的名称",
            ))

        # 3. 常量命名规范
        if category == VariableCategory.CONSTANT and not self.CONSTANT_PATTERN.match(name):
            issues.append(AtomIssue(
                issue_type="constant_naming",
                message=f"常量 '{name}' 应使用全大写下划线命名",
                line=line,
                column=col,
                severity=IssueSeverity.ERROR,
                suggestion=name.upper().replace("-", "_"),
            ))

        return issues

    @staticmethod
    def _to_snake_case(name: str) -> str:
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def scan(self, source: str) -> AtomScanResult:
        self.variables = []
        self.assigned_names = set()
        try:
            tree = ast.parse(source)
            self.visit(tree)
        except SyntaxError as e:
            logger.error(f"语法解析失败: {e}")
            return AtomScanResult(
                target_name="<module>",
                target_type="variable_scan",
                issues=[AtomIssue("syntax_error", str(e), getattr(e, "lineno", 0), 0, IssueSeverity.ERROR)],
                passed=False,
            )

        all_issues = []
        for var in self.variables:
            all_issues.extend(var.issues)

        return AtomScanResult(
            target_name="<module>",
            target_type="variable_scan",
            issues=all_issues,
            passed=not any(i.severity == IssueSeverity.ERROR for i in all_issues),
            metrics={
                "total_variables": len(self.variables),
                "constant_count": sum(1 for v in self.variables if v.category == VariableCategory.CONSTANT),
                "state_count": sum(1 for v in self.variables if v.category == VariableCategory.STATE),
                "issue_count": len(all_issues),
            },
        )


# ==================== 2. 方法原子扫描器 ====================

@dataclass
class MethodInfo:
    """方法信息"""
    name: str
    line: int
    column: int
    lines_count: int
    params_count: int
    has_docstring: bool
    has_four_sections: bool
    section_issues: List[str] = field(default_factory=list)
    issues: List[AtomIssue] = field(default_factory=list)


class MethodAtomScanner(ast.NodeVisitor):
    """方法原子扫描器

    检查项：
    - 四段式结构（参数校验、业务逻辑、结果组装、返回）
    - 单一职责（复杂度控制）
    - 行数限制 <= 30
    - 参数数量 <= 5
    - 命名规范（动词开头，snake_case）
    """

    MAX_METHOD_LINES = 30
    MAX_PARAMS = 5
    MAX_COMPLEXITY = 10

    # 四段式标记
    SECTION_VALIDATION = "validation"
    SECTION_LOGIC = "logic"
    SECTION_ASSEMBLY = "assembly"
    SECTION_RETURN = "return"

    def __init__(self):
        self.methods: List[MethodInfo] = []
        self.source_lines: List[str] = []

    def scan(self, source: str) -> AtomScanResult:
        self.methods = []
        self.source_lines = source.split("\n")
        try:
            tree = ast.parse(source)
            self.visit(tree)
        except SyntaxError as e:
            return AtomScanResult(
                target_name="<module>",
                target_type="method_scan",
                issues=[AtomIssue("syntax_error", str(e), getattr(e, "lineno", 0), 0, IssueSeverity.ERROR)],
                passed=False,
            )

        all_issues: List[AtomIssue] = []
        for method in self.methods:
            all_issues.extend(method.issues)

        return AtomScanResult(
            target_name="<module>",
            target_type="method_scan",
            issues=all_issues,
            passed=not any(i.severity == IssueSeverity.ERROR for i in all_issues),
            metrics={
                "total_methods": len(self.methods),
                "issue_methods": sum(1 for m in self.methods if m.issues),
                "avg_lines": sum(m.lines_count for m in self.methods) / max(len(self.methods), 1),
            },
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        method_info = self._analyze_method(node)
        self.methods.append(method_info)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        method_info = self._analyze_method(node)
        self.methods.append(method_info)
        self.generic_visit(node)

    def _analyze_method(self, node: ast.FunctionDef) -> MethodInfo:
        start_line = node.lineno
        end_line = self._find_end_line(node)
        lines_count = end_line - start_line + 1 if end_line else 1

        params_count = len(node.args.args) + len(node.args.kwonlyargs)
        if node.args.vararg:
            params_count += 1
        if node.args.kwarg:
            params_count += 1

        has_docstring = ast.get_docstring(node) is not None

        sections = self._detect_four_sections(node)
        has_four_sections = all(sections.values())
        section_issues = []
        if not sections[self.SECTION_VALIDATION]:
            section_issues.append("缺少参数校验段")
        if not sections[self.SECTION_LOGIC]:
            section_issues.append("缺少业务逻辑段")
        if not sections[self.SECTION_RETURN]:
            section_issues.append("缺少返回段")

        issues: List[AtomIssue] = []

        # 行数限制
        if lines_count > self.MAX_METHOD_LINES:
            issues.append(AtomIssue(
                issue_type="too_long",
                message=f"方法 '{node.name}' 过长 ({lines_count} 行)，建议不超过 {self.MAX_METHOD_LINES} 行",
                line=start_line,
                column=node.col_offset,
                severity=IssueSeverity.ERROR,
                suggestion="将方法拆分为多个单一职责的小方法",
            ))

        # 参数数量
        if params_count > self.MAX_PARAMS:
            issues.append(AtomIssue(
                issue_type="too_many_params",
                message=f"方法 '{node.name}' 参数过多 ({params_count} 个)，建议不超过 {self.MAX_PARAMS} 个",
                line=start_line,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="考虑使用数据类或字典封装参数",
            ))

        # 复杂度
        complexity = self._calculate_complexity(node)
        if complexity > self.MAX_COMPLEXITY:
            issues.append(AtomIssue(
                issue_type="too_complex",
                message=f"方法 '{node.name}' 复杂度过高 (复杂度 {complexity})，可能承担多个职责",
                line=start_line,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="按照单一职责原则拆分方法",
            ))

        # 命名规范
        if not self._is_good_method_name(node.name):
            issues.append(AtomIssue(
                issue_type="poor_naming",
                message=f"方法 '{node.name}' 命名不规范，应以动词开头并使用 snake_case",
                line=start_line,
                column=node.col_offset,
                severity=IssueSeverity.ERROR,
                suggestion=f"建议改为如 'do_{node.name}' 或更具体的动词开头名称",
            ))

        # 四段式
        if section_issues:
            issues.append(AtomIssue(
                issue_type="missing_four_sections",
                message=f"方法 '{node.name}' 四段式结构不完整: {', '.join(section_issues)}",
                line=start_line,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="建议按 参数校验 -> 业务逻辑 -> 结果组装 -> 返回 组织代码",
            ))

        return MethodInfo(
            name=node.name,
            line=start_line,
            column=node.col_offset,
            lines_count=lines_count,
            params_count=params_count,
            has_docstring=has_docstring,
            has_four_sections=has_four_sections,
            section_issues=section_issues,
            issues=issues,
        )

    def _find_end_line(self, node: ast.AST) -> int:
        end_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, "end_lineno") and child.end_lineno:
                end_line = max(end_line, child.end_lineno)
            elif hasattr(child, "lineno"):
                end_line = max(end_line, child.lineno)
        return end_line

    def _detect_four_sections(self, node: ast.FunctionDef) -> Dict[str, bool]:
        sections = {
            self.SECTION_VALIDATION: False,
            self.SECTION_LOGIC: False,
            self.SECTION_ASSEMBLY: False,
            self.SECTION_RETURN: False,
        }

        body = node.body
        # 跳过 docstring
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]

        for stmt in body:
            # 校验段：Raise / Assert / 条件判断带 Raise
            if isinstance(stmt, (ast.Raise, ast.Assert)):
                sections[self.SECTION_VALIDATION] = True
            elif isinstance(stmt, ast.If):
                for child in ast.walk(stmt):
                    if isinstance(child, ast.Raise):
                        sections[self.SECTION_VALIDATION] = True
                        break

            # 返回段
            if isinstance(stmt, ast.Return):
                sections[self.SECTION_RETURN] = True

            # 业务逻辑段：赋值、调用、循环等
            if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For, ast.While, ast.If, ast.With, ast.Try)):
                sections[self.SECTION_LOGIC] = True

            # 结果组装段：赋值后紧跟返回
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                sections[self.SECTION_ASSEMBLY] = True

        # 如果没有显式return，但函数体有内容，视为有返回段（隐式return None）
        if not sections[self.SECTION_RETURN] and body:
            # 对于无返回的简单函数，降低要求
            pass

        return sections

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        complexity = 1

        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 1

            def visit_If(self, n):
                self.complexity += 1
                self.generic_visit(n)

            def visit_For(self, n):
                self.complexity += 1
                self.generic_visit(n)

            def visit_While(self, n):
                self.complexity += 1
                self.generic_visit(n)

            def visit_ExceptHandler(self, n):
                self.complexity += 1
                self.generic_visit(n)

            def visit_With(self, n):
                self.complexity += 1
                self.generic_visit(n)

        visitor = ComplexityVisitor()
        visitor.visit(node)
        return visitor.complexity

    def _is_good_method_name(self, name: str) -> bool:
        if name.startswith("__") and name.endswith("__"):
            return True
        verbs = (
            "get", "set", "update", "delete", "create", "save", "load",
            "process", "handle", "validate", "check", "find", "search",
            "calculate", "compute", "format", "parse", "convert", "transform",
            "build", "run", "execute", "perform", "apply", "resolve",
            "fetch", "send", "receive", "read", "write", "init", "setup",
            "generate", "render", "compose", "decompose", "analyze",
        )
        if any(name.lower().startswith(v) for v in verbs):
            return True
        return bool(re.match(r"^[a-z][a-z0-9_]*$", name))


# ==================== 3. 类原子扫描器 ====================

class ClassZone(Enum):
    """类区域类型"""
    CONSTANT = "constant"
    STATE = "state"
    METHOD = "method"
    UNKNOWN = "unknown"


@dataclass
class ClassStructure:
    """类结构信息"""
    name: str
    line: int
    constants: List[Tuple[str, int]] = field(default_factory=list)
    states: List[Tuple[str, int]] = field(default_factory=list)
    methods: List[Tuple[str, int]] = field(default_factory=list)
    issues: List[AtomIssue] = field(default_factory=list)
    zone_order_correct: bool = True
    single_responsibility_score: float = 1.0


class ClassAtomScanner(ast.NodeVisitor):
    """类原子扫描器

    检查项：
    - 单一职责（方法数、职责关键词分散度）
    - 三区分离（常量区、状态区、方法区）
    - 命名规范（大驼峰）
    """

    MAX_METHODS = 15
    MAX_STATES = 10

    def __init__(self):
        self.classes: List[ClassStructure] = []

    def scan(self, source: str) -> AtomScanResult:
        self.classes = []
        try:
            tree = ast.parse(source)
            self.visit(tree)
        except SyntaxError as e:
            return AtomScanResult(
                target_name="<module>",
                target_type="class_scan",
                issues=[AtomIssue("syntax_error", str(e), getattr(e, "lineno", 0), 0, IssueSeverity.ERROR)],
                passed=False,
            )

        all_issues: List[AtomIssue] = []
        for cls in self.classes:
            all_issues.extend(cls.issues)

        return AtomScanResult(
            target_name="<module>",
            target_type="class_scan",
            issues=all_issues,
            passed=not any(i.severity == IssueSeverity.ERROR for i in all_issues),
            metrics={
                "total_classes": len(self.classes),
                "issue_classes": sum(1 for c in self.classes if c.issues),
            },
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        structure = self._analyze_class(node)
        self.classes.append(structure)
        self.generic_visit(node)

    def _analyze_class(self, node: ast.ClassDef) -> ClassStructure:
        structure = ClassStructure(name=node.name, line=node.lineno)
        items: List[Tuple[str, ClassZone, int]] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append((item.name, ClassZone.METHOD, item.lineno))
            elif isinstance(item, ast.Assign):
                zone = self._classify_assignment(item)
                name = item.targets[0].id if hasattr(item.targets[0], "id") else str(item.targets[0])
                items.append((name, zone, item.lineno))
            elif isinstance(item, ast.AnnAssign):
                zone = self._classify_annotated_assignment(item)
                name = item.target.id if hasattr(item.target, "id") else str(item.target)
                items.append((name, zone, item.lineno))

        items.sort(key=lambda x: x[2])

        for name, zone, line in items:
            if zone == ClassZone.CONSTANT:
                structure.constants.append((name, line))
            elif zone == ClassZone.STATE:
                structure.states.append((name, line))
            elif zone == ClassZone.METHOD:
                structure.methods.append((name, line))

        structure.zone_order_correct = self._check_zone_order(items)
        structure.issues = self._check_class_issues(node, structure)
        structure.single_responsibility_score = self._calculate_single_responsibility(node)

        return structure

    def _classify_assignment(self, node: ast.Assign) -> ClassZone:
        if not node.targets:
            return ClassZone.UNKNOWN
        target = node.targets[0]
        if hasattr(target, "id"):
            name = target.id
            if name.isupper() or (name.startswith("_") and name.lstrip("_").isupper()):
                return ClassZone.CONSTANT
            return ClassZone.STATE
        return ClassZone.UNKNOWN

    def _classify_annotated_assignment(self, node: ast.AnnAssign) -> ClassZone:
        if hasattr(node.target, "id"):
            name = node.target.id
            if name.isupper() or (name.startswith("_") and name.lstrip("_").isupper()):
                return ClassZone.CONSTANT
        return ClassZone.STATE

    def _check_zone_order(self, items: List[Tuple[str, ClassZone, int]]) -> bool:
        expected_order = [ClassZone.CONSTANT, ClassZone.STATE, ClassZone.METHOD]
        current_index = -1
        for _, zone, _ in items:
            if zone == ClassZone.UNKNOWN:
                continue
            try:
                idx = expected_order.index(zone)
            except ValueError:
                continue
            if idx < current_index:
                return False
            current_index = idx
        return True

    def _check_class_issues(self, node: ast.ClassDef, structure: ClassStructure) -> List[AtomIssue]:
        issues: List[AtomIssue] = []

        # 命名规范：大驼峰
        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
            issues.append(AtomIssue(
                issue_type="class_naming",
                message=f"类 '{node.name}' 命名不符合大驼峰规范",
                line=node.lineno,
                column=node.col_offset,
                severity=IssueSeverity.ERROR,
                suggestion="类名应使用大驼峰命名法，如 MyClass",
            ))

        # 单一职责：方法数检查
        if len(structure.methods) > self.MAX_METHODS:
            issues.append(AtomIssue(
                issue_type="too_many_methods",
                message=f"类 '{node.name}' 方法过多 ({len(structure.methods)} 个)，可能违反单一职责",
                line=node.lineno,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="考虑拆分为多个职责单一的类",
            ))

        # 单一职责：状态数检查
        if len(structure.states) > self.MAX_STATES:
            issues.append(AtomIssue(
                issue_type="too_many_states",
                message=f"类 '{node.name}' 状态变量过多 ({len(structure.states)} 个)，可能违反单一职责",
                line=node.lineno,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="考虑提取部分状态到专门的类中",
            ))

        # 三区分离检查
        if not structure.zone_order_correct:
            issues.append(AtomIssue(
                issue_type="zone_order",
                message=f"类 '{node.name}' 区域顺序不正确，应为：常量区 -> 状态区 -> 方法区",
                line=node.lineno,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="重新排列类成员顺序",
            ))

        # 职责分散度
        if structure.single_responsibility_score < 0.5:
            issues.append(AtomIssue(
                issue_type="low_cohesion",
                message=f"类 '{node.name}' 内聚度较低 (得分 {structure.single_responsibility_score:.2f})，可能承担多个职责",
                line=node.lineno,
                column=node.col_offset,
                severity=IssueSeverity.WARNING,
                suggestion="将不同职责的方法提取到独立的类中",
            ))

        return issues

    def _calculate_single_responsibility(self, node: ast.ClassDef) -> float:
        """通过方法命名前缀的集中度估算单一职责程度"""
        methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) <= 1:
            return 1.0

        prefixes: Dict[str, int] = defaultdict(int)
        for method in methods:
            name = method.name.lstrip("_")
            # 提取前缀（前3-5个字符或第一个下划线前的部分）
            prefix = re.split(r"[_\d]", name)[0] if name else ""
            if prefix:
                prefixes[prefix] += 1

        if not prefixes:
            return 1.0

        max_count = max(prefixes.values())
        return max_count / len(methods)


# ==================== 4. 模块原子扫描器 ====================

@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    lines_count: int
    class_count: int
    function_count: int
    public_api: List[str] = field(default_factory=list)
    private_api: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class ModuleAtomScanner:
    """模块原子扫描器

    检查项：
    - 模块粒度（行数、类数、函数数）
    - 接口清晰度（__all__定义、公共API数量）
    - 三区分离（导入区、定义区、执行区）
    """

    MAX_LINES = 500
    MAX_CLASSES = 10
    MAX_FUNCTIONS = 30
    MAX_PUBLIC_API = 20

    def scan(self, source: str, module_name: str = "<module>") -> AtomScanResult:
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return AtomScanResult(
                target_name=module_name,
                target_type="module_scan",
                issues=[AtomIssue("syntax_error", str(e), getattr(e, "lineno", 0), 0, IssueSeverity.ERROR)],
                passed=False,
            )

        lines = source.split("\n")
        module_info = self._parse_module(tree, lines)
        issues = self._check_module_issues(module_info, tree, lines)

        return AtomScanResult(
            target_name=module_name,
            target_type="module_scan",
            issues=issues,
            passed=not any(i.severity == IssueSeverity.ERROR for i in issues),
            metrics={
                "lines_count": module_info.lines_count,
                "class_count": module_info.class_count,
                "function_count": module_info.function_count,
                "public_api_count": len(module_info.public_api),
                "private_api_count": len(module_info.private_api),
            },
        )

    def _parse_module(self, tree: ast.AST, lines: List[str]) -> ModuleInfo:
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        top_level_functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        public_api = self._get_public_api(tree)
        private_api = self._get_private_api(tree)
        imports = self._get_imports(tree)

        return ModuleInfo(
            name="<module>",
            lines_count=len(lines),
            class_count=len(classes),
            function_count=len(top_level_functions),
            public_api=public_api,
            private_api=private_api,
            imports=imports,
        )

    def _get_public_api(self, tree: ast.AST) -> List[str]:
        public_api = []
        # 检查 __all__
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    public_api.append(str(elt.value))
                                elif isinstance(elt, ast.Name):
                                    public_api.append(elt.id)
                        break

        if not public_api:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        public_api.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("_"):
                        public_api.append(node.name)
        return public_api

    def _get_private_api(self, tree: ast.AST) -> List[str]:
        private_api = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") and not node.name.startswith("__"):
                    private_api.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    private_api.append(node.name)
        return private_api

    def _get_imports(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _check_module_issues(self, module_info: ModuleInfo, tree: ast.AST, lines: List[str]) -> List[AtomIssue]:
        issues: List[AtomIssue] = []

        # 粒度检查
        if module_info.lines_count > self.MAX_LINES:
            issues.append(AtomIssue(
                issue_type="module_too_large",
                message=f"模块行数过多 ({module_info.lines_count})，建议不超过 {self.MAX_LINES}",
                line=1,
                column=0,
                severity=IssueSeverity.WARNING,
                suggestion="将大模块拆分为多个职责单一的小模块",
            ))

        if module_info.class_count > self.MAX_CLASSES:
            issues.append(AtomIssue(
                issue_type="too_many_classes",
                message=f"模块类数过多 ({module_info.class_count})，建议不超过 {self.MAX_CLASSES}",
                line=1,
                column=0,
                severity=IssueSeverity.WARNING,
                suggestion="考虑将不同职责的类拆分到独立模块",
            ))

        if module_info.function_count > self.MAX_FUNCTIONS:
            issues.append(AtomIssue(
                issue_type="too_many_functions",
                message=f"模块顶层函数数过多 ({module_info.function_count})，建议不超过 {self.MAX_FUNCTIONS}",
                line=1,
                column=0,
                severity=IssueSeverity.WARNING,
                suggestion="考虑将相关函数组织到类或独立模块中",
            ))

        # 接口清晰度
        if len(module_info.public_api) > self.MAX_PUBLIC_API:
            issues.append(AtomIssue(
                issue_type="too_many_public_api",
                message=f"公共API过多 ({len(module_info.public_api)})，建议不超过 {self.MAX_PUBLIC_API}",
                line=1,
                column=0,
                severity=IssueSeverity.WARNING,
                suggestion="使用 __all__ 精确控制公共接口",
            ))

        # 检查是否有 __all__
        has_all = any(
            isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__"
                for t in node.targets
            )
            for node in tree.body
        )
        if not has_all and len(module_info.public_api) > 5:
            issues.append(AtomIssue(
                issue_type="missing_all",
                message="模块缺少 __all__ 定义，公共接口不清晰",
                line=1,
                column=0,
                severity=IssueSeverity.WARNING,
                suggestion="建议显式定义 __all__ 以明确公共API",
            ))

        # 模块三区分离：导入区 -> 定义区 -> 执行区
        zone_issues = self._check_module_zones(tree, lines)
        issues.extend(zone_issues)

        return issues

    def _check_module_zones(self, tree: ast.AST, lines: List[str]) -> List[AtomIssue]:
        issues: List[AtomIssue] = []
        # 简化检查：确保导入语句在模块顶部
        last_import_line = 0
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_import_line = max(last_import_line, node.end_lineno or node.lineno)

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue  # 允许模块级 docstring
            if last_import_line and hasattr(node, "lineno") and node.lineno < last_import_line:
                # 有定义在导入之前（docstring除外）
                pass  # 实际上 ast 解析时 body 顺序就是代码顺序，这里不需要额外检查

        # 检查是否有顶层执行代码（非导入、非定义、非 docstring）
        execution_nodes = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            execution_nodes.append(node)

        if execution_nodes:
            # 允许 if __name__ == "__main__":
            for node in execution_nodes:
                if isinstance(node, ast.If):
                    if self._is_name_main_guard(node):
                        continue
                    issues.append(AtomIssue(
                        issue_type="execution_zone",
                        message=f"模块中存在顶层执行代码（行 {node.lineno}），建议放入 if __name__ == '__main__': 中",
                        line=node.lineno,
                        column=node.col_offset,
                        severity=IssueSeverity.WARNING,
                        suggestion="将执行代码放入主程序保护块中",
                    ))
                else:
                    issues.append(AtomIssue(
                        issue_type="execution_zone",
                        message=f"模块中存在顶层执行代码（行 {node.lineno}），建议放入 if __name__ == '__main__': 中",
                        line=node.lineno,
                        column=node.col_offset,
                        severity=IssueSeverity.WARNING,
                        suggestion="将执行代码放入主程序保护块中",
                    ))

        return issues

    @staticmethod
    def _is_name_main_guard(node: ast.If) -> bool:
        """检查是否为 if __name__ == '__main__':"""
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            ops = node.test.ops
            comparators = node.test.comparators
            if (isinstance(left, ast.Name) and left.id == "__name__"
                    and len(ops) == 1 and isinstance(ops[0], ast.Eq)
                    and len(comparators) == 1
                    and isinstance(comparators[0], ast.Constant)
                    and comparators[0].value == "__main__"):
                return True
        return False


# ==================== 综合扫描器 ====================

class UnifiedAtomScanner:
    """综合原子扫描器

    整合四级原子扫描，提供统一的扫描接口。
    """

    def __init__(self):
        self.variable_scanner = VariableAtomScanner()
        self.method_scanner = MethodAtomScanner()
        self.class_scanner = ClassAtomScanner()
        self.module_scanner = ModuleAtomScanner()

    def scan_source(self, source: str, module_name: str = "<module>") -> Dict[str, AtomScanResult]:
        """扫描源代码，返回各级扫描结果"""
        return {
            "variable": self.variable_scanner.scan(source),
            "method": self.method_scanner.scan(source),
            "class": self.class_scanner.scan(source),
            "module": self.module_scanner.scan(source, module_name),
        }

    def scan_file(self, file_path: str) -> Dict[str, AtomScanResult]:
        """扫描文件"""
        path = Path(file_path)
        source = path.read_text(encoding="utf-8")
        return self.scan_source(source, module_name=path.stem)

    def scan_directory(self, directory: str) -> Dict[str, Dict[str, AtomScanResult]]:
        """扫描目录"""
        results = {}
        for file in Path(directory).rglob("*.py"):
            results[str(file)] = self.scan_file(str(file))
        return results


def scan_file(file_path: str) -> Dict[str, AtomScanResult]:
    """便捷函数：扫描单个文件"""
    scanner = UnifiedAtomScanner()
    return scanner.scan_file(file_path)


def scan_source(source: str, module_name: str = "<module>") -> Dict[str, AtomScanResult]:
    """便捷函数：扫描源代码"""
    scanner = UnifiedAtomScanner()
    return scanner.scan_source(source, module_name)
