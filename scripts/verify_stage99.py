"""
阶段99验证脚本：最终集成测试
功能：全系统集成测试、端到端测试、回归测试、性能基准测试
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.cleanup_tool import CleanupTool, DiskUsage
from common.backup_restore import BackupRestoreTool, BackupType, BackupStatus
from common.system_diagnostic import SystemDiagnostic, DiagnosticReport
from common.utils import setup_logger, GlobalConfig, PathManager, generate_trace_id


def test_end_to_end_cleanup_backup_diagnostic():
    """端到端测试：清理 -> 备份 -> 诊断"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "test.txt").write_text("integration test")

        cleanup = CleanupTool()
        usage = cleanup.check_disk_space("/workspace")
        assert isinstance(usage, DiskUsage)

        backup = BackupRestoreTool(backup_dir=tmp_path / "backups")
        record = backup.full_backup(data_dir, name="e2e_backup")
        assert record.status == BackupStatus.SUCCESS
        assert backup.verify_backup(record.id) is True

        diagnostic = SystemDiagnostic()
        report = diagnostic.run_diagnosis()
        assert isinstance(report, DiagnosticReport)
        assert len(report.items) > 0

    print("✓ 端到端测试通过")


def test_regression_common_modules():
    """回归测试：公共层核心模块"""
    from common.utils import setup_logger, GlobalConfig, StateManager, generate_trace_id
    from common.logging_enhanced import EnhancedLogger, LogFormat, LogLevel

    logger = setup_logger("regression_test")
    logger.info("regression test log")

    state = StateManager()
    state.set_task_state("key", "value")
    assert state.get_task_state("key") == "value"

    trace_id = generate_trace_id()
    assert len(trace_id) == 36

    with tempfile.TemporaryDirectory() as tmpdir:
        el = EnhancedLogger("regression", level=LogLevel.INFO, log_format=LogFormat.TEXT, log_dir=tmpdir)
        el.info("test")

    print("✓ 回归测试通过")


def test_performance_benchmark():
    """性能基准测试"""
    diagnostic = SystemDiagnostic()
    start = time.time()
    report = diagnostic.run_diagnosis()
    duration = time.time() - start
    assert duration < 5.0, f"诊断耗时过长: {duration:.2f}s"

    with tempfile.TemporaryDirectory() as tmpdir:
        backup = BackupRestoreTool(backup_dir=Path(tmpdir) / "backups")
        src = Path(tmpdir) / "src"
        src.mkdir()
        for i in range(10):
            (src / f"f{i}.txt").write_text("x" * 1024)
        start = time.time()
        record = backup.full_backup(src, name="perf")
        duration = time.time() - start
        assert duration < 5.0, f"备份耗时过长: {duration:.2f}s"

    cleanup = CleanupTool()
    start = time.time()
    result = cleanup.cleanup_temp_files(max_age_hours=720)
    duration = time.time() - start
    assert duration < 5.0, f"清理耗时过长: {duration:.2f}s"

    print(f"✓ 性能基准测试通过 (诊断/备份/清理均 < 5s)")


def test_all_stages_96_98_modules_import():
    """测试阶段96-98模块可导入"""
    from common.cleanup_tool import CleanupTool
    from common.backup_restore import BackupRestoreTool
    from common.system_diagnostic import SystemDiagnostic
    assert CleanupTool is not None
    assert BackupRestoreTool is not None
    assert SystemDiagnostic is not None
    print("✓ 模块导入测试通过")


def test_integration_report():
    """集成测试报告生成"""
    diagnostic = SystemDiagnostic()
    report = diagnostic.run_diagnosis()
    text = diagnostic.generate_report_text(report)
    assert "系统诊断报告" in text
    suggestions = diagnostic.get_repair_suggestions(report)
    assert isinstance(suggestions, list)
    print("✓ 集成报告生成测试通过")


def test_cross_module_data_flow():
    """跨模块数据流测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        src = tmp_path / "data"
        src.mkdir()
        (src / "a.txt").write_text("cross module")

        backup = BackupRestoreTool(backup_dir=tmp_path / "backups")
        record = backup.full_backup(src, name="cross")

        cleanup = CleanupTool()
        report = cleanup.get_cleanup_report()
        assert "disk_usage" in report

        diagnostic = SystemDiagnostic()
        diag_report = diagnostic.run_diagnosis()
        assert any(item.category.value == "system" for item in diag_report.items)

    print("✓ 跨模块数据流测试通过")


def main():
    print("=" * 60)
    print("阶段99验证：最终集成测试")
    print("=" * 60)

    test_end_to_end_cleanup_backup_diagnostic()
    test_regression_common_modules()
    test_performance_benchmark()
    test_all_stages_96_98_modules_import()
    test_integration_report()
    test_cross_module_data_flow()

    print("=" * 60)
    print("阶段99验证全部通过 ✓")
    print("=" * 60)
    print()
    print("集成测试总结:")
    print("  ✓ 端到端测试 (清理 -> 备份 -> 诊断)")
    print("  ✓ 回归测试 (公共层核心模块)")
    print("  ✓ 性能基准测试 (各模块 < 5s)")
    print("  ✓ 模块导入测试")
    print("  ✓ 集成报告生成")
    print("  ✓ 跨模块数据流")
    return 0


if __name__ == "__main__":
    sys.exit(main())
