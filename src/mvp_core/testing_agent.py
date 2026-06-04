"""
MVP阶段7: 测试Agent
遵循第一性原理：责任正交性、状态分离
"""

import ast
import importlib.util
import inspect
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus
from src.common.utils import setup_logger, AgentException

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """测试用例 - 原子化测试单元"""
    name: str
    target_function: str
    source: str
    test_type: str  # unit, boundary, exception
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """单个测试结果"""
    test_name: str
    status: str  # passed, failed, error, skipped
    duration: float = 0.0
    message: Optional[str] = None
    traceback: Optional[str] = None


@dataclass
class TestReport:
    """测试报告"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    duration: float = 0.0
    results: List[TestResult] = field(default_factory=list)
    coverage: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "skipped": self.skipped,
            "duration": self.duration,
            "results": [
                {
                    "test_name": r.test_name,
                    "status": r.status,
                    "duration": r.duration,
                    "message": r.message,
                }
                for r in self.results
            ],
            "coverage": self.coverage,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CoverageInfo:
    """覆盖率信息"""
    file_path: str
    line_rate: float = 0.0
    branch_rate: float = 0.0
    missing_lines: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TestCaseGenerator - 测试用例生成器
# ---------------------------------------------------------------------------

class TestCaseGenerator:
    """
    测试用例生成器 - 基于代码分析自动生成测试

    核心方法：
    - generate_for_function: 为函数生成单元测试
    - generate_boundary_tests: 生成边界值测试
    - generate_exception_tests: 生成异常测试
    """

    def __init__(self):
        self._generated_cases: List[TestCase] = []

    def generate_for_function(
        self,
        func_name: str,
        source_code: str,
        module_name: str = "target_module",
    ) -> List[TestCase]:
        """
        为函数生成单元测试

        Args:
            func_name: 目标函数名
            source_code: 函数所在源码
            module_name: 模块名（用于import）
        """
        cases: List[TestCase] = []

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return cases

        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                target_node = node
                break

        if target_node is None:
            return cases

        # 解析参数
        args = self._extract_args(target_node)

        # 生成基本单元测试
        unit_case = self._build_unit_test(func_name, args, module_name)
        cases.append(unit_case)

        # 生成边界值测试
        boundary_cases = self._build_boundary_tests(func_name, args, module_name)
        cases.extend(boundary_cases)

        # 生成异常测试
        exception_case = self._build_exception_test(func_name, args, module_name)
        cases.append(exception_case)

        self._generated_cases.extend(cases)
        logger.info(f"为函数 {func_name} 生成 {len(cases)} 个测试用例")
        return cases

    def generate_boundary_tests(
        self,
        func_name: str,
        source_code: str,
        module_name: str = "target_module",
    ) -> List[TestCase]:
        """生成边界值分析测试"""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                target_node = node
                break

        if target_node is None:
            return []

        args = self._extract_args(target_node)
        cases = self._build_boundary_tests(func_name, args, module_name)
        self._generated_cases.extend(cases)
        return cases

    def generate_exception_tests(
        self,
        func_name: str,
        source_code: str,
        module_name: str = "target_module",
    ) -> List[TestCase]:
        """生成异常测试"""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                target_node = node
                break

        if target_node is None:
            return []

        args = self._extract_args(target_node)
        case = self._build_exception_test(func_name, args, module_name)
        self._generated_cases.append(case)
        return [case]

    def _extract_args(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """提取函数参数信息"""
        args: List[Dict[str, Any]] = []
        for arg in node.args.args:
            arg_info = {"name": arg.arg, "annotation": None, "default": None}
            if arg.annotation:
                arg_info["annotation"] = ast.unparse(arg.annotation)
            args.append(arg_info)

        # 处理默认值
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                idx = len(args) - len(defaults) + i
                if idx >= 0:
                    args[idx]["default"] = ast.unparse(default)
        return args

    def _build_unit_test(
        self,
        func_name: str,
        args: List[Dict[str, Any]],
        module_name: str,
    ) -> TestCase:
        """构建基本单元测试"""
        arg_values = self._generate_default_values(args)
        arg_str = ", ".join(f"{k}={v}" for k, v in arg_values.items())

        source = textwrap.dedent(f"""
            def test_{func_name}_basic():
                from {module_name} import {func_name}
                result = {func_name}({arg_str})
                assert result is not None
        """).strip() + "\n"

        return TestCase(
            name=f"test_{func_name}_basic",
            target_function=func_name,
            source=source,
            test_type="unit",
            description=f"{func_name} 基本功能测试",
        )

    def _build_boundary_tests(
        self,
        func_name: str,
        args: List[Dict[str, Any]],
        module_name: str,
    ) -> List[TestCase]:
        """构建边界值测试"""
        cases: List[TestCase] = []
        boundary_values = self._get_boundary_values(args)

        for i, values in enumerate(boundary_values):
            arg_str = ", ".join(f"{k}={v}" for k, v in values.items())
            source = textwrap.dedent(f"""
                def test_{func_name}_boundary_{i + 1}():
                    from {module_name} import {func_name}
                    result = {func_name}({arg_str})
                    assert result is not None
            """).strip() + "\n"

            cases.append(TestCase(
                name=f"test_{func_name}_boundary_{i + 1}",
                target_function=func_name,
                source=source,
                test_type="boundary",
                description=f"{func_name} 边界值测试 {i + 1}",
            ))

        return cases

    def _build_exception_test(
        self,
        func_name: str,
        args: List[Dict[str, Any]],
        module_name: str,
    ) -> TestCase:
        """构建异常测试"""
        source = textwrap.dedent(f"""
            import pytest

            def test_{func_name}_exception():
                from {module_name} import {func_name}
                with pytest.raises(Exception):
                    {func_name}()
        """).strip() + "\n"

        return TestCase(
            name=f"test_{func_name}_exception",
            target_function=func_name,
            source=source,
            test_type="exception",
            description=f"{func_name} 异常输入测试",
        )

    def _generate_default_values(self, args: List[Dict[str, Any]]) -> Dict[str, str]:
        """生成默认参数值"""
        values: Dict[str, str] = {}
        for arg in args:
            name = arg["name"]
            annotation = arg.get("annotation") or ""
            default = arg.get("default")

            if default is not None:
                values[name] = default
            elif "int" in annotation:
                values[name] = "1"
            elif "float" in annotation:
                values[name] = "1.0"
            elif "str" in annotation:
                values[name] = '"test"'
            elif "bool" in annotation:
                values[name] = "True"
            elif "list" in annotation:
                values[name] = "[]"
            elif "dict" in annotation:
                values[name] = "{}"
            else:
                values[name] = "None"
        return values

    def _get_boundary_values(self, args: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """获取边界值组合"""
        if not args:
            return [{}]

        values_list: List[Dict[str, str]] = []
        for arg in args:
            name = arg["name"]
            annotation = arg.get("annotation") or ""
            if "int" in annotation:
                values_list.append({name: "0"})
                values_list.append({name: "-1"})
            elif "float" in annotation:
                values_list.append({name: "0.0"})
                values_list.append({name: "-1.0"})
            elif "str" in annotation:
                values_list.append({name: '""'})
            else:
                values_list.append({name: "None"})

        # 简化：返回前3个边界组合
        return values_list[:3] if values_list else [{}]

    def get_generated_cases(self) -> List[TestCase]:
        """获取所有生成的测试用例"""
        return self._generated_cases.copy()


# ---------------------------------------------------------------------------
# TestRunner - 测试运行器
# ---------------------------------------------------------------------------

class TestRunner:
    """
    测试运行器 - 执行测试并收集结果

    核心方法：
    - run_tests: 执行测试
    - run_with_pytest: 使用pytest执行
    - collect_results: 收集测试结果
    """

    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or os.getcwd()
        self._last_report: Optional[TestReport] = None

    def run_tests(
        self,
        test_path: str,
        coverage: bool = False,
    ) -> TestReport:
        """
        执行测试

        Args:
            test_path: 测试文件或目录路径
            coverage: 是否启用覆盖率分析
        """
        report = self.run_with_pytest(test_path, coverage=coverage)
        self._last_report = report
        return report

    def run_with_pytest(
        self,
        test_path: str,
        coverage: bool = False,
    ) -> TestReport:
        """使用pytest执行测试"""
        report = TestReport()

        if not Path(test_path).exists():
            report.error += 1
            report.total += 1
            report.results.append(TestResult(
                test_name="pytest_execution",
                status="error",
                message=f"测试路径不存在: {test_path}",
            ))
            return report

        cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
        if coverage:
            cmd.extend(["--cov", "--cov-report=term-missing", "--cov-report=json"])

        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            report.error += 1
            report.total += 1
            report.results.append(TestResult(
                test_name="pytest_execution",
                status="error",
                message="测试执行超时",
            ))
            return report
        except Exception as e:
            report.error += 1
            report.total += 1
            report.results.append(TestResult(
                test_name="pytest_execution",
                status="error",
                message=str(e),
            ))
            return report

        # 解析pytest输出
        report = self._parse_pytest_output(result.stdout + "\n" + result.stderr)

        # 若启用覆盖率，解析覆盖率报告
        if coverage:
            report.coverage = self._parse_coverage_report()

        self._last_report = report
        return report

    def _parse_pytest_output(self, output: str) -> TestReport:
        """解析pytest输出"""
        report = TestReport()
        lines = output.splitlines()

        for line in lines:
            line_stripped = line.strip()
            # pytest -v 输出格式: path::test_name PASSED/FAILED/ERROR/SKIPPED
            if " PASSED" in line_stripped:
                test_name = line_stripped.split(" PASSED")[0].strip()
                report.passed += 1
                report.total += 1
                report.results.append(TestResult(
                    test_name=test_name,
                    status="passed",
                ))
            elif " FAILED" in line_stripped:
                test_name = line_stripped.split(" FAILED")[0].strip()
                report.failed += 1
                report.total += 1
                report.results.append(TestResult(
                    test_name=test_name,
                    status="failed",
                ))
            elif " ERROR" in line_stripped:
                test_name = line_stripped.split(" ERROR")[0].strip()
                report.error += 1
                report.total += 1
                report.results.append(TestResult(
                    test_name=test_name,
                    status="error",
                ))
            elif " SKIPPED" in line_stripped:
                test_name = line_stripped.split(" SKIPPED")[0].strip()
                report.skipped += 1
                report.total += 1
                report.results.append(TestResult(
                    test_name=test_name,
                    status="skipped",
                ))

        # 尝试从汇总行解析（处理只有 passed 没有 failed 的情况）
        for line in lines:
            line_stripped = line.strip()
            if "passed" in line_stripped or "failed" in line_stripped or "error" in line_stripped:
                # 匹配 pytest 汇总行，例如:
                # 5 passed, 2 failed, 1 error in 0.12s
                # 2 passed in 0.01s
                if " in " in line_stripped and any(kw in line_stripped for kw in ("passed", "failed", "error", "skipped")):
                    parts = line_stripped.split(",")
                    for part in parts:
                        part_clean = part.strip()
                        if "passed" in part_clean:
                            try:
                                report.passed = int(part_clean.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif "failed" in part_clean:
                            try:
                                report.failed = int(part_clean.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif "error" in part_clean:
                            try:
                                report.error = int(part_clean.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif "skipped" in part_clean:
                            try:
                                report.skipped = int(part_clean.split()[0])
                            except (ValueError, IndexError):
                                pass
                    # 提取时间
                    if " in " in line_stripped:
                        time_part = line_stripped.split(" in ")[-1].strip().replace("s", "")
                        try:
                            report.duration = float(time_part)
                        except ValueError:
                            pass
                    break

        if report.total == 0:
            report.total = report.passed + report.failed + report.error + report.skipped

        return report

    def _parse_coverage_report(self) -> Dict[str, Any]:
        """解析覆盖率报告"""
        coverage_json = Path(self.working_dir) / "coverage.json"
        if not coverage_json.exists():
            return {}

        try:
            import json
            data = json.loads(coverage_json.read_text(encoding="utf-8"))
            totals = data.get("totals", {})
            return {
                "line_rate": totals.get("covered_lines", 0) / max(totals.get("num_statements", 1), 1),
                "branch_rate": totals.get("covered_branches", 0) / max(totals.get("num_branches", 1), 1),
                "missing_lines": totals.get("missing_lines", []),
            }
        except Exception as e:
            logger.warning(f"解析覆盖率报告失败: {e}")
            return {}

    def generate_report(self, report: Optional[TestReport] = None) -> str:
        """生成文本格式测试报告"""
        r = report or self._last_report
        if r is None:
            return "暂无测试报告"

        lines: List[str] = [
            "=" * 60,
            "测试报告",
            "=" * 60,
            f"总用例数: {r.total}",
            f"通过: {r.passed}",
            f"失败: {r.failed}",
            f"错误: {r.error}",
            f"跳过: {r.skipped}",
            f"耗时: {r.duration:.3f}s",
            "-" * 60,
        ]

        for result in r.results:
            status_icon = {
                "passed": "✓",
                "failed": "✗",
                "error": "!",
                "skipped": "-",
            }.get(result.status, "?")
            lines.append(f"{status_icon} {result.test_name} ({result.status})")
            if result.message:
                lines.append(f"   消息: {result.message}")

        if r.coverage:
            lines.extend([
                "-" * 60,
                "覆盖率分析:",
                f"  行覆盖率: {r.coverage.get('line_rate', 0) * 100:.1f}%",
                f"  分支覆盖率: {r.coverage.get('branch_rate', 0) * 100:.1f}%",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_last_report(self) -> Optional[TestReport]:
        """获取最近一次测试报告"""
        return self._last_report


# ---------------------------------------------------------------------------
# TestingAgent - 测试Agent
# ---------------------------------------------------------------------------

class TestingAgent(AgentBase):
    """
    测试Agent - 负责测试用例生成、执行和报告

    核心职责：
    - 测试用例生成：基于代码分析自动生成测试
    - 测试执行：使用pytest运行测试
    - 测试报告生成：汇总测试结果
    - 覆盖率分析：分析代码覆盖率
    """

    def __init__(
        self,
        name: str = "testing_agent",
        message_bus: Optional[MessageBus] = None,
        working_dir: Optional[str] = None,
    ):
        super().__init__(name=name, message_bus=message_bus)
        self.generator = TestCaseGenerator()
        self.runner = TestRunner(working_dir=working_dir)
        self._generated_tests: Dict[str, List[TestCase]] = {}
        self._last_report: Optional[TestReport] = None
        logger.info(f"TestingAgent初始化完成: {name}")

    # ------------------------------
    # 测试用例生成
    # ------------------------------

    def generate_tests(self, task: Dict[str, Any]) -> List[TestCase]:
        """
        基于代码分析生成测试用例

        task格式：
        {
            "file_path": str,
            "target_function": str,  # 可选，指定函数
        }
        """
        file_path = task.get("file_path")
        target_function = task.get("target_function")

        if not file_path or not Path(file_path).exists():
            raise AgentException(f"文件不存在: {file_path}")

        content = Path(file_path).read_text(encoding="utf-8")
        module_name = Path(file_path).stem

        cases: List[TestCase] = []
        if target_function:
            cases = self.generator.generate_for_function(
                func_name=target_function,
                source_code=content,
                module_name=module_name,
            )
        else:
            # 为文件中所有函数生成测试
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                raise AgentException(f"语法解析失败: {e}")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_cases = self.generator.generate_for_function(
                        func_name=node.name,
                        source_code=content,
                        module_name=module_name,
                    )
                    cases.extend(func_cases)

        self._generated_tests[file_path] = cases
        logger.info(f"测试用例生成完成: {file_path} ({len(cases)} 个)")
        return cases

    def generate_boundary_tests(self, task: Dict[str, Any]) -> List[TestCase]:
        """生成边界值测试"""
        file_path = task.get("file_path")
        target_function = task.get("target_function")

        if not file_path or not Path(file_path).exists():
            raise AgentException(f"文件不存在: {file_path}")

        content = Path(file_path).read_text(encoding="utf-8")
        module_name = Path(file_path).stem

        if not target_function:
            raise AgentException("边界值测试需要指定 target_function")

        cases = self.generator.generate_boundary_tests(
            func_name=target_function,
            source_code=content,
            module_name=module_name,
        )
        logger.info(f"边界值测试生成完成: {target_function} ({len(cases)} 个)")
        return cases

    def generate_exception_tests(self, task: Dict[str, Any]) -> List[TestCase]:
        """生成异常测试"""
        file_path = task.get("file_path")
        target_function = task.get("target_function")

        if not file_path or not Path(file_path).exists():
            raise AgentException(f"文件不存在: {file_path}")

        content = Path(file_path).read_text(encoding="utf-8")
        module_name = Path(file_path).stem

        if not target_function:
            raise AgentException("异常测试需要指定 target_function")

        cases = self.generator.generate_exception_tests(
            func_name=target_function,
            source_code=content,
            module_name=module_name,
        )
        logger.info(f"异常测试生成完成: {target_function} ({len(cases)} 个)")
        return cases

    # ------------------------------
    # 测试执行
    # ------------------------------

    def run_tests(self, task: Dict[str, Any]) -> TestReport:
        """
        执行测试

        task格式：
        {
            "test_path": str,
            "coverage": bool,  # 是否启用覆盖率
        }
        """
        test_path = task.get("test_path")
        coverage = task.get("coverage", False)

        if not test_path:
            raise AgentException("必须指定 test_path")

        report = self.runner.run_tests(test_path, coverage=coverage)
        self._last_report = report
        logger.info(f"测试执行完成: {report.passed}/{report.total} 通过")
        return report

    # ------------------------------
    # 测试报告
    # ------------------------------

    def generate_report(self, task: Optional[Dict[str, Any]] = None) -> str:
        """生成测试报告"""
        report = self._last_report
        if task and "report" in task:
            report = task["report"]
        return self.runner.generate_report(report)

    # ------------------------------
    # 覆盖率分析
    # ------------------------------

    def analyze_coverage(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析代码覆盖率

        task格式：
        {
            "test_path": str,
            "source_path": str,  # 可选
        }
        """
        test_path = task.get("test_path")
        if not test_path:
            raise AgentException("必须指定 test_path")

        report = self.runner.run_tests(test_path, coverage=True)
        self._last_report = report
        logger.info(f"覆盖率分析完成: 行覆盖率 {report.coverage.get('line_rate', 0) * 100:.1f}%")
        return report.coverage

    # ------------------------------
    # 保存生成的测试到文件
    # ------------------------------

    def save_tests(self, task: Dict[str, Any]) -> str:
        """
        将生成的测试用例保存到文件

        task格式：
        {
            "file_path": str,  # 源文件路径
            "output_path": str,  # 输出测试文件路径
        }
        """
        file_path = task.get("file_path")
        output_path = task.get("output_path")

        if not file_path or file_path not in self._generated_tests:
            raise AgentException(f"未找到生成的测试: {file_path}")

        cases = self._generated_tests[file_path]
        lines: List[str] = [
            f'"""\nAuto-generated tests for {file_path}\n"""\n',
            "import pytest\n",
        ]

        for case in cases:
            lines.append(f"# {case.description or case.name}")
            lines.append(case.source)
            lines.append("")

        content = "\n".join(lines)
        Path(output_path).write_text(content, encoding="utf-8")
        logger.info(f"测试文件已保存: {output_path}")
        return output_path

    # ------------------------------
    # AgentBase 抽象方法实现
    # ------------------------------

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务 - TestingAgent核心入口

        task格式：
        {
            "action": "generate" | "run" | "report" | "coverage" | "save",
            ... 其他参数
        }
        """
        action = task.get("action")
        self.status = AgentStatus.BUSY

        try:
            if action == "generate":
                cases = self.generate_tests(task)
                return {
                    "success": True,
                    "action": action,
                    "cases": cases,
                    "count": len(cases),
                }
            elif action == "generate_boundary":
                cases = self.generate_boundary_tests(task)
                return {
                    "success": True,
                    "action": action,
                    "cases": cases,
                    "count": len(cases),
                }
            elif action == "generate_exception":
                cases = self.generate_exception_tests(task)
                return {
                    "success": True,
                    "action": action,
                    "cases": cases,
                    "count": len(cases),
                }
            elif action == "run":
                report = self.run_tests(task)
                return {
                    "success": True,
                    "action": action,
                    "report": report,
                }
            elif action == "report":
                text = self.generate_report(task)
                return {
                    "success": True,
                    "action": action,
                    "text": text,
                }
            elif action == "coverage":
                coverage = self.analyze_coverage(task)
                return {
                    "success": True,
                    "action": action,
                    "coverage": coverage,
                }
            elif action == "save":
                path = self.save_tests(task)
                return {
                    "success": True,
                    "action": action,
                    "path": path,
                }
            else:
                raise AgentException(f"不支持的操作: {action}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"任务执行失败: {e}")
            return {
                "success": False,
                "action": action,
                "error": str(e),
            }
        finally:
            self.status = AgentStatus.IDLE
