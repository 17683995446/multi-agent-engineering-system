"""
阶段98验证脚本：系统诊断模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.system_diagnostic import (
    ConfigCheck,
    DependencyCheck,
    DiagnosticCategory,
    DiagnosticCheck,
    DiagnosticItem,
    DiagnosticLevel,
    DiagnosticReport,
    DiskSpaceCheck,
    LogCheck,
    MemoryCheck,
    SystemDiagnostic,
    SystemInfoCheck,
)


def test_diagnostic_item():
    """测试诊断项"""
    item = DiagnosticItem(
        category=DiagnosticCategory.SYSTEM,
        level=DiagnosticLevel.INFO,
        title="测试",
        message="测试消息",
        suggestion="测试建议",
    )
    assert item.title == "测试"
    d = item.to_dict()
    assert d["level"] == "info"
    print("✓ 诊断项测试通过")


def test_diagnostic_report():
    """测试诊断报告"""
    report = DiagnosticReport(generated_at=__import__("datetime").datetime.now())
    report.add_item(
        DiagnosticItem(
            category=DiagnosticCategory.SYSTEM,
            level=DiagnosticLevel.INFO,
            title="t1",
            message="m1",
        )
    )
    report.add_item(
        DiagnosticItem(
            category=DiagnosticCategory.DISK,
            level=DiagnosticLevel.WARNING,
            title="t2",
            message="m2",
        )
    )
    assert report.summary.get("info", 0) == 1
    assert report.summary.get("warning", 0) == 1
    assert report.has_issues() is False
    report.add_item(
        DiagnosticItem(
            category=DiagnosticCategory.SYSTEM,
            level=DiagnosticLevel.ERROR,
            title="t3",
            message="m3",
        )
    )
    assert report.has_issues() is True
    print("✓ 诊断报告测试通过")


def test_system_info_check():
    """测试系统信息检查"""
    check = SystemInfoCheck()
    items = check.check()
    assert len(items) >= 2
    assert any(item.title == "操作系统" for item in items)
    print("✓ 系统信息检查测试通过")


def test_disk_space_check():
    """测试磁盘空间检查"""
    check = DiskSpaceCheck(threshold_percent=99.0, min_free_gb=0.01)
    items = check.check()
    assert len(items) == 1
    assert items[0].category == DiagnosticCategory.DISK
    print("✓ 磁盘空间检查测试通过")


def test_memory_check():
    """测试内存检查"""
    check = MemoryCheck()
    items = check.check()
    assert len(items) == 1
    assert items[0].category == DiagnosticCategory.MEMORY
    print("✓ 内存检查测试通过")


def test_config_check():
    """测试配置检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "configs"
        config_dir.mkdir()
        (config_dir / "test.yaml").write_text("test: true")
        check = ConfigCheck(config_dir=config_dir)
        items = check.check()
        assert len(items) == 1
        assert items[0].level == DiagnosticLevel.INFO
    print("✓ 配置检查测试通过")


def test_dependency_check():
    """测试依赖检查"""
    check = DependencyCheck()
    items = check.check()
    assert len(items) >= 1
    print("✓ 依赖检查测试通过")


def test_log_check():
    """测试日志检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()
        (log_dir / "app.log").write_text("log")
        check = LogCheck(log_dir=log_dir)
        items = check.check()
        assert len(items) == 1
        assert items[0].level == DiagnosticLevel.INFO
    print("✓ 日志检查测试通过")


def test_system_diagnostic():
    """测试系统诊断主类"""
    diagnostic = SystemDiagnostic()
    report = diagnostic.run_diagnosis()
    assert isinstance(report, DiagnosticReport)
    assert len(report.items) > 0
    text = diagnostic.generate_report_text(report)
    assert "系统诊断报告" in text
    suggestions = diagnostic.get_repair_suggestions(report)
    assert isinstance(suggestions, list)
    print("✓ 系统诊断主类测试通过")


def test_custom_check():
    """测试自定义检查"""
    class CustomCheck(DiagnosticCheck):
        def get_name(self):
            return "custom"

        def check(self):
            return [
                DiagnosticItem(
                    category=DiagnosticCategory.SYSTEM,
                    level=DiagnosticLevel.INFO,
                    title="自定义检查",
                    message="通过",
                )
            ]

    diagnostic = SystemDiagnostic()
    diagnostic.add_check(CustomCheck())
    report = diagnostic.run_diagnosis()
    assert any(item.title == "自定义检查" for item in report.items)
    print("✓ 自定义检查测试通过")


def test_save_report():
    """测试保存报告"""
    with tempfile.TemporaryDirectory() as tmpdir:
        diagnostic = SystemDiagnostic()
        report = diagnostic.run_diagnosis()
        path = Path(tmpdir) / "report.json"
        diagnostic.save_report(report, path)
        assert path.exists()
        data = __import__("json").loads(path.read_text(encoding="utf-8"))
        assert "summary" in data
    print("✓ 保存报告测试通过")


def main():
    print("=" * 60)
    print("阶段98验证：系统诊断模块")
    print("=" * 60)

    test_diagnostic_item()
    test_diagnostic_report()
    test_system_info_check()
    test_disk_space_check()
    test_memory_check()
    test_config_check()
    test_dependency_check()
    test_log_check()
    test_system_diagnostic()
    test_custom_check()
    test_save_report()

    print("=" * 60)
    print("阶段98验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
