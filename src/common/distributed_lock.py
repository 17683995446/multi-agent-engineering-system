"""
分布式锁模块
遵循第一性原理：互斥与安全性

核心功能：
1. 基于文件的分布式锁 - 多进程互斥
2. 锁超时 - 防止死锁
3. 锁续期 - 自动延长锁持有时间
4. 可重入锁 - 同一线程多次获取
"""

from __future__ import annotations

import fcntl
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from common.utils import setup_logger

logger = setup_logger(__name__)


class LockStatus(Enum):
    """锁状态"""
    FREE = "free"
    LOCKED = "locked"
    EXPIRED = "expired"


class LockException(Exception):
    """锁异常"""
    pass


class LockTimeoutException(LockException):
    """锁超时异常"""
    pass


class LockNotOwnedException(LockException):
    """锁不属于自己的异常"""
    pass


@dataclass
class LockInfo:
    """锁信息"""
    lock_id: str
    owner: str
    acquired_at: float
    expires_at: float
    renew_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lock_id": self.lock_id,
            "owner": self.owner,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "renew_count": self.renew_count,
            "is_expired": self.is_expired,
        }


class DistributedLock:
    """基于文件的分布式锁"""

    def __init__(
        self,
        lock_name: str,
        lock_dir: Optional[Path] = None,
        default_timeout: float = 30.0,
        auto_renew: bool = False,
        renew_interval: float = 10.0,
    ):
        self.lock_name = lock_name
        self.lock_dir = lock_dir or Path("/tmp/distributed_locks")
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.lock_dir / f"{lock_name}.lock"
        self.default_timeout = default_timeout
        self.auto_renew = auto_renew
        self.renew_interval = renew_interval

        self._owner = f"{os.getpid()}_{threading.current_thread().ident}_{uuid.uuid4().hex[:8]}"
        self._lock_info: Optional[LockInfo] = None
        self._file_handle: Optional[Any] = None
        self._reentrant_count = 0
        self._renew_thread: Optional[threading.Thread] = None
        self._stop_renew = threading.Event()
        self._local_lock = threading.RLock()

    def _open_lock_file(self) -> Any:
        """打开锁文件"""
        return open(self.lock_file, "w")

    def _write_lock_info(self, fh: Any, info: LockInfo) -> None:
        """写入锁信息到文件"""
        fh.seek(0)
        fh.truncate()
        fh.write(f"{info.lock_id}\n{info.owner}\n{info.acquired_at}\n{info.expires_at}\n")
        fh.flush()

    def _read_lock_info(self, fh: Any) -> Optional[LockInfo]:
        """从文件读取锁信息"""
        try:
            fh.seek(0)
            lines = fh.read().strip().split("\n")
            if len(lines) >= 4:
                return LockInfo(
                    lock_id=lines[0],
                    owner=lines[1],
                    acquired_at=float(lines[2]),
                    expires_at=float(lines[3]),
                )
        except Exception:
            pass
        return None

    def _start_renew_thread(self) -> None:
        """启动续期线程"""
        if not self.auto_renew or self._renew_thread is not None:
            return

        self._stop_renew.clear()

        def renew_loop():
            while not self._stop_renew.is_set():
                self._stop_renew.wait(self.renew_interval)
                if self._stop_renew.is_set():
                    break
                try:
                    self.renew()
                except Exception as e:
                    logger.warning(f"锁续期失败 [{self.lock_name}]: {e}")

        self._renew_thread = threading.Thread(target=renew_loop, daemon=True, name=f"lock_renew_{self.lock_name}")
        self._renew_thread.start()
        logger.debug(f"锁续期线程已启动 [{self.lock_name}]")

    def _stop_renew_thread(self) -> None:
        """停止续期线程"""
        if self._renew_thread is None:
            return
        self._stop_renew.set()
        self._renew_thread.join(timeout=2.0)
        self._renew_thread = None
        logger.debug(f"锁续期线程已停止 [{self.lock_name}]")

    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """获取锁"""
        with self._local_lock:
            # 可重入
            if self._reentrant_count > 0 and self._lock_info is not None:
                if not self._lock_info.is_expired:
                    self._reentrant_count += 1
                    logger.debug(f"锁可重入获取 [{self.lock_name}], count={self._reentrant_count}")
                    return True

            wait_timeout = timeout if timeout is not None else self.default_timeout
            start_time = time.time()

            while True:
                try:
                    fh = self._open_lock_file()
                    # 非阻塞获取文件锁
                    lock_flags = fcntl.LOCK_EX if blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fh.fileno(), lock_flags)

                    # 检查现有锁是否过期
                    existing = self._read_lock_info(fh)
                    if existing is not None and existing.owner != self._owner:
                        if not existing.is_expired:
                            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                            fh.close()
                            if not blocking:
                                return False
                            if time.time() - start_time >= wait_timeout:
                                raise LockTimeoutException(f"获取锁超时 [{self.lock_name}]")
                            time.sleep(0.1)
                            continue

                    # 获取锁成功（旧锁已过期或不存在）
                    now = time.time()
                    info = LockInfo(
                        lock_id=str(uuid.uuid4()),
                        owner=self._owner,
                        acquired_at=now,
                        expires_at=now + self.default_timeout,
                    )
                    self._write_lock_info(fh, info)
                    self._lock_info = info
                    self._file_handle = fh
                    self._reentrant_count = 1

                    if self.auto_renew:
                        self._start_renew_thread()

                    logger.info(f"锁获取成功 [{self.lock_name}], owner={self._owner}")
                    return True

                except (IOError, OSError) as e:
                    if not blocking:
                        return False
                    if time.time() - start_time >= wait_timeout:
                        raise LockTimeoutException(f"获取锁超时 [{self.lock_name}]: {e}")
                    time.sleep(0.1)

    def release(self) -> None:
        """释放锁"""
        with self._local_lock:
            if self._reentrant_count > 1:
                self._reentrant_count -= 1
                logger.debug(f"锁可重入释放 [{self.lock_name}], count={self._reentrant_count}")
                return

            if self._file_handle is None or self._lock_info is None:
                raise LockNotOwnedException(f"未持有锁 [{self.lock_name}]")

            if self._lock_info.owner != self._owner:
                raise LockNotOwnedException(f"锁不属于当前持有者 [{self.lock_name}]")

            self._stop_renew_thread()

            try:
                # 将过期时间设为过去，标记锁已释放
                self._lock_info.expires_at = 0.0
                self._write_lock_info(self._file_handle, self._lock_info)
                fcntl.flock(self._file_handle.fileno(), fcntl.LOCK_UN)
                self._file_handle.close()
            except Exception as e:
                logger.warning(f"释放锁时异常 [{self.lock_name}]: {e}")
            finally:
                self._file_handle = None
                self._lock_info = None
                self._reentrant_count = 0
                logger.info(f"锁已释放 [{self.lock_name}]")

    def renew(self, extend_seconds: Optional[float] = None) -> bool:
        """续期锁"""
        with self._local_lock:
            if self._file_handle is None or self._lock_info is None:
                raise LockNotOwnedException(f"未持有锁 [{self.lock_name}]")

            if self._lock_info.owner != self._owner:
                raise LockNotOwnedException(f"锁不属于当前持有者 [{self.lock_name}]")

            extend = extend_seconds if extend_seconds is not None else self.default_timeout
            new_expires = time.time() + extend
            self._lock_info.expires_at = new_expires
            self._lock_info.renew_count += 1
            self._write_lock_info(self._file_handle, self._lock_info)
            # 同步更新内存对象，确保 get_info() 返回最新值
            logger.debug(f"锁续期成功 [{self.lock_name}], 新过期时间={new_expires}")
            return True

    def is_locked(self) -> bool:
        """检查锁是否被持有（可能不是当前进程）"""
        try:
            if not self.lock_file.exists():
                return False
            with open(self.lock_file, "r") as fh:
                info = self._read_lock_info(fh)
                if info is None:
                    return False
                return not info.is_expired
        except Exception:
            return False

    def is_owned(self) -> bool:
        """检查锁是否被当前持有者持有"""
        with self._local_lock:
            if self._lock_info is None:
                return False
            return self._lock_info.owner == self._owner and not self._lock_info.is_expired

    def get_info(self) -> Optional[LockInfo]:
        """获取锁信息"""
        with self._local_lock:
            return self._lock_info

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def __del__(self):
        try:
            if self._file_handle is not None:
                self.release()
        except Exception:
            pass


class ReentrantDistributedLock(DistributedLock):
    """可重入分布式锁（显式支持）"""

    def __init__(self, lock_name: str, **kwargs):
        super().__init__(lock_name, **kwargs)

    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        return super().acquire(blocking=blocking, timeout=timeout)

    def release(self) -> None:
        super().release()


@contextmanager
def distributed_lock(
    lock_name: str,
    timeout: float = 30.0,
    auto_renew: bool = False,
    lock_dir: Optional[Path] = None,
):
    """分布式锁上下文管理器"""
    lock = DistributedLock(
        lock_name=lock_name,
        default_timeout=timeout,
        auto_renew=auto_renew,
        lock_dir=lock_dir,
    )
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()
