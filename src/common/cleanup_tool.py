"""
系统清理工具模块
遵循第一性原理：资源最小占用公理

核心功能：
1. 临时文件清理
2. 日志归档
3. 资源释放
4. 磁盘空间管理
"""

from __future__ import annotations

import gzip
import os
import shutil
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class CleanupError(Exception):
    """清理异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class CleanupStrategy(Enum):
    """清理策略"""
    DELETE = "delete"
    ARCHIVE = "archive"
    COMPRESS = "compress"
    MOVE = "move"


@dataclass
class CleanupRule:
    """清理规则"""
    name: str
    pattern: str
    max_age_days: int
    strategy: CleanupStrategy
    target_dir: Optional[Path] = None
    enabled: bool = True
    priority: int = 0


@dataclass
class CleanupResult:
    """清理结果"""
    rule_name: str
    files_processed: int = 0
    bytes_reclaimed: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class DiskUsage:
    """磁盘使用情况"""
    total: int
    used: int
    free: int
    percent: float

    @property
    def free_gb(self) -> float:
        return self.free / (1024 ** 3)

    @property
    def used_gb(self) -> float:
        return self.used / (1024 ** 3)

    @property
    def total_gb(self) -> float:
        return self.total / (1024 ** 3)


class CleanupTask(ABC):
    """清理任务抽象基类"""

    @abstractmethod
    def execute(self) -> CleanupResult:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class TempFileCleanup(CleanupTask):
    """临时文件清理任务"""

    def __init__(
        self,
        temp_dirs: Optional[List[Path]] = None,
        max_age_hours: int = 24,
        patterns: Optional[List[str]] = None,
    ):
        self.temp_dirs = temp_dirs or [Path(tempfile.gettempdir())]
        self.max_age_hours = max_age_hours
        self.patterns = patterns or ["*.tmp", "*.temp", "*.cache", "*.log.tmp"]
        self.logger = setup_logger(f"{__name__}.temp")

    def get_name(self) -> str:
        return "temp_file_cleanup"

    def execute(self) -> CleanupResult:
        result = CleanupResult(rule_name=self.get_name(), start_time=datetime.now())
        cutoff = time.time() - (self.max_age_hours * 3600)

        for temp_dir in self.temp_dirs:
            if not temp_dir.exists():
                continue
            for pattern in self.patterns:
                for file_path in temp_dir.rglob(pattern):
                    try:
                        if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                            size = file_path.stat().st_size
                            file_path.unlink()
                            result.files_processed += 1
                            result.bytes_reclaimed += size
                            self.logger.debug(f"删除临时文件: {file_path}")
                    except OSError as e:
                        result.errors.append(f"无法删除 {file_path}: {e}")

        result.end_time = datetime.now()
        self.logger.info(
            f"临时文件清理完成: {result.files_processed} 个文件, "
            f"回收 {result.bytes_reclaimed / 1024 / 1024:.2f} MB"
        )
        return result


class LogArchiveTask(CleanupTask):
    """日志归档任务"""

    def __init__(
        self,
        log_dir: Path,
        archive_dir: Path,
        max_age_days: int = 7,
        compress: bool = True,
        archive_format: str = "gz",
    ):
        self.log_dir = log_dir
        self.archive_dir = archive_dir
        self.max_age_days = max_age_days
        self.compress = compress
        self.archive_format = archive_format
        self.logger = setup_logger(f"{__name__}.archive")

    def get_name(self) -> str:
        return "log_archive"

    def execute(self) -> CleanupResult:
        result = CleanupResult(rule_name=self.get_name(), start_time=datetime.now())
        if not self.log_dir.exists():
            result.errors.append(f"日志目录不存在: {self.log_dir}")
            result.end_time = datetime.now()
            return result

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - (self.max_age_days * 86400)

        for log_file in self.log_dir.glob("*.log"):
            try:
                if log_file.is_file() and log_file.stat().st_mtime < cutoff:
                    size = log_file.stat().st_size
                    if self.compress:
                        archive_path = self.archive_dir / f"{log_file.name}.{self.archive_format}"
                        with open(log_file, "rb") as f_in:
                            with gzip.open(archive_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        log_file.unlink()
                    else:
                        archive_path = self.archive_dir / log_file.name
                        shutil.move(str(log_file), str(archive_path))
                    result.files_processed += 1
                    result.bytes_reclaimed += size
                    self.logger.debug(f"归档日志: {log_file.name}")
            except OSError as e:
                result.errors.append(f"无法归档 {log_file}: {e}")

        result.end_time = datetime.now()
        self.logger.info(
            f"日志归档完成: {result.files_processed} 个文件, "
            f"回收 {result.bytes_reclaimed / 1024 / 1024:.2f} MB"
        )
        return result


class ResourceReleaseTask(CleanupTask):
    """资源释放任务"""

    def __init__(self):
        self.releasers: List[Callable[[], None]] = []
        self.logger = setup_logger(f"{__name__}.release")

    def get_name(self) -> str:
        return "resource_release"

    def register(self, releaser: Callable[[], None]) -> None:
        """注册资源释放回调"""
        self.releasers.append(releaser)

    def execute(self) -> CleanupResult:
        result = CleanupResult(rule_name=self.get_name(), start_time=datetime.now())
        for releaser in self.releasers:
            try:
                releaser()
                result.files_processed += 1
            except Exception as e:
                result.errors.append(f"资源释放失败: {e}")
        self.releasers.clear()
        result.end_time = datetime.now()
        self.logger.info(f"资源释放完成: {result.files_processed} 个资源")
        return result


class DiskSpaceManager:
    """磁盘空间管理器"""

    def __init__(self, threshold_percent: float = 90.0, min_free_gb: float = 1.0):
        self.threshold_percent = threshold_percent
        self.min_free_gb = min_free_gb
        self.logger = setup_logger(f"{__name__}.disk")

    def get_usage(self, path: Union[str, Path] = "/") -> DiskUsage:
        """获取磁盘使用情况"""
        stat = shutil.disk_usage(str(path))
        percent = (stat.used / stat.total) * 100 if stat.total > 0 else 0.0
        return DiskUsage(
            total=stat.total,
            used=stat.used,
            free=stat.free,
            percent=percent,
        )

    def is_low_space(self, path: Union[str, Path] = "/") -> bool:
        """检查磁盘空间是否不足"""
        usage = self.get_usage(path)
        return usage.percent >= self.threshold_percent or usage.free_gb < self.min_free_gb

    def get_cleanup_recommendations(self, path: Union[str, Path] = "/") -> List[str]:
        """获取清理建议"""
        usage = self.get_usage(path)
        recommendations = []
        if usage.percent >= self.threshold_percent:
            recommendations.append(
                f"磁盘使用率 {usage.percent:.1f}% 超过阈值 {self.threshold_percent}%, 建议清理"
            )
        if usage.free_gb < self.min_free_gb:
            recommendations.append(
                f"可用空间 {usage.free_gb:.2f} GB 低于最小值 {self.min_free_gb} GB, 建议清理"
            )
        return recommendations


class CleanupScheduler:
    """清理调度器"""

    def __init__(self):
        self.tasks: List[CleanupTask] = []
        self.rules: List[CleanupRule] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.logger = setup_logger(f"{__name__}.scheduler")

    def add_task(self, task: CleanupTask) -> None:
        """添加清理任务"""
        with self._lock:
            self.tasks.append(task)

    def add_rule(self, rule: CleanupRule) -> None:
        """添加清理规则"""
        with self._lock:
            self.rules.append(rule)

    def run_once(self) -> List[CleanupResult]:
        """执行一次清理"""
        results = []
        with self._lock:
            tasks = self.tasks.copy()
        for task in tasks:
            try:
                self.logger.info(f"执行清理任务: {task.get_name()}")
                result = task.execute()
                results.append(result)
            except Exception as e:
                self.logger.error(f"清理任务失败: {task.get_name()}: {e}")
                results.append(
                    CleanupResult(
                        rule_name=task.get_name(),
                        errors=[str(e)],
                    )
                )
        return results

    def start_scheduler(self, interval_seconds: int = 3600) -> None:
        """启动定时调度"""
        self._running = True

        def _loop():
            while self._running:
                self.run_once()
                time.sleep(interval_seconds)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"清理调度器启动, 间隔: {interval_seconds} 秒")

    def stop_scheduler(self) -> None:
        """停止定时调度"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self.logger.info("清理调度器停止")


class CleanupTool:
    """
    系统清理工具主类

    整合所有清理功能:
    - 临时文件清理
    - 日志归档
    - 资源释放
    - 磁盘空间管理
    """

    def __init__(self):
        self.scheduler = CleanupScheduler()
        self.disk_manager = DiskSpaceManager()
        self.logger = setup_logger(__name__)

    def cleanup_temp_files(
        self,
        temp_dirs: Optional[List[Path]] = None,
        max_age_hours: int = 24,
    ) -> CleanupResult:
        """清理临时文件"""
        task = TempFileCleanup(temp_dirs=temp_dirs, max_age_hours=max_age_hours)
        return task.execute()

    def archive_logs(
        self,
        log_dir: Path,
        archive_dir: Path,
        max_age_days: int = 7,
    ) -> CleanupResult:
        """归档日志"""
        task = LogArchiveTask(log_dir=log_dir, archive_dir=archive_dir, max_age_days=max_age_days)
        return task.execute()

    def release_resources(self, releasers: Optional[List[Callable[[], None]]] = None) -> CleanupResult:
        """释放资源"""
        task = ResourceReleaseTask()
        if releasers:
            for r in releasers:
                task.register(r)
        return task.execute()

    def check_disk_space(self, path: Union[str, Path] = "/") -> DiskUsage:
        """检查磁盘空间"""
        return self.disk_manager.get_usage(path)

    def get_cleanup_report(self) -> Dict[str, Any]:
        """获取清理报告"""
        usage = self.disk_manager.get_usage()
        recommendations = self.disk_manager.get_cleanup_recommendations()
        return {
            "disk_usage": {
                "total_gb": round(usage.total_gb, 2),
                "used_gb": round(usage.used_gb, 2),
                "free_gb": round(usage.free_gb, 2),
                "percent": round(usage.percent, 2),
            },
            "recommendations": recommendations,
            "low_space": self.disk_manager.is_low_space(),
        }

    def run_full_cleanup(self) -> List[CleanupResult]:
        """执行完整清理"""
        self.logger.info("开始完整系统清理")
        results = []
        results.append(self.cleanup_temp_files())
        log_dir = Path(__file__).parent.parent.parent / "logs"
        archive_dir = log_dir / "archive"
        results.append(self.archive_logs(log_dir=log_dir, archive_dir=archive_dir))
        results.append(self.release_resources())
        self.logger.info("完整系统清理完成")
        return results


def demo_cleanup_tool():
    """演示系统清理工具"""
    print("=" * 60)
    print("系统清理工具演示")
    print("=" * 60)
    print()

    tool = CleanupTool()

    print("1. 磁盘空间检查:")
    usage = tool.check_disk_space()
    print(f"   总空间: {usage.total_gb:.2f} GB")
    print(f"   已用: {usage.used_gb:.2f} GB")
    print(f"   可用: {usage.free_gb:.2f} GB")
    print(f"   使用率: {usage.percent:.1f}%")
    print()

    print("2. 清理建议:")
    recommendations = tool.disk_manager.get_cleanup_recommendations()
    if recommendations:
        for rec in recommendations:
            print(f"   ! {rec}")
    else:
        print("   磁盘空间充足")
    print()

    print("3. 临时文件清理:")
    result = tool.cleanup_temp_files(max_age_hours=720)
    print(f"   处理文件: {result.files_processed}")
    print(f"   回收空间: {result.bytes_reclaimed / 1024:.2f} KB")
    print()

    print("4. 清理报告:")
    report = tool.get_cleanup_report()
    print(f"   磁盘使用率: {report['disk_usage']['percent']}%")
    print(f"   空间不足: {report['low_space']}")
    print()

    print("=" * 60)
    print("系统清理工具演示完成")
    print("=" * 60)
    print()
    print("✓ 临时文件清理")
    print("✓ 日志归档")
    print("✓ 资源释放")
    print("✓ 磁盘空间管理")
    print()


if __name__ == "__main__":
    demo_cleanup_tool()
