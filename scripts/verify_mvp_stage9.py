"""
MVP阶段9验证脚本：代码审查Agent

测试内容：
1. 代码审查Agent初始化
2. 代码质量检查
3. 原子规范审查
4. 安全问题检测
5. 审查报告生成
"""

import sys
import os

# 将项目根目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.mvp_core.code_review_agent import (
    CodeReviewAgent,
    CodeReviewer,
    ReviewReport,
    ReviewIssue,
    ReviewCategory,
    SeverityLevel,
)
from src.mvp_core.agent_base import MessageBus, AgentStatus


def test_agent_initialization():
    """测试1: 代码审查Agent初始化"""
    print("=" * 60)
    print("测试1: 代码审查Agent初始化")
    print("=" * 60)

    # 无消息总线初始化
    agent = CodeReviewAgent(name="review_agent_1")
    assert agent.name == "review_agent_1"
    assert agent.reviewer is not None
    assert isinstance(agent.reviewer, CodeReviewer)
    print("  ✓ 无消息总线初始化成功")

    # 有消息总线初始化
    bus = MessageBus(name="test_bus")
    agent2 = CodeReviewAgent(name="review_agent_2", message_bus=bus)
    assert agent2.message_bus == bus
    print("  ✓ 有消息总线初始化成功")

    # 初始化方法
    result = agent.initialize()
    assert result is True
    assert agent.status == AgentStatus.IDLE
    print("  ✓ initialize() 返回True，状态为IDLE")

    # 关闭方法
    result = agent.shutdown()
    assert result is True
    assert agent.status == AgentStatus.STOPPED
    print("  ✓ shutdown() 返回True，状态为STOPPED")

    print("\n[通过] 测试1: 代码审查Agent初始化\n")
    return True


def test_code_quality_check():
    """测试2: 代码质量检查"""
    print("=" * 60)
    print("测试2: 代码质量检查")
    print("=" * 60)

    reviewer = CodeReviewer()

    # 测试空方法检测
    source_empty = '''
class Foo:
    """doc"""
    def bar(self):
        """empty"""
        pass
'''
    report = reviewer.review(source_empty, target_name="empty_test")
    empty_issues = [i for i in report.issues if i.rule_id == "EMPTY_BODY"]
    assert len(empty_issues) >= 1, f"期望检测到空方法，实际: {empty_issues}"
    print("  ✓ 空方法检测正常")

    # 测试嵌套深度检测
    source_deep = '''
def deep_func():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        pass
'''
    report = reviewer.review(source_deep, target_name="deep_test")
    deep_issues = [i for i in report.issues if i.rule_id == "DEEP_NESTING"]
    assert len(deep_issues) >= 1, f"期望检测到过深嵌套，实际: {deep_issues}"
    print("  ✓ 嵌套深度检测正常")

    # 测试长行检测
    source_long = 'x = "' + "a" * 130 + '"\n'
    report = reviewer.review(source_long, target_name="long_line_test")
    long_issues = [i for i in report.issues if i.rule_id == "LONG_LINE"]
    assert len(long_issues) >= 1, f"期望检测到长行，实际: {long_issues}"
    print("  ✓ 长行检测正常")

    # 测试语法错误检测
    source_syntax = "def foo(\n"
    report = reviewer.review(source_syntax, target_name="syntax_test")
    syntax_issues = [i for i in report.issues if i.rule_id == "SYNTAX_ERROR"]
    assert len(syntax_issues) >= 1, f"期望检测到语法错误，实际: {syntax_issues}"
    print("  ✓ 语法错误检测正常")

    print("\n[通过] 测试2: 代码质量检查\n")
    return True


def test_atom_compliance():
    """测试3: 原子规范审查"""
    print("=" * 60)
    print("测试3: 原子规范审查")
    print("=" * 60)

    reviewer = CodeReviewer()

    # 测试变量命名规范
    source_var = '''
def func():
    BadName = 1
    temp = 2
'''
    report = reviewer.review(source_var, target_name="var_test")
    atom_issues = [i for i in report.issues if i.category == ReviewCategory.ATOM_COMPLIANCE]
    assert len(atom_issues) > 0, f"期望检测到原子规范问题，实际: {atom_issues}"
    print(f"  ✓ 变量命名规范检测正常，发现问题数: {len(atom_issues)}")

    # 测试方法行数限制
    source_long_method = "\n".join(["def long_method():"] + ["    x = 1"] * 40)
    report = reviewer.review(source_long_method, target_name="method_test")
    atom_issues = [i for i in report.issues if i.category == ReviewCategory.ATOM_COMPLIANCE]
    assert len(atom_issues) > 0, f"期望检测到方法过长，实际: {atom_issues}"
    print(f"  ✓ 方法行数限制检测正常，发现问题数: {len(atom_issues)}")

    # 测试类命名规范
    source_class = '''
class bad_class:
    pass
'''
    report = reviewer.review(source_class, target_name="class_test")
    atom_issues = [i for i in report.issues if i.category == ReviewCategory.ATOM_COMPLIANCE]
    assert len(atom_issues) > 0, f"期望检测到类命名问题，实际: {atom_issues}"
    print(f"  ✓ 类命名规范检测正常，发现问题数: {len(atom_issues)}")

    print("\n[通过] 测试3: 原子规范审查\n")
    return True


def test_security_detection():
    """测试4: 安全问题检测"""
    print("=" * 60)
    print("测试4: 安全问题检测")
    print("=" * 60)

    reviewer = CodeReviewer()

    # 测试危险函数
    source_danger = '''
result = eval(user_input)
'''
    report = reviewer.review(source_danger, target_name="danger_test")
    sec_issues = [i for i in report.issues if i.category == ReviewCategory.SECURITY]
    assert len(sec_issues) >= 1, f"期望检测到安全问题，实际: {sec_issues}"
    print(f"  ✓ 危险函数检测正常，发现问题数: {len(sec_issues)}")

    # 测试硬编码密码
    source_secret = 'password = "123456"\n'
    report = reviewer.review(source_secret, target_name="secret_test")
    sec_issues = [i for i in report.issues if i.rule_id == "HARDCODED_SECRET"]
    assert len(sec_issues) >= 1, f"期望检测到硬编码密码，实际: {sec_issues}"
    print(f"  ✓ 硬编码密码检测正常，发现问题数: {len(sec_issues)}")

    # 测试SQL注入风险
    source_sql = 'query = f"SELECT * FROM users WHERE id = {user_id}"\n'
    report = reviewer.review(source_sql, target_name="sql_test")
    sec_issues = [i for i in report.issues if i.rule_id == "SQL_INJECTION_RISK"]
    assert len(sec_issues) >= 1, f"期望检测到SQL注入风险，实际: {sec_issues}"
    print(f"  ✓ SQL注入风险检测正常，发现问题数: {len(sec_issues)}")

    print("\n[通过] 测试4: 安全问题检测\n")
    return True


def test_report_generation():
    """测试5: 审查报告生成"""
    print("=" * 60)
    print("测试5: 审查报告生成")
    print("=" * 60)

    agent = CodeReviewAgent(name="report_test_agent")
    agent.initialize()

    source = '''
def bad_func():
    password = "secret123"
    eval("1+1")
    x = 1
'''
    result = agent.execute({
        "source": source,
        "target_name": "report_test",
    })

    assert result["success"] is True, f"执行失败: {result.get('error')}"
    report_dict = result["report"]
    assert report_dict is not None
    print("  ✓ execute() 返回报告字典")

    # 验证报告结构
    assert "target" in report_dict
    assert "summary" in report_dict
    assert "metrics" in report_dict
    assert "issues" in report_dict
    assert "timestamp" in report_dict
    print("  ✓ 报告结构完整")

    # 验证摘要统计
    summary = report_dict["summary"]
    assert summary["total_issues"] > 0
    assert not summary["pass"]  # 有问题，不应通过
    print(f"  ✓ 摘要统计正确，总问题数: {summary['total_issues']}")

    # 验证分类统计
    for cat in ["code_quality", "atom_compliance", "security", "performance", "best_practice"]:
        assert cat in summary["by_category"]
    print("  ✓ 分类统计完整")

    # 验证严重程度统计
    for sev in ["critical", "high", "medium", "low", "info"]:
        assert sev in summary["by_severity"]
    print("  ✓ 严重程度统计完整")

    # 验证Agent状态
    status = agent.get_status()
    assert status["review_count"] == 1
    assert status["latest_target"] == "report_test"
    print("  ✓ Agent状态更新正确")

    # 验证get_latest_report
    latest = agent.get_latest_report()
    assert latest is not None
    assert isinstance(latest, ReviewReport)
    print("  ✓ get_latest_report() 返回ReviewReport")

    # 验证to_dict
    report_dict2 = latest.to_dict()
    assert report_dict2["target"] == "report_test"
    print("  ✓ ReviewReport.to_dict() 正常")

    agent.shutdown()

    print("\n[通过] 测试5: 审查报告生成\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MVP阶段9验证: 代码审查Agent")
    print("=" * 60 + "\n")

    tests = [
        test_agent_initialization,
        test_code_quality_check,
        test_atom_compliance,
        test_security_detection,
        test_report_generation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            failed += 1
            print(f"\n[失败] {test.__name__}: {e}\n")
        except Exception as e:
            failed += 1
            print(f"\n[错误] {test.__name__}: {e}\n")

    print("=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")

    if failed == 0:
        print("\n✓ MVP阶段9验证全部通过！")
        return 0
    else:
        print("\n✗ MVP阶段9验证存在失败！")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
