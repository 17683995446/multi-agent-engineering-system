"""
MVP阶段7验证脚本：测试Agent
验证内容：
1. 测试Agent初始化
2. 测试用例生成
3. 测试执行
4. 测试报告
5. 覆盖率分析
"""

import os
import sys
import tempfile
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mvp_core.testing_agent import (
    TestingAgent,
    TestCaseGenerator,
    TestRunner,
    TestCase,
    TestReport,
)
from src.mvp_core.agent_base import AgentStatus, MessageBus


def verify_testing_agent_initialization():
    """验证1: 测试Agent初始化"""
    print("=" * 60)
    print("验证1: 测试Agent初始化")
    print("=" * 60)

    # 无消息总线初始化
    agent = TestingAgent(name="test_agent_1")
    assert agent.name == "test_agent_1"
    assert agent.status == AgentStatus.IDLE
    assert agent.generator is not None
    assert agent.runner is not None
    print("  ✓ 基本初始化通过")

    # 带消息总线初始化
    bus = MessageBus(name="test_bus")
    agent2 = TestingAgent(name="test_agent_2", message_bus=bus, working_dir=str(project_root))
    assert agent2.message_bus == bus
    assert agent2.runner.working_dir == str(project_root)
    print("  ✓ 带消息总线初始化通过")

    # initialize / shutdown
    assert agent.initialize() is True
    assert agent.status == AgentStatus.IDLE
    assert agent._running is True
    print("  ✓ initialize() 通过")

    assert agent.shutdown() is True
    assert agent.status == AgentStatus.STOPPED
    assert agent._running is False
    print("  ✓ shutdown() 通过")

    print("  [通过] 测试Agent初始化验证成功\n")


def verify_test_case_generation():
    """验证2: 测试用例生成"""
    print("=" * 60)
    print("验证2: 测试用例生成")
    print("=" * 60)

    # 创建临时目标文件
    target_code = '''
def add(a: int, b: int) -> int:
    """加法函数"""
    return a + b

def greet(name: str) -> str:
    """问候函数"""
    return f"Hello, {name}"
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(target_code)
        temp_path = f.name

    try:
        agent = TestingAgent(name="gen_agent")

        # 为指定函数生成测试
        result = agent.execute({
            "action": "generate",
            "file_path": temp_path,
            "target_function": "add",
        })
        assert result["success"] is True
        assert result["count"] > 0
        cases = result["cases"]
        assert all(isinstance(c, TestCase) for c in cases)
        assert any(c.test_type == "unit" for c in cases)
        assert any(c.test_type == "boundary" for c in cases)
        assert any(c.test_type == "exception" for c in cases)
        print(f"  ✓ 为 add 生成 {result['count']} 个测试用例")

        # 为整个文件生成测试
        result2 = agent.execute({
            "action": "generate",
            "file_path": temp_path,
        })
        assert result2["success"] is True
        assert result2["count"] > 0
        print(f"  ✓ 为整个文件生成 {result2['count']} 个测试用例")

        # 边界值测试生成
        result3 = agent.execute({
            "action": "generate_boundary",
            "file_path": temp_path,
            "target_function": "add",
        })
        assert result3["success"] is True
        assert all(c.test_type == "boundary" for c in result3["cases"])
        print(f"  ✓ 边界值测试生成 {result3['count']} 个")

        # 异常测试生成
        result4 = agent.execute({
            "action": "generate_exception",
            "file_path": temp_path,
            "target_function": "add",
        })
        assert result4["success"] is True
        assert all(c.test_type == "exception" for c in result4["cases"])
        print(f"  ✓ 异常测试生成 {result4['count']} 个")

        # 独立TestCaseGenerator验证
        gen = TestCaseGenerator()
        cases = gen.generate_for_function("greet", target_code, module_name="temp_module")
        assert len(cases) > 0
        assert cases[0].target_function == "greet"
        print("  ✓ TestCaseGenerator 独立工作正常")

    finally:
        os.unlink(temp_path)

    print("  [通过] 测试用例生成验证成功\n")


def verify_test_execution():
    """验证3: 测试执行"""
    print("=" * 60)
    print("验证3: 测试执行")
    print("=" * 60)

    # 创建临时测试文件
    test_code = '''
def test_always_pass():
    assert 1 + 1 == 2

def test_another_pass():
    assert "hello".upper() == "HELLO"
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False, encoding="utf-8") as f:
        f.write(test_code)
        temp_test_path = f.name

    try:
        agent = TestingAgent(name="run_agent")

        # 执行测试
        result = agent.execute({
            "action": "run",
            "test_path": temp_test_path,
        })
        assert result["success"] is True
        report = result["report"]
        assert isinstance(report, TestReport)
        assert report.passed >= 2
        print(f"  ✓ 测试执行通过: {report.passed}/{report.total}")

        # 独立TestRunner验证
        runner = TestRunner()
        report2 = runner.run_tests(temp_test_path)
        assert report2.passed >= 2
        print("  ✓ TestRunner 独立执行正常")

        # 测试不存在的路径
        report3 = runner.run_tests("/nonexistent/path/test.py")
        assert report3.error > 0
        print("  ✓ 错误路径处理正常")

    finally:
        os.unlink(temp_test_path)

    print("  [通过] 测试执行验证成功\n")


def verify_test_report():
    """验证4: 测试报告"""
    print("=" * 60)
    print("验证4: 测试报告")
    print("=" * 60)

    agent = TestingAgent(name="report_agent")

    # 构造一个模拟报告
    from src.mvp_core.testing_agent import TestResult
    report = TestReport(
        total=5,
        passed=3,
        failed=1,
        error=1,
        skipped=0,
        duration=0.45,
    )
    report.results = [
        TestResult(test_name="test_a", status="passed"),
        TestResult(test_name="test_b", status="passed"),
        TestResult(test_name="test_c", status="passed"),
        TestResult(test_name="test_d", status="failed", message="assertion error"),
        TestResult(test_name="test_e", status="error", message="setup error"),
    ]

    # 生成报告文本
    text = agent.runner.generate_report(report)
    assert "测试报告" in text
    assert "总用例数: 5" in text
    assert "通过: 3" in text
    assert "失败: 1" in text
    assert "错误: 1" in text
    print("  ✓ 报告文本生成正确")

    # 通过execute生成报告
    result = agent.execute({
        "action": "report",
        "report": report,
    })
    assert result["success"] is True
    assert "测试报告" in result["text"]
    print("  ✓ execute(report) 正常")

    # 报告字典转换
    d = report.to_dict()
    assert d["total"] == 5
    assert d["passed"] == 3
    assert "timestamp" in d
    print("  ✓ 报告字典转换正常")

    print("  [通过] 测试报告验证成功\n")


def verify_coverage_analysis():
    """验证5: 覆盖率分析"""
    print("=" * 60)
    print("验证5: 覆盖率分析")
    print("=" * 60)

    # 创建临时源文件和测试文件
    src_code = '''
def calc(x: int, y: int) -> int:
    if x > 0:
        return x + y
    return y - x
'''
    test_code = '''
def test_calc_positive():
    from temp_cov_src import calc
    assert calc(1, 2) == 3
'''

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "temp_cov_src.py"
        src_path.write_text(src_code, encoding="utf-8")

        test_path = Path(tmpdir) / "test_temp_cov.py"
        test_path.write_text(test_code, encoding="utf-8")

        agent = TestingAgent(name="cov_agent", working_dir=tmpdir)

        # 执行带覆盖率的测试
        result = agent.execute({
            "action": "coverage",
            "test_path": str(test_path),
        })
        assert result["success"] is True
        coverage = result["coverage"]
        # 覆盖率数据结构检查
        assert isinstance(coverage, dict)
        print(f"  ✓ 覆盖率分析执行成功，数据结构: {list(coverage.keys())}")

        # 独立runner覆盖率
        runner = TestRunner(working_dir=tmpdir)
        report = runner.run_tests(str(test_path), coverage=True)
        assert report.coverage is not None
        print("  ✓ TestRunner 覆盖率分析正常")

    print("  [通过] 覆盖率分析验证成功\n")


def verify_save_tests():
    """验证6: 保存生成的测试到文件"""
    print("=" * 60)
    print("验证6: 保存测试文件")
    print("=" * 60)

    target_code = '''
def multiply(a: int, b: int) -> int:
    return a * b
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(target_code)
        temp_path = f.name

    try:
        agent = TestingAgent(name="save_agent")

        # 先生成测试
        agent.execute({
            "action": "generate",
            "file_path": temp_path,
            "target_function": "multiply",
        })

        # 保存到文件
        output_path = temp_path.replace(".py", "_test.py")
        result = agent.execute({
            "action": "save",
            "file_path": temp_path,
            "output_path": output_path,
        })
        assert result["success"] is True
        assert Path(result["path"]).exists()
        content = Path(result["path"]).read_text(encoding="utf-8")
        assert "test_multiply_basic" in content
        print(f"  ✓ 测试文件已保存: {result['path']}")

        os.unlink(output_path)
    finally:
        os.unlink(temp_path)

    print("  [通过] 保存测试文件验证成功\n")


def main():
    print("\n" + "=" * 60)
    print("MVP阶段7验证: 测试Agent")
    print("=" * 60 + "\n")

    verify_testing_agent_initialization()
    verify_test_case_generation()
    verify_test_execution()
    verify_test_report()
    verify_coverage_analysis()
    verify_save_tests()

    print("=" * 60)
    print("MVP阶段7验证结果: 全部通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
