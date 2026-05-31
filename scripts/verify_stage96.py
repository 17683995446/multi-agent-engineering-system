"""
阶段96验证脚本：系统清理工具模块
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.cleanup_tool import (
    CleanupResult,
    CleanupRule,
    CleanupScheduler,
    CleanupStrategy,
    CleanupTool,
    DiskSpaceManager,
    DiskUsage,
    LogArchiveTask,
    ResourceReleaseTask,
    TempFileCleanup,
)


def test_disk_usage():
    """测试磁盘使用数据类"""
    usage = DiskUsage(total=100 * 1024 ** 3, used=50 * 1024 ** 3, free=50 * 1024 ** 3, percent=50.0)
    assert usage.total_gb == 100.0
    assert usage.used_gb == 50.0
    assert usage.free_gb == 50.0
    print("✓ 磁盘使用数据类测试通过")


def test_disk_space_manager():
    """测试磁盘空间管理器"""
    mgr = DiskSpaceManager(threshold_percent=95.0, min_free_gb=0.1)
    usage = mgr.get_usage("/workspace")
    assert isinstance(usage, DiskUsage)
    assert usage.total > 0
    low = mgr.is_low_space("/workspace")
    assert isinstance(low, bool)
    recs = mgr.get_cleanup_recommendations("/workspace")
    assert isinstance(recs, list)
    print("✓ 磁盘空间管理器测试通过")


def test_temp_file_cleanup():
    """测试临时文件清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        old_file = tmp_path / "test.tmp"
        old_file.write_text("old temp file")
        old_time = time.time() - 7200
        os = __import__("os")
        os.utime(old_file, (old_time, old_time))

        task = TempFileCleanup(temp_dirs=[tmp_path], max_age_hours=1, patterns=["*.tmp"])
        result = task.execute()
        assert isinstance(result, CleanupResult)
        assert result.rule_name == "temp_file_cleanup"
        assert result.files_processed >= 1
        assert not old_file.exists()
    print("✓ 临时文件清理测试通过")


def test_log_archive_task():
    """测试日志归档任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        archive_dir = Path(tmpdir) / "archive"
        log_dir.mkdir()
        old_log = log_dir / "app.log"
        old_log.write_text("log content")
        os = __import__("os")
        old_time = time.time() - 10 * 86400
        os.utime(old_log, (old_time, old_time))

        task = LogArchiveTask(log_dir=log_dir, archive_dir=archive_dir, max_age_days=7)
        result = task.execute()
        assert isinstance(result, CleanupResult)
        assert result.files_processed >= 1
        assert not old_log.exists()
        assert any(archive_dir.iterdir())
    print("✓ 日志归档任务测试通过")


def test_resource_release_task():
    """测试资源释放任务"""
    released = []

    def releaser():
        released.append(True)

    task = ResourceReleaseTask()
    task.register(releaser)
    result = task.execute()
    assert result.files_processed == 1
    assert len(released) == 1
    print("✓ 资源释放任务测试通过")


def test_cleanup_scheduler():
    """测试清理调度器"""
    scheduler = CleanupScheduler()
    task = TempFileCleanup(max_age_hours=720)
    scheduler.add_task(task)
    assert len(scheduler.tasks) == 1
    results = scheduler.run_once()
    assert len(results) == 1
    assert isinstance(results[0], CleanupResult)
    print("✓ 清理调度器测试通过")


def test_cleanup_tool():
    """测试清理工具主类"""
    tool = CleanupTool()
    usage = tool.check_disk_space("/workspace")
    assert isinstance(usage, DiskUsage)
    report = tool.get_cleanup_report()
    assert "disk_usage" in report
    assert "recommendations" in report
    assert "low_space" in report
    print("✓ 清理工具主类测试通过")


def test_cleanup_rule():
    """测试清理规则"""
    rule = CleanupRule(
        name="test_rule",
        pattern="*.log",
        max_age_days=30,
        strategy=CleanupStrategy.ARCHIVE,
    )
    assert rule.name == "test_rule"
    assert rule.enabled is True
    print("✓ 清理规则测试通过")


def test_cleanup_result():
    """测试清理结果"""
    from datetime import datetime
    result = CleanupResult(rule_name="test", files_processed=5, bytes_reclaimed=1024)
    result.start_time = datetime.now()
    result.end_time = datetime.now()
    assert result.rule_name == "test"
    assert result.files_processed == 5
    assert result.duration_seconds >= 0.0
    print("✓ 清理结果测试通过")


def main():
    print("=" * 60)
    print("阶段96验证：系统清理工具模块")
    print("=" * 60)

    test_disk_usage()
    test_disk_space_manager()
    test_temp_file_cleanup()
    test_log_archive_task()
    test_resource_release_task()
    test_cleanup_scheduler()
    test_cleanup_tool()
    test_cleanup_rule()
    test_cleanup_result()

    print("=" * 60)
    print("阶段96验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
