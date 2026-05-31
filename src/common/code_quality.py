"""
代码质量检查模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 代码复杂度分析（圈复杂度、认知复杂度）
2. 代码异味检测（重复代码、过长函数、过大类）
3. 技术债务评估
4. 质量评分
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class SmellType(Enum):
    """代码异味类型"""
    LONG_METHOD = "long_method"
    LONG_CLASS = "long_class"
    DUPLICATE_CODE = "duplicate_code"
    DEEP_NESTING = "deep_nesting"
    TOO_MANY_PARAMETERS = "too_many_parameters"
    GOD_CLASS = "god_class"
    FEATURE_ENVY = "feature_envy"


class Severity(Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodeSmell:
    """代码异味记录"""
    smell_type: SmellType
    severity: Severity
    file_path: str
    line_number: int
    message: str
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.smell_type.value,
            "severity": self.severity.value,
            "file": self.file_path,
            "line": self.line_number,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ComplexityReport:
    """复杂度报告"""
    file_path: str
    cyclomatic_complexity: int
    cognitive_complexity: int
    lines_of_code: int
    function_count: int
    class_count: int
    max_function_complexity: int = 0
    max_function_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file_path,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "cognitive_complexity": self.cognitive_complexity,
            "lines_of_code": self.lines_of_code,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "max_function_complexity": self.max_function_complexity,
            "max_function_name": self.max_function_name,
        }


@dataclass
class QualityScore:
    """质量评分"""
    overall: float
    maintainability: float
    reliability: float
    complexity_score: float
    duplication_score: float
    smells: List[CodeSmell] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 2),
            "maintainability": round(self.maintainability, 2),
            "reliability": round(self.reliability, 2),
            "complexity_score": round(self.complexity_score, 2),
            "duplication_score": round(self.duplication_score, 2),
            "smell_count": len(self.smells),
        }


@dataclass
class TechDebtItem:
    """技术债务项"""
    category: str
    description: str
    estimated_hours: float
    severity: Severity
    file_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "estimated_hours": self.estimated_hours,
            "severity": self.severity.value,
            "file": self.file_path,
        }


class ComplexityAnalyzer:
    """代码复杂度分析器"""

    def __init__(self):
        self.thresholds = {
            "cyclomatic_high": 10,
            "cyclomatic_critical": 20,
            "cognitive_high": 15,
            "method_lines": 50,
            "class_lines": 300,
        }

    def analyze_file(self, file_path: Union[str, Path]) -> ComplexityReport:
        """分析单个文件复杂度"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning(f"语法错误，跳过分析: {file_path}")
            return ComplexityReport(
                file_path=str(file_path),
                cyclomatic_complexity=0,
                cognitive_complexity=0,
                lines_of_code=len(source.splitlines()),
                function_count=0,
                class_count=0,
            )

        lines = source.splitlines()
        total_cyclomatic = 1
        total_cognitive = 0
        function_count = 0
        class_count = 0
        max_func_complexity = 0
        max_func_name = ""

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_count += 1
                func_complexity = self._calc_function_cyclomatic(node)
                total_cyclomatic += func_complexity - 1
                func_cognitive = self._calc_function_cognitive(node)
                total_cognitive += func_cognitive
                if func_complexity > max_func_complexity:
                    max_func_complexity = func_complexity
                    max_func_name = node.name
            elif isinstance(node, ast.ClassDef):
                class_count += 1

        report = ComplexityReport(
            file_path=str(file_path),
            cyclomatic_complexity=total_cyclomatic,
            cognitive_complexity=total_cognitive,
            lines_of_code=len(lines),
            function_count=function_count,
            class_count=class_count,
            max_function_complexity=max_func_complexity,
            max_function_name=max_func_name,
        )
        logger.info(f"复杂度分析完成: {file_path}")
        return report

    def _calc_function_cyclomatic(self, node: ast.FunctionDef) -> int:
        """计算函数圈复杂度"""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _calc_function_cognitive(self, node: ast.FunctionDef) -> int:
        """计算函数认知复杂度"""
        complexity = 0
        nesting = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1 + nesting
                nesting += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def analyze_directory(self, directory: Union[str, Path]) -> List[ComplexityReport]:
        """分析目录下所有Python文件"""
        directory = Path(directory)
        reports = []
        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                report = self.analyze_file(py_file)
                reports.append(report)
            except Exception as e:
                logger.warning(f"分析失败 {py_file}: {e}")
        return reports


class SmellDetector:
    """代码异味检测器"""

    def __init__(self):
        self.thresholds = {
            "max_method_lines": 50,
            "max_class_lines": 300,
            "max_parameters": 5,
            "max_nesting_depth": 4,
            "max_class_methods": 20,
        }

    def detect_file(self, file_path: Union[str, Path]) -> List[CodeSmell]:
        """检测单个文件的代码异味"""
        file_path = Path(file_path)
        smells = []

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return smells

        lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_smells = self._check_function(node, lines, str(file_path))
                smells.extend(func_smells)
            elif isinstance(node, ast.ClassDef):
                class_smells = self._check_class(node, lines, str(file_path))
                smells.extend(class_smells)

        duplicate_smells = self._check_duplicates(source, str(file_path))
        smells.extend(duplicate_smells)

        return smells

    def _check_function(self, node: ast.FunctionDef, lines: List[str], file_path: str) -> List[CodeSmell]:
        """检查函数异味"""
        smells = []
        func_lines = node.end_lineno - node.lineno if node.end_lineno else 1

        if func_lines > self.thresholds["max_method_lines"]:
            smells.append(CodeSmell(
                smell_type=SmellType.LONG_METHOD,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=node.lineno,
                message=f"函数 '{node.name}' 过长: {func_lines} 行",
                suggestion="考虑将函数拆分为多个小函数",
            ))

        param_count = len(node.args.args) + len(node.args.kwonlyargs)
        if param_count > self.thresholds["max_parameters"]:
            smells.append(CodeSmell(
                smell_type=SmellType.TOO_MANY_PARAMETERS,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=node.lineno,
                message=f"函数 '{node.name}' 参数过多: {param_count} 个",
                suggestion="考虑使用数据类或字典封装参数",
            ))

        max_depth = self._calc_nesting_depth(node)
        if max_depth > self.thresholds["max_nesting_depth"]:
            smells.append(CodeSmell(
                smell_type=SmellType.DEEP_NESTING,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=node.lineno,
                message=f"函数 '{node.name}' 嵌套过深: {max_depth} 层",
                suggestion="考虑使用提前返回或提取函数",
            ))

        return smells

    def _check_class(self, node: ast.ClassDef, lines: List[str], file_path: str) -> List[CodeSmell]:
        """检查类异味"""
        smells = []
        class_lines = node.end_lineno - node.lineno if node.end_lineno else 1

        if class_lines > self.thresholds["max_class_lines"]:
            smells.append(CodeSmell(
                smell_type=SmellType.LONG_CLASS,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=node.lineno,
                message=f"类 '{node.name}' 过大: {class_lines} 行",
                suggestion="考虑将类拆分为多个职责单一的类",
            ))

        method_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.FunctionDef))
        if method_count > self.thresholds["max_class_methods"]:
            smells.append(CodeSmell(
                smell_type=SmellType.GOD_CLASS,
                severity=Severity.CRITICAL,
                file_path=file_path,
                line_number=node.lineno,
                message=f"类 '{node.name}' 方法过多: {method_count} 个",
                suggestion="考虑按职责拆分",
            ))

        return smells

    def _calc_nesting_depth(self, node: ast.AST) -> int:
        """计算最大嵌套深度"""
        max_depth = 0
        current_depth = 0

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
        return max_depth

    def _check_duplicates(self, source: str, file_path: str) -> List[CodeSmell]:
        """检查重复代码（简单行哈希比对）"""
        smells = []
        lines = [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("#")]
        hashes: Dict[str, List[int]] = {}

        for i, line in enumerate(lines):
            h = hashlib.md5(line.encode()).hexdigest()
            hashes.setdefault(h, []).append(i + 1)

        for h, line_nums in hashes.items():
            if len(line_nums) >= 5:
                smells.append(CodeSmell(
                    smell_type=SmellType.DUPLICATE_CODE,
                    severity=Severity.MEDIUM,
                    file_path=file_path,
                    line_number=line_nums[0],
                    message=f"检测到 {len(line_nums)} 行重复代码",
                    suggestion="考虑提取为公共函数或常量",
                ))
                break

        return smells

    def detect_directory(self, directory: Union[str, Path]) -> List[CodeSmell]:
        """检测目录下所有Python文件"""
        directory = Path(directory)
        all_smells = []
        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            smells = self.detect_file(py_file)
            all_smells.extend(smells)
        return all_smells


class TechDebtEstimator:
    """技术债务评估器"""

    def __init__(self):
        self.hour_estimates = {
            SmellType.LONG_METHOD: 2.0,
            SmellType.LONG_CLASS: 4.0,
            SmellType.DUPLICATE_CODE: 1.5,
            SmellType.DEEP_NESTING: 1.0,
            SmellType.TOO_MANY_PARAMETERS: 0.5,
            SmellType.GOD_CLASS: 8.0,
            SmellType.FEATURE_ENVY: 2.0,
        }

    def estimate(self, smells: List[CodeSmell]) -> List[TechDebtItem]:
        """根据代码异味评估技术债务"""
        debts = []
        for smell in smells:
            hours = self.hour_estimates.get(smell.smell_type, 1.0)
            if smell.severity == Severity.CRITICAL:
                hours *= 2.0
            elif smell.severity == Severity.HIGH:
                hours *= 1.5
            debts.append(TechDebtItem(
                category=smell.smell_type.value,
                description=smell.message,
                estimated_hours=hours,
                severity=smell.severity,
                file_path=smell.file_path,
            ))
        return debts

    def summarize(self, debts: List[TechDebtItem]) -> Dict[str, Any]:
        """汇总技术债务"""
        total_hours = sum(d.estimated_hours for d in debts)
        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for d in debts:
            by_severity[d.severity.value] = by_severity.get(d.severity.value, 0) + 1
            by_category[d.category] = by_category.get(d.category, 0) + 1

        return {
            "total_items": len(debts),
            "total_estimated_hours": round(total_hours, 2),
            "by_severity": by_severity,
            "by_category": by_category,
        }


class QualityScorer:
    """质量评分器"""

    def __init__(self):
        self.weights = {
            "maintainability": 0.3,
            "reliability": 0.2,
            "complexity": 0.25,
            "duplication": 0.25,
        }

    def score(self, reports: List[ComplexityReport], smells: List[CodeSmell]) -> QualityScore:
        """计算质量评分"""
        if not reports:
            return QualityScore(overall=100.0, maintainability=100.0, reliability=100.0,
                                complexity_score=100.0, duplication_score=100.0)

        total_loc = sum(r.lines_of_code for r in reports)
        total_cc = sum(r.cyclomatic_complexity for r in reports)
        avg_cc = total_cc / max(total_loc, 1)

        maintainability = max(0, 100 - avg_cc * 5)
        reliability = max(0, 100 - len([s for s in smells if s.severity in (Severity.HIGH, Severity.CRITICAL)]) * 5)
        complexity_score = max(0, 100 - total_cc / max(len(reports), 1))
        duplication_score = max(0, 100 - len([s for s in smells if s.smell_type == SmellType.DUPLICATE_CODE]) * 10)

        overall = (
            maintainability * self.weights["maintainability"]
            + reliability * self.weights["reliability"]
            + complexity_score * self.weights["complexity"]
            + duplication_score * self.weights["duplication"]
        )

        return QualityScore(
            overall=overall,
            maintainability=maintainability,
            reliability=reliability,
            complexity_score=complexity_score,
            duplication_score=duplication_score,
            smells=smells,
        )


class CodeQualityEngine:
    """代码质量引擎 - 主类"""

    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.smell_detector = SmellDetector()
        self.tech_debt_estimator = TechDebtEstimator()
        self.quality_scorer = QualityScorer()
        logger.info("代码质量引擎初始化完成")

    def analyze(self, target: Union[str, Path]) -> Dict[str, Any]:
        """完整分析目标（文件或目录）"""
        target = Path(target)
        if target.is_file():
            reports = [self.complexity_analyzer.analyze_file(target)]
            smells = self.smell_detector.detect_file(target)
        else:
            reports = self.complexity_analyzer.analyze_directory(target)
            smells = self.smell_detector.detect_directory(target)

        debts = self.tech_debt_estimator.estimate(smells)
        score = self.quality_scorer.score(reports, smells)

        result = {
            "target": str(target),
            "complexity": [r.to_dict() for r in reports],
            "smells": [s.to_dict() for s in smells],
            "tech_debt": {
                "items": [d.to_dict() for d in debts],
                "summary": self.tech_debt_estimator.summarize(debts),
            },
            "quality_score": score.to_dict(),
        }
        logger.info(f"代码质量分析完成: {target}")
        return result

    def get_summary(self, result: Dict[str, Any]) -> str:
        """生成分析摘要"""
        score = result["quality_score"]
        summary = (
            f"代码质量分析摘要\n"
            f"  目标: {result['target']}\n"
            f"  综合评分: {score['overall']}/100\n"
            f"  可维护性: {score['maintainability']}/100\n"
            f"  可靠性: {score['reliability']}/100\n"
            f"  异味数量: {score['smell_count']}\n"
            f"  技术债务: {result['tech_debt']['summary']['total_estimated_hours']} 小时"
        )
        return summary
