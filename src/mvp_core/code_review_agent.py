"""
MVP阶段9: 代码审查Agent
遵循第一性原理：责任正交性、状态分离

核心功能：
1. CodeReviewAgent - 继承AgentBase，提供代码审查任务执行
2. CodeReviewer - 基于AST分析代码，检测代码异味和最佳实践
3. ReviewReport - 审查报告，包含问题分类、严重程度评级、修复建议
"""

import ast
import re
from abc import ABC
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.mvp_core.agent_base import AgentBase, MessageBus, AgentStatus
from src.mvp_core.atom_scanner import (
    UnifiedAtomScanner,
    AtomScanResult,
    AtomIssue,
    IssueSeverity,
)
from src.common.utils import setup_logger

logger = setup_logger(__name__)


# ==================== 审查报告数据类 ====================

class ReviewCategory(Enum):
    """审查问题分类"""
    CODE_QUALITY = "code_quality"
    ATOM_COMPLIANCE = "atom_compliance"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BEST_PRACTICE = "best_practice"


class SeverityLevel(Enum):
    """严重程度评级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ReviewIssue:
    """审查问题项"""
    category: ReviewCategory
    severity: SeverityLevel
    line: int
    column: int
    message: str
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None


@dataclass
class ReviewReport:
    """审查报告

    属性：
    - target: 审查目标（文件路径或模块名）
    - summary: 摘要统计
    - issues: 问题列表
    - metrics: 代码度量
    - timestamp: 生成时间
    """
    target: str
    issues: List[ReviewIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_issue(self, issue: ReviewIssue) -> None:
        """添加问题"""
        self.issues.append(issue)

    def get_issues_by_category(self, category: ReviewCategory) -> List[ReviewIssue]:
        """按分类获取问题"""
        return [i for i in self.issues if i.category == category]

    def get_issues_by_severity(self, severity: SeverityLevel) -> List[ReviewIssue]:
        """按严重程度获取问题"""
        return [i for i in self.issues if i.severity == severity]

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要统计"""
        summary = {
            "total_issues": len(self.issues),
            "by_category": {},
            "by_severity": {},
            "pass": len(self.issues) == 0,
        }
        for cat in ReviewCategory:
            summary["by_category"][cat.value] = len(self.get_issues_by_category(cat))
        for sev in SeverityLevel:
            summary["by_severity"][sev.value] = len(self.get_issues_by_severity(sev))
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "target": self.target,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.get_summary(),
            "metrics": self.metrics,
            "issues": [
                {
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "line": i.line,
                    "column": i.column,
                    "message": i.message,
                    "suggestion": i.suggestion,
                    "rule_id": i.rule_id,
                }
                for i in self.issues
            ],
        }


# ==================== 代码审查器 ====================

class CodeReviewer:
    """代码审查器

    基于AST分析代码，检测：
    - 代码异味
    - 最佳实践违规
    - 安全问题
    - 性能问题
    """

    # 危险函数列表
    DANGEROUS_FUNCTIONS = {
        "eval", "exec", "compile", "__import__",
        "os.system", "subprocess.call", "subprocess.Popen",
        "pickle.loads", "yaml.load",
    }

    # 性能反模式
    PERFORMANCE_ANTIPATTERNS = {
        "list_concat_in_loop": "在循环中使用列表拼接，建议使用列表推导或append",
        "repeated_attr_lookup": "重复属性查找，建议缓存到局部变量",
        "inefficient_string_concat": "低效字符串拼接，建议使用join",
    }

    def __init__(self):
        self.atom_scanner = UnifiedAtomScanner()

    def review(self, source: str, target_name: str = "<module>") -> ReviewReport:
        """执行完整审查"""
        report = ReviewReport(target=target_name)

        # 1. 代码质量检查（基于AST）
        self._check_code_quality(source, report)

        # 2. 原子规范审查
        self._check_atom_compliance(source, target_name, report)

        # 3. 安全问题检测
        self._check_security(source, report)

        # 4. 性能问题检测
        self._check_performance(source, report)

        # 5. 最佳实践检查
        self._check_best_practices(source, report)

        # 基础度量
        report.metrics = self._calculate_metrics(source)

        return report

    def review_file(self, file_path: str) -> ReviewReport:
        """审查文件"""
        path = Path(file_path)
        source = path.read_text(encoding="utf-8")
        return self.review(source, target_name=str(path))

    def _check_code_quality(self, source: str, report: ReviewReport) -> None:
        """代码质量检查"""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            report.add_issue(ReviewIssue(
                category=ReviewCategory.CODE_QUALITY,
                severity=SeverityLevel.CRITICAL,
                line=getattr(e, "lineno", 0),
                column=getattr(e, "offset", 0),
                message=f"语法错误: {e}",
                suggestion="修复语法错误后再进行审查",
                rule_id="SYNTAX_ERROR",
            ))
            return

        # 检查空代码块
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = node.body
                # 跳过 docstring
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    effective_body = body[1:]
                else:
                    effective_body = body

                # 判断是否为真正空实现：无有效语句，或仅包含 Pass / Ellipsis
                def _is_empty_stmt(stmt):
                    if isinstance(stmt, ast.Pass):
                        return True
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                        if stmt.value.value is ... or stmt.value.value is Ellipsis:
                            return True
                    return False

                is_empty = not effective_body or all(_is_empty_stmt(s) for s in effective_body)

                if is_empty:
                    report.add_issue(ReviewIssue(
                        category=ReviewCategory.CODE_QUALITY,
                        severity=SeverityLevel.MEDIUM,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"{'方法' if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else '类'} '{node.name}' 为空实现",
                        suggestion="移除空实现或添加TODO注释说明",
                        rule_id="EMPTY_BODY",
                    ))

        # 检查过深嵌套
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                depth = self._calculate_nesting_depth(node)
                if depth > 4:
                    report.add_issue(ReviewIssue(
                        category=ReviewCategory.CODE_QUALITY,
                        severity=SeverityLevel.HIGH,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"方法 '{node.name}' 嵌套深度过大 ({depth} 层)",
                        suggestion="建议提取内部逻辑为独立方法，降低嵌套深度",
                        rule_id="DEEP_NESTING",
                    ))

        # 检查过长行
        lines = source.split("\n")
        for idx, line in enumerate(lines, start=1):
            if len(line) > 120:
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.CODE_QUALITY,
                    severity=SeverityLevel.LOW,
                    line=idx,
                    column=0,
                    message=f"行过长 ({len(line)} 字符)，建议不超过 120 字符",
                    suggestion="换行或提取变量",
                    rule_id="LONG_LINE",
                ))

    def _check_atom_compliance(self, source: str, target_name: str, report: ReviewReport) -> None:
        """原子规范审查"""
        results = self.atom_scanner.scan_source(source, target_name)

        severity_map = {
            IssueSeverity.ERROR: SeverityLevel.HIGH,
            IssueSeverity.WARNING: SeverityLevel.MEDIUM,
            IssueSeverity.INFO: SeverityLevel.LOW,
        }

        for scan_type, result in results.items():
            for issue in result.issues:
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.ATOM_COMPLIANCE,
                    severity=severity_map.get(issue.severity, SeverityLevel.LOW),
                    line=issue.line,
                    column=issue.column,
                    message=f"[{scan_type}] {issue.message}",
                    suggestion=issue.suggestion,
                    rule_id=issue.issue_type,
                ))

    def _check_security(self, source: str, report: ReviewReport) -> None:
        """安全问题检测"""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        # 检测危险函数调用
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name in self.DANGEROUS_FUNCTIONS:
                    report.add_issue(ReviewIssue(
                        category=ReviewCategory.SECURITY,
                        severity=SeverityLevel.CRITICAL,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"检测到危险函数调用: {func_name}",
                        suggestion="避免使用危险函数，使用更安全的替代方案",
                        rule_id="DANGEROUS_FUNCTION",
                    ))

        # 检测硬编码密码/密钥
        password_patterns = re.compile(r'(password|passwd|secret|key|token)\s*=\s*["\'][^"\']+["\']', re.IGNORECASE)
        for idx, line in enumerate(source.split("\n"), start=1):
            if password_patterns.search(line):
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.CRITICAL,
                    line=idx,
                    column=0,
                    message="检测到可能的硬编码密码或密钥",
                    suggestion="使用环境变量或密钥管理服务",
                    rule_id="HARDCODED_SECRET",
                ))

        # 检测SQL字符串拼接
        sql_patterns = re.compile(r'(SELECT|INSERT|UPDATE|DELETE|DROP)\s+', re.IGNORECASE)
        for idx, line in enumerate(source.split("\n"), start=1):
            if sql_patterns.search(line) and ("f\"" in line or "f'" in line or "%" in line or "+" in line):
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.HIGH,
                    line=idx,
                    column=0,
                    message="检测到可能的SQL注入风险（SQL字符串拼接）",
                    suggestion="使用参数化查询或ORM",
                    rule_id="SQL_INJECTION_RISK",
                ))

    def _check_performance(self, source: str, report: ReviewReport) -> None:
        """性能问题检测"""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        # 检测循环中的字符串拼接
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                for child in ast.walk(node):
                    if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                        if isinstance(child.target, ast.Name):
                            report.add_issue(ReviewIssue(
                                category=ReviewCategory.PERFORMANCE,
                                severity=SeverityLevel.MEDIUM,
                                line=child.lineno,
                                column=child.col_offset,
                                message="循环中使用 += 拼接，可能导致性能问题",
                                suggestion="使用列表收集后通过 str.join() 合并",
                                rule_id="STRING_CONCAT_IN_LOOP",
                            ))

        # 检测列表作为默认参数
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        report.add_issue(ReviewIssue(
                            category=ReviewCategory.PERFORMANCE,
                            severity=SeverityLevel.HIGH,
                            line=node.lineno,
                            column=node.col_offset,
                            message=f"方法 '{node.name}' 使用可变对象作为默认参数",
                            suggestion="使用 None 作为默认值，在方法内部初始化",
                            rule_id="MUTABLE_DEFAULT_ARG",
                        ))

        # 检测重复导入
        imports: Dict[str, List[int]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.setdefault(alias.name, []).append(node.lineno)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.setdefault(node.module, []).append(node.lineno)

        for module, lines in imports.items():
            if len(lines) > 1:
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.PERFORMANCE,
                    severity=SeverityLevel.LOW,
                    line=lines[1],
                    column=0,
                    message=f"模块 '{module}' 被重复导入 {len(lines)} 次",
                    suggestion="移除重复导入",
                    rule_id="DUPLICATE_IMPORT",
                ))

    def _check_best_practices(self, source: str, report: ReviewReport) -> None:
        """最佳实践检查"""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        # 检测裸 except
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if handler.type is None:
                        report.add_issue(ReviewIssue(
                            category=ReviewCategory.BEST_PRACTICE,
                            severity=SeverityLevel.HIGH,
                            line=handler.lineno,
                            column=handler.col_offset,
                            message="使用了裸 except:，会捕获所有异常包括 KeyboardInterrupt",
                            suggestion="指定具体的异常类型，如 except ValueError:",
                            rule_id="BARE_EXCEPT",
                        ))

        # 检测未使用的导入
        imported_names: Dict[str, int] = {}
        used_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name.split(".")[0]
                    imported_names[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imported_names[name] = node.lineno
            elif isinstance(node, ast.Name):
                used_names.add(node.id)

        for name, line in imported_names.items():
            if name not in used_names and name != "*":
                report.add_issue(ReviewIssue(
                    category=ReviewCategory.BEST_PRACTICE,
                    severity=SeverityLevel.LOW,
                    line=line,
                    column=0,
                    message=f"导入的 '{name}' 可能未被使用",
                    suggestion="移除未使用的导入",
                    rule_id="UNUSED_IMPORT",
                ))

        # 检测类中缺少 __repr__
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                has_repr = any(
                    isinstance(item, ast.FunctionDef) and item.name == "__repr__"
                    for item in node.body
                )
                if not has_repr:
                    report.add_issue(ReviewIssue(
                        category=ReviewCategory.BEST_PRACTICE,
                        severity=SeverityLevel.LOW,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"类 '{node.name}' 缺少 __repr__ 方法",
                        suggestion="添加 __repr__ 方法以便于调试和日志记录",
                        rule_id="MISSING_REPR",
                    ))

    def _calculate_metrics(self, source: str) -> Dict[str, Any]:
        """计算代码度量"""
        lines = source.split("\n")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {
                "total_lines": len(lines),
                "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
                "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
                "blank_lines": len([l for l in lines if not l.strip()]),
            }

        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

        return {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
            "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "function_count": len(functions),
            "class_count": len(classes),
        }

    @staticmethod
    def _calculate_nesting_depth(node: ast.AST) -> int:
        """计算嵌套深度"""
        max_depth = 0

        class DepthVisitor(ast.NodeVisitor):
            def __init__(self):
                self.depth = 0
                self.max_depth = 0

            def visit_If(self, n):
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)
                self.generic_visit(n)
                self.depth -= 1

            def visit_For(self, n):
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)
                self.generic_visit(n)
                self.depth -= 1

            def visit_While(self, n):
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)
                self.generic_visit(n)
                self.depth -= 1

            def visit_With(self, n):
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)
                self.generic_visit(n)
                self.depth -= 1

            def visit_Try(self, n):
                self.depth += 1
                self.max_depth = max(self.max_depth, self.depth)
                self.generic_visit(n)
                self.depth -= 1

        visitor = DepthVisitor()
        visitor.visit(node)
        return visitor.max_depth

    @staticmethod
    def _get_call_name(node: ast.Call) -> str:
        """获取函数调用名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


# ==================== 代码审查Agent ====================

class CodeReviewAgent(AgentBase):
    """代码审查Agent

    继承AgentBase，提供：
    - 代码质量检查
    - 原子规范审查
    - 安全问题检测
    - 性能问题检测
    - 审查报告生成
    """

    def __init__(self, name: str = "code_review_agent", message_bus: Optional[MessageBus] = None):
        """初始化代码审查Agent"""
        super().__init__(name=name, message_bus=message_bus)
        self.reviewer = CodeReviewer()
        self._reports: List[ReviewReport] = []
        logger.info(f"CodeReviewAgent初始化完成: {name}")

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行审查任务

        任务参数：
        - source: 源代码字符串（与file_path二选一）
        - file_path: 文件路径（与source二选一）
        - target_name: 目标名称（可选）

        返回：
        - report: 审查报告字典
        - success: 是否成功
        """
        self.status = AgentStatus.BUSY
        try:
            source = task.get("source")
            file_path = task.get("file_path")
            target_name = task.get("target_name", file_path or "<module>")

            if file_path:
                report = self.reviewer.review_file(file_path)
            elif source:
                report = self.reviewer.review(source, target_name)
            else:
                return {
                    "success": False,
                    "error": "缺少审查目标，请提供 source 或 file_path",
                    "report": None,
                }

            self._reports.append(report)
            self.status = AgentStatus.IDLE
            return {
                "success": True,
                "report": report.to_dict(),
            }
        except Exception as e:
            logger.error(f"代码审查失败: {e}")
            self.status = AgentStatus.ERROR
            return {
                "success": False,
                "error": str(e),
                "report": None,
            }

    def review_source(self, source: str, target_name: str = "<module>") -> ReviewReport:
        """审查源代码"""
        return self.reviewer.review(source, target_name)

    def review_file(self, file_path: str) -> ReviewReport:
        """审查文件"""
        return self.reviewer.review_file(file_path)

    def get_reports(self) -> List[ReviewReport]:
        """获取所有审查报告"""
        return self._reports.copy()

    def get_latest_report(self) -> Optional[ReviewReport]:
        """获取最新审查报告"""
        if self._reports:
            return self._reports[-1]
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        base_status = super().get_status()
        base_status["review_count"] = len(self._reports)
        base_status["latest_target"] = self._reports[-1].target if self._reports else None
        return base_status
