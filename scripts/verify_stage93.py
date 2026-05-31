"""
阶段93验证脚本：系统测试框架模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.system_test import (
    BaseTestCase,
    EndToEndTestCase,
    IntegrationTestCase,
    LoadTestCase,
    PerformanceTestCase,
    SystemTestFramework,
    TestReportGenerator,
    TestStatus,
    TestSuite,
    TestType,
)


def test_integration_test_pass():
    """测试集成测试通过场景"""
    case = IntegrationTestCase("add_test", lambda: 2 + 2, expected=4)
    result = case.execute()
    assert result.status == TestStatus.PASSED
    assert result.test_type == TestType.INTEGRATION
    assert result.duration_ms >= 0
    print("✓ 集成测试通过场景测试通过")


def test_integration_test_fail():
    """测试集成测试失败场景"""
    case = IntegrationTestCase("fail_test", lambda: 2 + 2, expected=5)
    result = case.execute()
    assert result.status == TestStatus.FAILED
    assert "期望值 5" in result.message
    print("✓ 集成测试失败场景测试通过")


def test_end_to_end_test():
    """测试端到端测试"""
    counter = {"value": 0}

    def step1():
        counter["value"] += 1
        return counter["value"]

    def step2():
        counter["value"] *= 2
        return counter["value"]

    case = EndToEndTestCase(
        "e2e_flow",
        steps=[step1, step2],
        validators=[lambda results: counter["value"] == 2],
    )
    result = case.execute()
    assert result.status == TestStatus.PASSED
    assert result.test_type == TestType.END_TO_END
    print("✓ 端到端测试测试通过")


def test_performance_test():
    """测试性能测试"""
    def fast_op():
        return sum(range(100))

    case = PerformanceTestCase("perf_sum", fast_op, max_duration_ms=1000.0, iterations=5)
    result = case.execute()
    assert result.status == TestStatus.PASSED
    assert "avg_ms" in result.details
    assert result.details["iterations"] == 5
    print("✓ 性能测试测试通过")


def test_performance_test_fail():
    """测试性能测试超时失败"""
    def slow_op():
        import time
        time.sleep(0.05)

    case = PerformanceTestCase("perf_slow", slow_op, max_duration_ms=1.0, iterations=3)
    result = case.execute()
    assert result.status == TestStatus.FAILED
    print("✓ 性能测试超时失败测试通过")


def test_load_test():
    """测试负载测试"""
    call_count = {"n": 0}

    def quick_op():
        call_count["n"] += 1

    case = LoadTestCase("load_quick", quick_op, concurrent=3, duration_seconds=1)
    result = case.execute()
    assert result.status == TestStatus.PASSED
    assert result.details["total_requests"] > 0
    assert result.details["throughput"] > 0
    print("✓ 负载测试测试通过")


def test_test_suite():
    """测试测试套件"""
    suite = TestSuite("demo_suite")
    suite.add_case(IntegrationTestCase("t1", lambda: 1, expected=1))
    suite.add_case(IntegrationTestCase("t2", lambda: 2, expected=2))

    result = suite.run()
    assert result.passed_count == 2
    assert result.failed_count == 0
    assert result.pass_rate == 100.0
    print("✓ 测试套件测试通过")


def test_filtered_run():
    """测试按类型过滤执行"""
    suite = TestSuite("filter_suite")
    suite.add_case(IntegrationTestCase("int", lambda: 1, expected=1))
    suite.add_case(PerformanceTestCase("perf", lambda: None, max_duration_ms=1000, iterations=2))

    result = suite.run_filtered(test_type=TestType.INTEGRATION)
    assert len(result.results) == 1
    assert result.results[0].name == "int"
    print("✓ 过滤执行测试通过")


def test_report_generator():
    """测试报告生成器"""
    suite = TestSuite("report_suite")
    suite.add_case(IntegrationTestCase("r1", lambda: 1, expected=1))
    result = suite.run()

    gen = TestReportGenerator()
    gen.add_suite_result(result)

    md = gen.generate_markdown()
    assert "# 系统测试报告" in md
    assert "report_suite" in md

    json_str = gen.generate_json()
    assert "report_suite" in json_str

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = gen.save(tmpdir)
        assert paths["markdown"].exists()
        assert paths["json"].exists()
    print("✓ 报告生成器测试通过")


def test_system_test_framework():
    """测试系统测试框架主类"""
    framework = SystemTestFramework()
    suite = framework.create_suite("main_suite")
    suite.add_case(IntegrationTestCase("f1", lambda: 10, expected=10))
    suite.add_case(IntegrationTestCase("f2", lambda: 20, expected=20))

    results = framework.run_all()
    assert "main_suite" in results
    assert results["main_suite"].passed_count == 2

    summary = framework.get_summary()
    assert summary["suite_count"] == 1
    assert summary["total_cases"] == 2
    print("✓ 系统测试框架主类测试通过")


def main():
    print("=" * 60)
    print("阶段93验证：系统测试框架模块")
    print("=" * 60)

    test_integration_test_pass()
    test_integration_test_fail()
    test_end_to_end_test()
    test_performance_test()
    test_performance_test_fail()
    test_load_test()
    test_test_suite()
    test_filtered_run()
    test_report_generator()
    test_system_test_framework()

    print("=" * 60)
    print("阶段93验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
