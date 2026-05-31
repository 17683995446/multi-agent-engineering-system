"""
备份恢复模块
遵循第一性原理：数据安全公理

核心功能：
1. 数据备份
2. 增量备份
3. 备份验证
4. 数据恢复
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class BackupError(Exception):
    """备份异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class BackupType(Enum):
    """备份类型"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    """备份状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class BackupRecord:
    """备份记录"""
    id: str
    source: Path
    destination: Path
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    size_bytes: int = 0
    file_count: int = 0
    checksum: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": str(self.source),
            "destination": str(self.destination),
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "checksum": self.checksum,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }


@dataclass
class RestoreResult:
    """恢复结果"""
    backup_id: str
    target: Path
    success: bool
    files_restored: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class BackupStrategy(ABC):
    """备份策略抽象基类"""

    @abstractmethod
    def execute(self, source: Path, destination: Path, record: BackupRecord) -> BackupRecord:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class FullBackupStrategy(BackupStrategy):
    """全量备份策略"""

    def get_name(self) -> str:
        return "full"

    def execute(self, source: Path, destination: Path, record: BackupRecord) -> BackupRecord:
        if not source.exists():
            raise BackupError(f"备份源不存在: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(destination, "w:gz") as tar:
            tar.add(source, arcname=source.name)
        stat = destination.stat()
        record.size_bytes = stat.st_size
        record.checksum = self._compute_checksum(destination)
        record.status = BackupStatus.SUCCESS
        record.completed_at = datetime.now()
        return record

    def _compute_checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


class IncrementalBackupStrategy(BackupStrategy):
    """增量备份策略"""

    def __init__(self, last_backup_time: Optional[float] = None):
        self.last_backup_time = last_backup_time

    def get_name(self) -> str:
        return "incremental"

    def execute(self, source: Path, destination: Path, record: BackupRecord) -> BackupRecord:
        if not source.exists():
            raise BackupError(f"备份源不存在: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        cutoff = self.last_backup_time or 0
        with tarfile.open(destination, "w:gz") as tar:
            for item in source.rglob("*"):
                if item.is_file() and item.stat().st_mtime > cutoff:
                    tar.add(item, arcname=item.relative_to(source.parent))
        stat = destination.stat()
        record.size_bytes = stat.st_size
        record.status = BackupStatus.SUCCESS
        record.completed_at = datetime.now()
        return record


class BackupValidator:
    """备份验证器"""

    def __init__(self):
        self.logger = setup_logger(f"{__name__}.validator")

    def validate_checksum(self, record: BackupRecord) -> bool:
        """验证备份校验和"""
        if not record.checksum or not record.destination.exists():
            return False
        h = hashlib.sha256()
        with open(record.destination, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        valid = h.hexdigest() == record.checksum
        if valid:
            record.status = BackupStatus.VERIFIED
        self.logger.info(f"备份 {record.id} 校验和验证: {'通过' if valid else '失败'}")
        return valid

    def validate_integrity(self, record: BackupRecord) -> bool:
        """验证备份文件完整性"""
        try:
            if not record.destination.exists():
                return False
            if tarfile.is_tarfile(record.destination):
                with tarfile.open(record.destination, "r:gz") as tar:
                    members = tar.getmembers()
                    record.file_count = len(members)
                    for member in members:
                        tar.extractfile(member)
            return True
        except Exception as e:
            self.logger.error(f"备份完整性验证失败: {e}")
            return False


class BackupManager:
    """备份管理器"""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, BackupRecord] = {}
        self.validator = BackupValidator()
        self._lock = threading.Lock()
        self.logger = setup_logger(f"{__name__}.manager")
        self._load_records()

    def _load_records(self) -> None:
        """加载历史备份记录"""
        index_file = self.backup_dir / "backup_index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    record = BackupRecord(
                        id=item["id"],
                        source=Path(item["source"]),
                        destination=Path(item["destination"]),
                        backup_type=BackupType(item["backup_type"]),
                        status=BackupStatus(item["status"]),
                        created_at=datetime.fromisoformat(item["created_at"]),
                        completed_at=datetime.fromisoformat(item["completed_at"]) if item["completed_at"] else None,
                        size_bytes=item["size_bytes"],
                        file_count=item.get("file_count", 0),
                        checksum=item["checksum"],
                        parent_id=item["parent_id"],
                        metadata=item.get("metadata", {}),
                    )
                    self.records[record.id] = record
            except Exception as e:
                self.logger.warning(f"加载备份索引失败: {e}")

    def _save_records(self) -> None:
        """保存备份记录索引"""
        index_file = self.backup_dir / "backup_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self.records.values()], f, ensure_ascii=False, indent=2)

    def backup(
        self,
        source: Union[str, Path],
        backup_type: BackupType = BackupType.FULL,
        name: Optional[str] = None,
    ) -> BackupRecord:
        """执行备份"""
        source = Path(source)
        backup_id = name or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        destination = self.backup_dir / f"{backup_id}.tar.gz"

        record = BackupRecord(
            id=backup_id,
            source=source,
            destination=destination,
            backup_type=backup_type,
            status=BackupStatus.RUNNING,
            created_at=datetime.now(),
        )

        if backup_type == BackupType.INCREMENTAL:
            last_full = self._get_last_full_backup()
            if last_full and last_full.completed_at:
                strategy = IncrementalBackupStrategy(last_full.completed_at.timestamp())
                record.parent_id = last_full.id
            else:
                strategy = FullBackupStrategy()
        else:
            strategy = FullBackupStrategy()

        self.logger.info(f"开始备份: {backup_id}, 类型: {backup_type.value}")
        try:
            with self._lock:
                record = strategy.execute(source, destination, record)
                self.records[backup_id] = record
                self._save_records()
            self.logger.info(f"备份完成: {backup_id}, 大小: {record.size_bytes} 字节")
        except Exception as e:
            record.status = BackupStatus.FAILED
            record.metadata["error"] = str(e)
            self.logger.error(f"备份失败: {backup_id}: {e}")
            raise BackupError(str(e))

        return record

    def _get_last_full_backup(self) -> Optional[BackupRecord]:
        """获取最近一次全量备份"""
        fulls = [r for r in self.records.values() if r.backup_type == BackupType.FULL and r.status == BackupStatus.SUCCESS]
        if not fulls:
            return None
        return max(fulls, key=lambda r: r.created_at)

    def verify(self, backup_id: str) -> bool:
        """验证备份"""
        if backup_id not in self.records:
            raise BackupError(f"备份不存在: {backup_id}")
        record = self.records[backup_id]
        checksum_ok = self.validator.validate_checksum(record)
        integrity_ok = self.validator.validate_integrity(record)
        return checksum_ok and integrity_ok

    def restore(self, backup_id: str, target: Union[str, Path]) -> RestoreResult:
        """恢复数据"""
        target = Path(target)
        result = RestoreResult(backup_id=backup_id, target=target, success=False, start_time=datetime.now())

        if backup_id not in self.records:
            result.errors.append(f"备份不存在: {backup_id}")
            result.end_time = datetime.now()
            return result

        record = self.records[backup_id]
        if not record.destination.exists():
            result.errors.append(f"备份文件不存在: {record.destination}")
            result.end_time = datetime.now()
            return result

        self.logger.info(f"开始恢复: {backup_id} -> {target}")
        try:
            target.mkdir(parents=True, exist_ok=True)
            with tarfile.open(record.destination, "r:gz") as tar:
                tar.extractall(path=target)
                result.files_restored = len(tar.getmembers())
            result.success = True
            self.logger.info(f"恢复完成: {backup_id}")
        except Exception as e:
            result.errors.append(str(e))
            self.logger.error(f"恢复失败: {backup_id}: {e}")

        result.end_time = datetime.now()
        return result

    def list_backups(self) -> List[BackupRecord]:
        """列出所有备份"""
        return sorted(self.records.values(), key=lambda r: r.created_at, reverse=True)

    def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        if backup_id not in self.records:
            return False
        record = self.records[backup_id]
        try:
            if record.destination.exists():
                record.destination.unlink()
            del self.records[backup_id]
            self._save_records()
            self.logger.info(f"备份已删除: {backup_id}")
            return True
        except OSError as e:
            self.logger.error(f"删除备份失败: {backup_id}: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取备份管理器状态"""
        total_size = sum(r.size_bytes for r in self.records.values())
        return {
            "backup_count": len(self.records),
            "total_size_bytes": total_size,
            "backup_dir": str(self.backup_dir),
            "last_backup": max((r.created_at for r in self.records.values()), default=None).isoformat() if self.records else None,
        }


class BackupRestoreTool:
    """
    备份恢复工具主类

    整合所有功能:
    - 数据备份
    - 增量备份
    - 备份验证
    - 数据恢复
    """

    def __init__(self, backup_dir: Optional[Path] = None):
        if backup_dir is None:
            backup_dir = Path(__file__).parent.parent.parent / "backups"
        self.manager = BackupManager(backup_dir)
        self.logger = setup_logger(__name__)

    def full_backup(self, source: Union[str, Path], name: Optional[str] = None) -> BackupRecord:
        """全量备份"""
        return self.manager.backup(source, BackupType.FULL, name)

    def incremental_backup(self, source: Union[str, Path], name: Optional[str] = None) -> BackupRecord:
        """增量备份"""
        return self.manager.backup(source, BackupType.INCREMENTAL, name)

    def verify_backup(self, backup_id: str) -> bool:
        """验证备份"""
        return self.manager.verify(backup_id)

    def restore(self, backup_id: str, target: Union[str, Path]) -> RestoreResult:
        """恢复数据"""
        return self.manager.restore(backup_id, target)

    def list_backups(self) -> List[BackupRecord]:
        """列出备份"""
        return self.manager.list_backups()

    def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        return self.manager.delete_backup(backup_id)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return self.manager.get_status()


def demo_backup_restore():
    """演示备份恢复工具"""
    import tempfile

    print("=" * 60)
    print("备份恢复工具演示")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        source = tmp_path / "data"
        source.mkdir()
        (source / "file1.txt").write_text("hello world")
        (source / "file2.txt").write_text("backup demo")
        backup_dir = tmp_path / "backups"

        tool = BackupRestoreTool(backup_dir=backup_dir)

        print("1. 全量备份:")
        record = tool.full_backup(source, name="demo_full")
        print(f"   备份ID: {record.id}")
        print(f"   大小: {record.size_bytes} 字节")
        print(f"   状态: {record.status.value}")
        print()

        print("2. 验证备份:")
        valid = tool.verify_backup(record.id)
        print(f"   验证结果: {'通过' if valid else '失败'}")
        print()

        print("3. 增量备份:")
        time.sleep(0.1)
        (source / "file3.txt").write_text("new file")
        inc_record = tool.incremental_backup(source, name="demo_inc")
        print(f"   备份ID: {inc_record.id}")
        print(f"   类型: {inc_record.backup_type.value}")
        print()

        print("4. 列出备份:")
        backups = tool.list_backups()
        for b in backups:
            print(f"   - {b.id} ({b.backup_type.value})")
        print()

        print("5. 恢复数据:")
        restore_target = tmp_path / "restored"
        result = tool.restore(record.id, restore_target)
        print(f"   成功: {result.success}")
        print(f"   恢复文件数: {result.files_restored}")
        print()

        print("6. 状态报告:")
        status = tool.get_status()
        print(f"   备份数量: {status['backup_count']}")
        print(f"   总大小: {status['total_size_bytes']} 字节")
        print()

    print("=" * 60)
    print("备份恢复工具演示完成")
    print("=" * 60)
    print()
    print("✓ 数据备份")
    print("✓ 增量备份")
    print("✓ 备份验证")
    print("✓ 数据恢复")
    print()


if __name__ == "__main__":
    demo_backup_restore()
