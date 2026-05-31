"""
阶段97验证脚本：备份恢复模块
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.backup_restore import (
    BackupError,
    BackupManager,
    BackupRecord,
    BackupRestoreTool,
    BackupStatus,
    BackupType,
    BackupValidator,
    FullBackupStrategy,
    IncrementalBackupStrategy,
    RestoreResult,
)


def test_backup_record():
    """测试备份记录数据类"""
    record = BackupRecord(
        id="test1",
        source=Path("/tmp/src"),
        destination=Path("/tmp/dst"),
        backup_type=BackupType.FULL,
        status=BackupStatus.SUCCESS,
        created_at=__import__("datetime").datetime.now(),
    )
    assert record.id == "test1"
    d = record.to_dict()
    assert d["id"] == "test1"
    print("✓ 备份记录数据类测试通过")


def test_full_backup_strategy():
    """测试全量备份策略"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        dst = Path(tmpdir) / "backup.tar.gz"
        record = BackupRecord(
            id="full1",
            source=src,
            destination=dst,
            backup_type=BackupType.FULL,
            status=BackupStatus.RUNNING,
            created_at=__import__("datetime").datetime.now(),
        )
        strategy = FullBackupStrategy()
        result = strategy.execute(src, dst, record)
        assert result.status == BackupStatus.SUCCESS
        assert dst.exists()
        assert result.checksum is not None
    print("✓ 全量备份策略测试通过")


def test_incremental_backup_strategy():
    """测试增量备份策略"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        dst = Path(tmpdir) / "inc.tar.gz"
        now = time.time()
        record = BackupRecord(
            id="inc1",
            source=src,
            destination=dst,
            backup_type=BackupType.INCREMENTAL,
            status=BackupStatus.RUNNING,
            created_at=__import__("datetime").datetime.now(),
        )
        strategy = IncrementalBackupStrategy(last_backup_time=now)
        result = strategy.execute(src, dst, record)
        assert result.status == BackupStatus.SUCCESS
        assert dst.exists()
    print("✓ 增量备份策略测试通过")


def test_backup_validator():
    """测试备份验证器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "source"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        dst = Path(tmpdir) / "backup.tar.gz"
        record = BackupRecord(
            id="val1",
            source=src,
            destination=dst,
            backup_type=BackupType.FULL,
            status=BackupStatus.RUNNING,
            created_at=__import__("datetime").datetime.now(),
        )
        FullBackupStrategy().execute(src, dst, record)
        validator = BackupValidator()
        assert validator.validate_checksum(record) is True
        assert validator.validate_integrity(record) is True
    print("✓ 备份验证器测试通过")


def test_backup_manager():
    """测试备份管理器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "data"
        src.mkdir()
        (src / "f1.txt").write_text("data1")
        backup_dir = Path(tmpdir) / "backups"
        mgr = BackupManager(backup_dir)
        record = mgr.backup(src, BackupType.FULL, name="bm_full")
        assert record.id == "bm_full"
        assert record.status == BackupStatus.SUCCESS
        assert len(mgr.list_backups()) == 1
        status = mgr.get_status()
        assert status["backup_count"] == 1
    print("✓ 备份管理器测试通过")


def test_restore():
    """测试数据恢复"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "data"
        src.mkdir()
        (src / "f1.txt").write_text("restore me")
        backup_dir = Path(tmpdir) / "backups"
        mgr = BackupManager(backup_dir)
        record = mgr.backup(src, BackupType.FULL, name="restore_test")
        target = Path(tmpdir) / "restored"
        result = mgr.restore(record.id, target)
        assert result.success is True
        assert result.files_restored > 0
        assert (target / "data" / "f1.txt").exists()
    print("✓ 数据恢复测试通过")


def test_delete_backup():
    """测试删除备份"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "data"
        src.mkdir()
        (src / "f1.txt").write_text("delete me")
        backup_dir = Path(tmpdir) / "backups"
        mgr = BackupManager(backup_dir)
        record = mgr.backup(src, BackupType.FULL, name="del_test")
        assert record.destination.exists()
        ok = mgr.delete_backup(record.id)
        assert ok is True
        assert not record.destination.exists()
        assert len(mgr.list_backups()) == 0
    print("✓ 删除备份测试通过")


def test_backup_restore_tool():
    """测试备份恢复工具主类"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "data"
        src.mkdir()
        (src / "f1.txt").write_text("tool test")
        backup_dir = Path(tmpdir) / "backups"
        tool = BackupRestoreTool(backup_dir=backup_dir)
        record = tool.full_backup(src, name="tool_full")
        assert record.status == BackupStatus.SUCCESS
        assert tool.verify_backup(record.id) is True
        result = tool.restore(record.id, Path(tmpdir) / "restored")
        assert result.success is True
    print("✓ 备份恢复工具主类测试通过")


def test_backup_error():
    """测试备份异常"""
    try:
        raise BackupError("test error")
    except BackupError as e:
        assert "test error" in e.message
    print("✓ 备份异常测试通过")


def main():
    print("=" * 60)
    print("阶段97验证：备份恢复模块")
    print("=" * 60)

    test_backup_record()
    test_full_backup_strategy()
    test_incremental_backup_strategy()
    test_backup_validator()
    test_backup_manager()
    test_restore()
    test_delete_backup()
    test_backup_restore_tool()
    test_backup_error()

    print("=" * 60)
    print("阶段97验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
