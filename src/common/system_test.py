"""
系统测试框架模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 集成测试（模块间接口验证）
2. 端到端测试（完整业务流程）
3. 性能测试（响应时间、吞吐量）
4. 测试报告生成
"""

from __future__ import annotations

import json
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestType(Enum):
    """测试类型"""
    INTEGRATION = "integration"
    END_TO_END = "end_to_end"
    PERFORMANCE = "performance"
    LOAD = "load"
    STRESS = "stress"


@dataclass
class TestResult:
    """单个测试结果"""
    name: str
    status: TestStatus
    test_type: TestType
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "type": self.test_type.value,
            "duration_ms": round(self.duration_ms, 2),
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    suite_name: str
    results: List[TestResult] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""

    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now().isoformat()

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status in (TestStatus.FAILED, TestStatus.ERROR))

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)

    @property
    def pass_rate(self) -> float:
        total = len([r for r in self.results if r.status != TestStatus.SKIPPED])
        if total == 0:
            return 0.0
        return self.passed_count / total * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "summary": {
                "total": len(self.results),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "pass_rate": round(self.pass_rate, 2),
                "total_duration_ms": round(self.total_duration_ms, 2),
            },
            "results": [r.to_dict() for r in self.results],
        }


class BaseTestCase(ABC):
    """测试用例基类"""

    def __init__(self, name: str, test_type: TestType):
        self.name = name
        self.test_type = test_type
        self.result: Optional[TestResult] = None

    @abstractmethod
    def run(self) -> TestResult:
        """执行测试"""
        pass

    def setup(self):
        """测试前置准备"""
        pass

    def teardown(self):
        """测试后置清理"""
        pass

    def execute(self) -> TestResult:
        """完整执行测试（含setup/teardown）"""
        start = time.perf_counter()
        try:
            self.setup()
            self.result = self.run()
            self.teardown()
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self.result = TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                test_type=self.test_type,
                duration_ms=duration,
                message=str(e),
                details={"traceback": traceback.format_exc()},
            )
        return self.result


class IntegrationTestCase(BaseTestCase):
    """集成测试用例"""

    def __init__(self, name: str, test_func: Callable[[], Any], expected: Any = None):
        super().__init__(name, TestType.INTEGRATION)
        self.test_func = test_func
        self.expected = expected

    def run(self) -> TestResult:
        start = time.perf_counter()
        try:
            actual = self.test_func()
            duration = (time.perf_counter() - start) * 1000

            if self.expected is not None and actual != self.expected:
                return TestResult(
                    name=self.name,
                    status=TestStatus.FAILED,
                    test_type=self.test_type,
                    duration_ms=duration,
                    message=f"期望值 {self.expected}，实际值 {actual}",
                    details={"expected": str(self.expected), "actual": str(actual)},
                )

            return TestResult(
                name=self.name,
                status=TestStatus.PASSED,
                test_type=self.test_type,
                duration_ms=duration,
                message="集成测试通过",
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                test_type=self.test_type,
                duration_ms=duration,
                message=str(e),
                details={"traceback": traceback.format_exc()},
            )


class EndToEndTestCase(BaseTestCase):
    """端到端测试用例"""

    def __init__(self, name: str, steps: List[Callable[[], Any]], validators: List[Callable[[Any], bool]]):
        super().__init__(name, TestType.END_TO_END)
        self.steps = steps
        self.validators = validators

    def run(self) -> TestResult:
        start = time.perf_counter()
        step_results = []

        try:
            for i, step in enumerate(self.steps):
                step_result = step()
                step_results.append({"step": i, "result": str(step_result)})

            for i, validator in enumerate(self.validators):
                if not validator(step_results):
                    duration = (time.perf_counter() - start) * 1000
                    return TestResult(
                        name=self.name,
                        status=TestStatus.FAILED,
                        test_type=self.test_type,
                        duration_ms=duration,
                        message=f"端到端验证步骤 {i} 失败",
                        details={"step_results": step_results},
                    )

            duration = (time.perf_counter() - start) * 1000
            return TestResult(
                name=self.name,
                status=TestStatus.PASSED,
                test_type=self.test_type,
                duration_ms=duration,
                message="端到端测试通过",
                details={"step_results": step_results},
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return TestResult(
                name=self.name,
                status=TestStatus.ERROR,
                test_type=self.test_type,
                duration_ms=duration,
                message=str(e),
                details={"traceback": traceback.format_exc(), "step_results": step_results},
            )


class PerformanceTestCase(BaseTestCase):
    """性能测试用例"""

    def __init__(self, name: str, test_func: Callable[[], Any],
                 max_duration_ms: float = 1000.0, iterations: int = 10):
        super().__init__(name, TestType.PERFORMANCE)
        self.test_func = test_func
        self.max_duration_ms = max_duration_ms
        self.iterations = iterations

    def run(self) -> TestResult:
        durations = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            try:
                self.test_func()
            except Exception as e:
                return TestResult(
                    name=self.name,
                    status=TestStatus.ERROR,
                    test_type=self.test_type,
                    duration_ms=0,
                    message=f"性能测试执行异常: {e}",
                )
            durations.append((time.perf_counter() - start) * 1000)

        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        p95 = sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else max_duration

        status = TestStatus.PASSED if avg_duration <= self.max_duration_ms else TestStatus.FAILED
        message = f"平均 {avg_duration:.2f}ms (目标 {self.max_duration_ms}ms)"

        return TestResult(
            name=self.name,
            status=status,
            test_type=self.test_type,
            duration_ms=avg_duration,
            message=message,
            details={
                "iterations": self.iterations,
                "min_ms": round(min_duration, 2),
                "max_ms": round(max_duration, 2),
                "avg_ms": round(avg_duration, 2),
                "p95_ms": round(p95, 2),
                "all_durations": [round(d, 2) for d in durations],
            },
        )


class LoadTestCase(BaseTestCase):
    """负载测试用例"""

    def __init__(self, name: str, test_func: Callable[[], Any],
                 concurrent: int = 10, duration_seconds: int = 5):
        super().__init__(name, TestType.LOAD)
        self.test_func = test_func
        self.concurrent = concurrent
        self.duration_seconds = duration_seconds

    def run(self) -> TestResult:
        import threading
        results = {"success": 0, "failed": 0, "total": 0}
        stop_flag = threading.Event()
        lock = threading.Lock()

        def worker():
            while not stop_flag.is_set():
                try:
                    self.test_func()
                    with lock:
                        results["success"] += 1
                        results["total"] += 1
                except Exception:
                    with lock:
                        results["failed"] += 1
                        results["total"] += 1

        threads = [threading.Thread(target=worker) for _ in range(self.concurrent)]
        start = time.perf_counter()
        for t in threads:
            t.start()

        time.sleep(self.duration_seconds)
        stop_flag.set()
        for t in threads:
            t.join()

        total_duration = (time.perf_counter() - start) * 1000
        throughput = results["total"] / self.duration_seconds if self.duration_seconds > 0 else 0

        return TestResult(
            name=self.name,
            status=TestStatus.PASSED,
            test_type=self.test_type,
            duration_ms=total_duration,
            message=f"吞吐量 {throughput:.2f} req/s",
            details={
                "concurrent": self.concurrent,
                "duration_seconds": self.duration_seconds,
                "total_requests": results["total"],
                "success": results["success"],
                "failed": results["failed"],
                "throughput": round(throughput, 2),
            },
        )


class TestSuite:
    """测试套件"""

    def __init__(self, name: str):
        self.name = name
        self.cases: List[BaseTestCase] = []
        self.result = TestSuiteResult(suite_name=name)

    def add_case(self, case: BaseTestCase):
        """添加测试用例"""
        self.cases.append(case)

    def run(self) -> TestSuiteResult:
        """执行所有测试用例"""
        logger.info(f"测试套件开始: {self.name} ({len(self.cases)} 用例)")
        self.result.start_time = datetime.now().isoformat()

        for case in self.cases:
            logger.info(f"执行测试: {case.name}")
            result = case.execute()
            self.result.results.append(result)
            logger.info(f"测试完成: {case.name} -> {result.status.value}")

        self.result.end_time = datetime.now().isoformat()
        logger.info(f"测试套件完成: {self.name} (通过率 {self.result.pass_rate:.1f}%)")
        return self.result

    def run_filtered(self, test_type: Optional[TestType] = None) -> TestSuiteResult:
        """按类型过滤执行"""
        filtered = self.cases
        if test_type:
            filtered = [c for c in self.cases if c.test_type == test_type]

        self.result = TestSuiteResult(suite_name=self.name)
        self.result.start_time = datetime.now().isoformat()
        for case in filtered:
            result = case.execute()
            self.result.results.append(result)
        self.result.end_time = datetime.now().isoformat()
        return self.result


class TestReportGenerator:
    """测试报告生成器"""

    def __init__(self):
        self.reports: List[TestSuiteResult] = []

    def add_suite_result(self, result: TestSuiteResult):
        """添加套件结果"""
        self.reports.append(result)

    def generate_markdown(self) -> str:
        """生成Markdown报告"""
        lines = ["# 系统测试报告\n"]
        lines.append(f"生成时间: {datetime.now().isoformat()}\n")

        total_cases = sum(len(r.results) for r in self.reports)
        total_passed = sum(r.passed_count for r in self.reports)
        total_failed = sum(r.failed_count for r in self.reports)

        lines.append("## 汇总\n")
        lines.append(f"- 总用例数: {total_cases}\n")
        lines.append(f"- 通过: {total_passed}\n")
        lines.append(f"- 失败: {total_failed}\n")
        lines.append(f"- 通过率: {total_passed / max(total_cases, 1) * 100:.1f}%\n")
        lines.append("")

        for suite in self.reports:
            lines.append(f"## {suite.suite_name}\n")
            lines.append(f"- 通过: {suite.passed_count}/{len(suite.results)}\n")
            lines.append(f"- 耗时: {suite.total_duration_ms:.2f}ms\n")
            lines.append("")
            lines.append("| 用例 | 类型 | 状态 | 耗时(ms) | 消息 |\n")
            lines.append("|------|------|------|----------|------|\n")
            for r in suite.results:
                lines.append(f"| {r.name} | {r.test_type.value} | {r.status.value} | {r.duration_ms:.2f} | {r.message[:30]}... |\n")
            lines.append("")

        return "\n".join(lines)

    def generate_json(self) -> str:
        """生成JSON报告"""
        return json.dumps(
            {"suites": [r.to_dict() for r in self.reports]},
            ensure_ascii=False,
            indent=2,
        )

    def save(self, output_dir: Union[str, Path]):
        """保存报告到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        md_path = output_dir / "test_report.md"
        md_path.write_text(self.generate_markdown(), encoding="utf-8")

        json_path = output_dir / "test_report.json"
        json_path.write_text(self.generate_json(), encoding="utf-8")

        logger.info(f"测试报告已保存: {output_dir}")
        return {"markdown": md_path, "json": json_path}


class SystemTestFramework:
    """系统测试框架 - 主类"""

    def __init__(self):
        self.suites: Dict[str, TestSuite] = {}
        self.report_generator = TestReportGenerator()
        logger.info("系统测试框架初始化完成")

    def create_suite(self, name: str) -> TestSuite:
        """创建测试套件"""
        suite = TestSuite(name)
        self.suites[name] = suite
        return suite

    def run_all(self) -> Dict[str, TestSuiteResult]:
        """运行所有测试套件"""
        results = {}
        for name, suite in self.suites.items():
            result = suite.run()
            results[name] = result
            self.report_generator.add_suite_result(result)
        return results

    def run_suite(self, name: str) -> Optional[TestSuiteResult]:
        """运行指定测试套件"""
        suite = self.suites.get(name)
        if not suite:
            logger.warning(f"测试套件不存在: {name}")
            return None
        result = suite.run()
        self.report_generator.add_suite_result(result)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        total_cases = sum(len(s.cases) for s in self.suites.values())
        return {
            "suite_count": len(self.suites),
            "total_cases": total_cases,
            "suite_names": list(self.suites.keys()),
        }

    def generate_report(self, output_dir: Union[str, Path] = ".") -> Dict[str, Path]:
        """生成测试报告"""
        return self.report_generator.save(output_dir)
