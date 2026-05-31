"""
日志系统增强模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 结构化日志（JSON 格式）
2. 日志轮转（按大小/时间）
3. 日志分级（DEBUG/INFO/WARNING/ERROR/CRITICAL）
4. 异步日志（后台队列写入）
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import queue
import threading
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class LogFormat(Enum):
    """日志格式类型"""
    TEXT = "text"
    JSON = "json"


class LogLevel(Enum):
    """日志级别"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class StructuredLogRecord:
    """结构化日志记录"""
    timestamp: str
    level: str
    logger: str
    message: str
    thread: str
    module: str = ""
    function: str = ""
    line: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "thread": self.thread,
            "module": self.module,
            "function": self.function,
            "line": self.line,
        }
        if self.extra:
            result["extra"] = self.extra
        if self.exception:
            result["exception"] = self.exception
        return result

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        extra = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message", "asctime",
            }:
                extra[key] = value

        exc = None
        if record.exc_info:
            exc = traceback.format_exception(*record.exc_info)
            exc = "".join(exc)

        log_record = StructuredLogRecord(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            thread=record.threadName,
            module=record.module,
            function=record.funcName,
            line=record.lineno,
            extra=extra,
            exception=exc,
        )
        return log_record.to_json()


class RotatingFileHandlerBySize(logging.handlers.RotatingFileHandler):
    """按大小轮转的文件处理器"""

    def __init__(
        self,
        filename: Union[str, Path],
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
    ):
        super().__init__(
            filename=str(filename),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )


class TimedRotatingFileHandlerCustom(logging.handlers.TimedRotatingFileHandler):
    """按时间轮转的文件处理器"""

    def __init__(
        self,
        filename: Union[str, Path],
        when: str = "midnight",
        interval: int = 1,
        backup_count: int = 7,
        encoding: str = "utf-8",
    ):
        super().__init__(
            filename=str(filename),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding=encoding,
        )


class AsyncHandler(logging.Handler):
    """异步日志处理器"""

    def __init__(self, target: logging.Handler, max_queue_size: int = 10000):
        super().__init__()
        self.target = target
        self.queue: queue.Queue[Optional[logging.LogRecord]] = queue.Queue(maxsize=max_queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.dropped_count = 0
        self._start_worker()

    def _start_worker(self) -> None:
        """启动后台工作线程"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self) -> None:
        """后台工作线程"""
        while not self._stop_event.is_set():
            try:
                record = self.queue.get(timeout=0.5)
                if record is None:
                    self.queue.task_done()
                    break
                self.target.emit(record)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"异步日志处理异常: {e}")

    def emit(self, record: logging.LogRecord) -> None:
        """发送日志记录到队列"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            with self._lock:
                self.dropped_count += 1

    def flush(self) -> None:
        """刷新队列"""
        while not self.queue.empty():
            time.sleep(0.05)
        self.target.flush()

    def close(self) -> None:
        """关闭处理器"""
        self._stop_event.set()
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)
        self.target.close()
        super().close()

    def get_dropped_count(self) -> int:
        """获取丢弃的日志数量"""
        with self._lock:
            return self.dropped_count


class EnhancedLogger:
    """
    增强型日志器

    核心功能：
    - 结构化日志输出（JSON / TEXT）
    - 日志轮转（按大小 / 时间）
    - 异步日志写入
    - 日志分级过滤
    - 上下文注入
    """

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        log_format: LogFormat = LogFormat.TEXT,
        log_dir: Optional[Union[str, Path]] = None,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_async: bool = False,
        rotate_by_size: bool = True,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        rotate_when: str = "midnight",
        context: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.level = level
        self.log_format = log_format
        self.log_dir = Path(log_dir) if log_dir else Path(__file__).parent.parent.parent / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.enable_async = enable_async
        self.rotate_by_size = rotate_by_size
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.rotate_when = rotate_when
        self.context = context or {}

        self._logger = logging.getLogger(name)
        self._logger.setLevel(level.value)
        self._logger.handlers.clear()
        self._async_handlers: List[AsyncHandler] = []

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """设置日志处理器"""
        formatter = self._get_formatter()

        if self.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            if self.enable_async:
                async_handler = AsyncHandler(console_handler)
                self._logger.addHandler(async_handler)
                self._async_handlers.append(async_handler)
            else:
                self._logger.addHandler(console_handler)

        if self.enable_file:
            log_file = self.log_dir / f"{self.name.replace('.', '_')}.log"
            if self.rotate_by_size:
                file_handler = RotatingFileHandlerBySize(
                    log_file,
                    max_bytes=self.max_bytes,
                    backup_count=self.backup_count,
                )
            else:
                file_handler = TimedRotatingFileHandlerCustom(
                    log_file,
                    when=self.rotate_when,
                    backup_count=self.backup_count,
                )
            file_handler.setFormatter(formatter)
            if self.enable_async:
                async_handler = AsyncHandler(file_handler)
                self._logger.addHandler(async_handler)
                self._async_handlers.append(async_handler)
            else:
                self._logger.addHandler(file_handler)

    def _get_formatter(self) -> logging.Formatter:
        """获取格式化器"""
        if self.log_format == LogFormat.JSON:
            return JSONFormatter()
        return logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def set_level(self, level: LogLevel) -> None:
        """设置日志级别"""
        self.level = level
        self._logger.setLevel(level.value)

    def add_context(self, **kwargs: Any) -> None:
        """添加上下文信息"""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """清除上下文信息"""
        self.context.clear()

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """内部日志方法"""
        extra = {**self.context, **kwargs}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """记录异常信息"""
        extra = {**self.context, **kwargs}
        self._logger.exception(message, extra=extra)

    def get_dropped_count(self) -> int:
        """获取异步丢弃的日志数量"""
        return sum(h.get_dropped_count() for h in self._async_handlers)

    def flush(self) -> None:
        """刷新所有处理器"""
        for handler in self._async_handlers:
            handler.flush()
        for handler in self._logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

    def close(self) -> None:
        """关闭日志器"""
        for handler in self._async_handlers:
            handler.close()
        self._async_handlers.clear()
        for handler in self._logger.handlers[:]:
            handler.close()
            self._logger.removeHandler(handler)


class LogManager:
    """
    日志管理器

    统一管理所有增强型日志器
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._loggers: Dict[str, EnhancedLogger] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def get_logger(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        log_format: LogFormat = LogFormat.TEXT,
        enable_async: bool = False,
        **kwargs: Any,
    ) -> EnhancedLogger:
        """获取或创建增强型日志器"""
        with self._lock:
            if name not in self._loggers:
                self._loggers[name] = EnhancedLogger(
                    name=name,
                    level=level,
                    log_format=log_format,
                    enable_async=enable_async,
                    **kwargs,
                )
            return self._loggers[name]

    def remove_logger(self, name: str) -> None:
        """移除日志器"""
        with self._lock:
            if name in self._loggers:
                self._loggers[name].close()
                del self._loggers[name]

    def set_global_level(self, level: LogLevel) -> None:
        """设置全局日志级别"""
        with self._lock:
            for logger in self._loggers.values():
                logger.set_level(level)

    def get_status(self) -> Dict[str, Any]:
        """获取日志管理器状态"""
        with self._lock:
            return {
                "logger_count": len(self._loggers),
                "logger_names": list(self._loggers.keys()),
                "total_dropped": sum(l.get_dropped_count() for l in self._loggers.values()),
            }


def demo_logging_enhanced():
    """演示增强日志系统"""
    print("=" * 60)
    print("日志系统增强演示")
    print("=" * 60)
    print()

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        print("1. 文本格式日志:")
        text_logger = EnhancedLogger(
            "demo_text",
            level=LogLevel.DEBUG,
            log_format=LogFormat.TEXT,
            log_dir=tmpdir,
            enable_async=False,
        )
        text_logger.info("这是一条信息日志")
        text_logger.warning("这是一条警告日志")
        text_logger.error("这是一条错误日志")
        print("   ✓ 文本格式日志输出完成")
        print()

        print("2. JSON 结构化日志:")
        json_logger = EnhancedLogger(
            "demo_json",
            level=LogLevel.INFO,
            log_format=LogFormat.JSON,
            log_dir=tmpdir,
            enable_async=False,
        )
        json_logger.info("结构化日志示例", user_id="123", action="login")
        print("   ✓ JSON 格式日志输出完成")
        print()

        print("3. 日志轮转（按大小）:")
        rotate_logger = EnhancedLogger(
            "demo_rotate",
            level=LogLevel.INFO,
            log_format=LogFormat.TEXT,
            log_dir=tmpdir,
            rotate_by_size=True,
            max_bytes=1024,
            backup_count=3,
        )
        for i in range(100):
            rotate_logger.info(f"日志轮转测试消息 {i}")
        log_files = list(Path(tmpdir).glob("demo_rotate*"))
        print(f"   ✓ 轮转日志文件数: {len(log_files)}")
        print()

        print("4. 异步日志:")
        async_logger = EnhancedLogger(
            "demo_async",
            level=LogLevel.INFO,
            log_format=LogFormat.TEXT,
            log_dir=tmpdir,
            enable_async=True,
        )
        for i in range(50):
            async_logger.info(f"异步日志消息 {i}")
        async_logger.flush()
        dropped = async_logger.get_dropped_count()
        print(f"   ✓ 异步日志写入完成，丢弃: {dropped}")
        print()

        print("5. 日志分级:")
        level_logger = EnhancedLogger(
            "demo_level",
            level=LogLevel.WARNING,
            log_format=LogFormat.TEXT,
            log_dir=tmpdir,
        )
        level_logger.debug("这条 DEBUG 不会显示")
        level_logger.info("这条 INFO 不会显示")
        level_logger.warning("这条 WARNING 会显示")
        level_logger.error("这条 ERROR 会显示")
        print("   ✓ 日志分级过滤生效")
        print()

        print("6. 日志管理器:")
        manager = LogManager()
        manager.get_logger("managed_1")
        manager.get_logger("managed_2")
        status = manager.get_status()
        print(f"   ✓ 日志管理器状态: {status}")
        print()

    print("=" * 60)
    print("日志系统增强演示完成")
    print("=" * 60)
    print()
    print("✓ 结构化日志（JSON）")
    print("✓ 日志轮转（按大小/时间）")
    print("✓ 异步日志（后台队列）")
    print("✓ 日志分级过滤")
    print("✓ 上下文注入")
    print()


if __name__ == "__main__":
    demo_logging_enhanced()
