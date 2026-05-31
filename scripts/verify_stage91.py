"""
阶段91验证脚本：代码质量检查模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.code_quality import (
    CodeQualityEngine,
    CodeSmell,
    ComplexityAnalyzer,
    ComplexityReport,
    QualityScorer,
    Severity,
    SmellDetector,
    SmellType,
    TechDebtEstimator,
)


def create_test_file(content: str) -> Path:
    """创建临时测试文件"""
    fd, path = tempfile.mkstemp(suffix=".py")
    with open(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return Path(path)


def test_complexity_analyzer():
    """测试复杂度分析器"""
    source = '''
def simple():
    return 1

def complex_func(x):
    if x > 0:
        if x > 10:
            return x * 2
        elif x > 5:
            return x + 1
        else:
            return x
    elif x < 0:
        return -x
    else:
        return 0
'''
    test_file = create_test_file(source)
    analyzer = ComplexityAnalyzer()
    report = analyzer.analyze_file(test_file)

    assert report.lines_of_code > 0
    assert report.function_count == 2
    assert report.max_function_complexity > 1
    assert report.max_function_name in ("simple", "complex_func")
    print("✓ 复杂度分析器测试通过")
    test_file.unlink()


def test_smell_detector_long_method():
    """检测过长函数"""
    lines = ["    pass"] * 60
    source = f"def long_func():\n" + "\n".join(lines)
    test_file = create_test_file(source)
    detector = SmellDetector()
    smells = detector.detect_file(test_file)

    long_methods = [s for s in smells if s.smell_type == SmellType.LONG_METHOD]
    assert len(long_methods) >= 1
    assert long_methods[0].severity == Severity.HIGH
    print("✓ 过长函数检测测试通过")
    test_file.unlink()


def test_smell_detector_too_many_params():
    """检测过多参数"""
    source = "def many_args(a, b, c, d, e, f, g):\n    pass\n"
    test_file = create_test_file(source)
    detector = SmellDetector()
    smells = detector.detect_file(test_file)

    param_smells = [s for s in smells if s.smell_type == SmellType.TOO_MANY_PARAMETERS]
    assert len(param_smells) >= 1
    print("✓ 过多参数检测测试通过")
    test_file.unlink()


def test_smell_detector_deep_nesting():
    """检测深层嵌套"""
    source = '''
def nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        pass
'''
    test_file = create_test_file(source)
    detector = SmellDetector()
    smells = detector.detect_file(test_file)

    nest_smells = [s for s in smells if s.smell_type == SmellType.DEEP_NESTING]
    assert len(nest_smells) >= 1
    print("✓ 深层嵌套检测测试通过")
    test_file.unlink()


def test_tech_debt_estimator():
    """测试技术债务评估"""
    smells = [
        CodeSmell(SmellType.LONG_METHOD, Severity.HIGH, "a.py", 1, "msg"),
        CodeSmell(SmellType.DUPLICATE_CODE, Severity.MEDIUM, "b.py", 2, "msg"),
    ]
    estimator = TechDebtEstimator()
    debts = estimator.estimate(smells)

    assert len(debts) == 2
    assert debts[0].estimated_hours > 0
    summary = estimator.summarize(debts)
    assert summary["total_items"] == 2
    assert summary["total_estimated_hours"] > 0
    print("✓ 技术债务评估测试通过")


def test_quality_scorer():
    """测试质量评分"""
    reports = [
        ComplexityReport("a.py", 5, 3, 100, 2, 1),
        ComplexityReport("b.py", 8, 5, 150, 3, 1),
    ]
    smells = [
        CodeSmell(SmellType.LONG_METHOD, Severity.HIGH, "a.py", 1, "msg"),
    ]
    scorer = QualityScorer()
    score = scorer.score(reports, smells)

    assert 0 <= score.overall <= 100
    assert 0 <= score.maintainability <= 100
    assert 0 <= score.reliability <= 100
    assert len(score.smells) == 1
    print("✓ 质量评分测试通过")


def test_code_quality_engine():
    """测试代码质量引擎"""
    source = '''
def simple():
    return 1

def another():
    return 2
'''
    test_file = create_test_file(source)
    engine = CodeQualityEngine()
    result = engine.analyze(test_file)

    assert "target" in result
    assert "complexity" in result
    assert "quality_score" in result
    assert result["quality_score"]["overall"] >= 0
    summary = engine.get_summary(result)
    assert "综合评分" in summary
    print("✓ 代码质量引擎测试通过")
    test_file.unlink()


def test_directory_analysis():
    """测试目录分析"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "mod1.py").write_text("def f1():\n    return 1\n", encoding="utf-8")
        (tmpdir / "mod2.py").write_text("def f2():\n    return 2\n", encoding="utf-8")

        engine = CodeQualityEngine()
        result = engine.analyze(tmpdir)

        assert len(result["complexity"]) >= 2
        print("✓ 目录分析测试通过")


def main():
    print("=" * 60)
    print("阶段91验证：代码质量检查模块")
    print("=" * 60)

    test_complexity_analyzer()
    test_smell_detector_long_method()
    test_smell_detector_too_many_params()
    test_smell_detector_deep_nesting()
    test_tech_debt_estimator()
    test_quality_scorer()
    test_code_quality_engine()
    test_directory_analysis()

    print("=" * 60)
    print("阶段91验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
