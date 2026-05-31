"""
公共层 - 文件存储适配器模块
遵循第一性原理：统一接口、路径管理、存储抽象

核心功能：
1. 统一存储接口（本地/内存）
2. 文件上传下载
3. 路径管理
4. 存储后端切换
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class StorageType(Enum):
    """存储类型"""
    LOCAL = "local"
    MEMORY = "memory"
    S3 = "s3"
    OSS = "oss"


class StorageException(Exception):
    """存储异常"""
    pass


class FileNotFound(StorageException):
    """文件不存在"""
    pass


class PathNotAllowed(StorageException):
    """路径不允许访问"""
    pass


@dataclass
class FileInfo:
    """文件信息"""
    path: str = ""
    name: str = ""
    size: int = 0
    checksum: str = ""
    created_at: float = 0.0
    modified_at: float = 0.0
    content_type: str = "application/octet-stream"
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "content_type": self.content_type,
            "metadata": self.metadata,
        }


@dataclass
class StorageConfig:
    """存储配置"""
    storage_type: StorageType = StorageType.LOCAL
    base_path: str = "./storage"
    allowed_extensions: Optional[List[str]] = None
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    enable_checksum: bool = True
    enable_backup: bool = False


class StorageBackend(ABC):
    """
    存储后端抽象基类
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.logger = setup_logger(f"common.storage_adapter.{config.storage_type.value}")

    @abstractmethod
    def write(self, path: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        """写入文件"""

    @abstractmethod
    def read(self, path: str) -> bytes:
        """读取文件"""

    @abstractmethod
    def delete(self, path: str) -> bool:
        """删除文件"""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """文件是否存在"""

    @abstractmethod
    def list_files(self, prefix: str = "") -> List[FileInfo]:
        """列出文件"""

    @abstractmethod
    def get_info(self, path: str) -> Optional[FileInfo]:
        """获取文件信息"""

    @abstractmethod
    def move(self, src: str, dst: str) -> bool:
        """移动文件"""

    @abstractmethod
    def copy(self, src: str, dst: str) -> bool:
        """复制文件"""

    @abstractmethod
    def close(self) -> None:
        """关闭后端"""

    def _validate_path(self, path: str) -> str:
        """验证路径安全性"""
        normalized = os.path.normpath(path)
        if normalized.startswith("..") or normalized.startswith("/.."):
            raise PathNotAllowed(f"路径不允许访问: {path}")
        return normalized

    def _compute_checksum(self, data: bytes) -> str:
        """计算校验和"""
        return hashlib.md5(data).hexdigest()


class LocalStorageBackend(StorageBackend):
    """
    本地文件系统存储后端
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = Path(config.base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, path: str) -> Path:
        """获取完整路径"""
        normalized = self._validate_path(path)
        full = self.base_path / normalized
        # 确保在base_path下
        try:
            full.relative_to(self.base_path)
        except ValueError:
            raise PathNotAllowed(f"路径超出允许范围: {path}")
        return full

    def write(self, path: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        full = self._full_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            raw_data = data
        else:
            raw_data = data.read()

        if len(raw_data) > self.config.max_file_size:
            raise StorageException(f"文件大小超过限制: {len(raw_data)} > {self.config.max_file_size}")

        with open(full, "wb") as f:
            f.write(raw_data)

        now = time.time()
        info = FileInfo(
            path=path,
            name=full.name,
            size=len(raw_data),
            checksum=self._compute_checksum(raw_data) if self.config.enable_checksum else "",
            created_at=now,
            modified_at=now,
            metadata=metadata or {},
        )
        self.logger.debug(f"文件已写入: {path}, 大小: {len(raw_data)}")
        return info

    def read(self, path: str) -> bytes:
        full = self._full_path(path)
        if not full.exists():
            raise FileNotFound(f"文件不存在: {path}")
        with open(full, "rb") as f:
            return f.read()

    def delete(self, path: str) -> bool:
        full = self._full_path(path)
        if not full.exists():
            return False
        if full.is_file():
            full.unlink()
        else:
            shutil.rmtree(full)
        self.logger.debug(f"文件已删除: {path}")
        return True

    def exists(self, path: str) -> bool:
        full = self._full_path(path)
        return full.exists()

    def list_files(self, prefix: str = "") -> List[FileInfo]:
        base = self._full_path(prefix) if prefix else self.base_path
        if not base.exists():
            return []

        files = []
        for item in base.rglob("*"):
            if item.is_file():
                rel_path = str(item.relative_to(self.base_path))
                stat = item.stat()
                files.append(FileInfo(
                    path=rel_path,
                    name=item.name,
                    size=stat.st_size,
                    created_at=stat.st_ctime,
                    modified_at=stat.st_mtime,
                ))
        return files

    def get_info(self, path: str) -> Optional[FileInfo]:
        full = self._full_path(path)
        if not full.exists():
            return None
        stat = full.stat()
        return FileInfo(
            path=path,
            name=full.name,
            size=stat.st_size,
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
        )

    def move(self, src: str, dst: str) -> bool:
        src_full = self._full_path(src)
        dst_full = self._full_path(dst)
        if not src_full.exists():
            return False
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_full), str(dst_full))
        return True

    def copy(self, src: str, dst: str) -> bool:
        src_full = self._full_path(src)
        dst_full = self._full_path(dst)
        if not src_full.exists():
            return False
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_full), str(dst_full))
        return True

    def close(self) -> None:
        self.logger.info("本地存储后端已关闭")


class MemoryStorageBackend(StorageBackend):
    """
    内存存储后端（用于测试和演示）
    """

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def write(self, path: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        normalized = self._validate_path(path)

        if isinstance(data, bytes):
            raw_data = data
        else:
            raw_data = data.read()

        if len(raw_data) > self.config.max_file_size:
            raise StorageException(f"文件大小超过限制: {len(raw_data)} > {self.config.max_file_size}")

        now = time.time()
        info = FileInfo(
            path=normalized,
            name=Path(normalized).name,
            size=len(raw_data),
            checksum=self._compute_checksum(raw_data) if self.config.enable_checksum else "",
            created_at=now,
            modified_at=now,
            metadata=metadata or {},
        )

        with self._lock:
            self._storage[normalized] = {
                "data": raw_data,
                "info": info,
            }
        self.logger.debug(f"文件已写入内存: {normalized}, 大小: {len(raw_data)}")
        return info

    def read(self, path: str) -> bytes:
        normalized = self._validate_path(path)
        with self._lock:
            item = self._storage.get(normalized)
            if not item:
                raise FileNotFound(f"文件不存在: {path}")
            return item["data"]

    def delete(self, path: str) -> bool:
        normalized = self._validate_path(path)
        with self._lock:
            if normalized in self._storage:
                del self._storage[normalized]
                return True
            return False

    def exists(self, path: str) -> bool:
        normalized = self._validate_path(path)
        with self._lock:
            return normalized in self._storage

    def list_files(self, prefix: str = "") -> List[FileInfo]:
        with self._lock:
            files = []
            for path, item in self._storage.items():
                if path.startswith(prefix):
                    files.append(item["info"])
            return files

    def get_info(self, path: str) -> Optional[FileInfo]:
        normalized = self._validate_path(path)
        with self._lock:
            item = self._storage.get(normalized)
            return item["info"] if item else None

    def move(self, src: str, dst: str) -> bool:
        src_norm = self._validate_path(src)
        dst_norm = self._validate_path(dst)
        with self._lock:
            item = self._storage.get(src_norm)
            if not item:
                return False
            item["info"].path = dst_norm
            item["info"].name = Path(dst_norm).name
            self._storage[dst_norm] = item
            del self._storage[src_norm]
            return True

    def copy(self, src: str, dst: str) -> bool:
        src_norm = self._validate_path(src)
        dst_norm = self._validate_path(dst)
        with self._lock:
            item = self._storage.get(src_norm)
            if not item:
                return False
            new_info = FileInfo(
                path=dst_norm,
                name=Path(dst_norm).name,
                size=item["info"].size,
                checksum=item["info"].checksum,
                created_at=item["info"].created_at,
                modified_at=time.time(),
                metadata=dict(item["info"].metadata),
            )
            self._storage[dst_norm] = {
                "data": item["data"],
                "info": new_info,
            }
            return True

    def close(self) -> None:
        with self._lock:
            self._storage.clear()
        self.logger.info("内存存储后端已关闭")


class StorageAdapter:
    """
    文件存储适配器

    统一存储接口，支持本地/内存存储，文件上传下载，路径管理
    """

    def __init__(self, config: Optional[StorageConfig] = None, name: str = "storage_adapter"):
        self.config = config or StorageConfig()
        self.name = name
        self.logger = setup_logger(f"common.storage_adapter.{name}")
        self._backend: Optional[StorageBackend] = None
        self._stats = {
            "total_writes": 0,
            "total_reads": 0,
            "total_deletes": 0,
            "total_bytes_written": 0,
            "total_bytes_read": 0,
        }
        self._lock = threading.RLock()
        self._init_backend()

    def _init_backend(self) -> None:
        """初始化后端"""
        if self.config.storage_type == StorageType.LOCAL:
            self._backend = LocalStorageBackend(self.config)
        elif self.config.storage_type == StorageType.MEMORY:
            self._backend = MemoryStorageBackend(self.config)
        else:
            self.logger.warning(f"存储类型 {self.config.storage_type.value} 暂未实现，使用 LOCAL")
            self._backend = LocalStorageBackend(self.config)

    def upload(self, path: str, data: Union[bytes, BinaryIO], metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        """
        上传文件

        Args:
            path: 存储路径
            data: 文件数据
            metadata: 元数据
        """
        info = self._backend.write(path, data, metadata)
        with self._lock:
            self._stats["total_writes"] += 1
            self._stats["total_bytes_written"] += info.size
        return info

    def upload_bytes(self, path: str, data: bytes, metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        """上传字节数据"""
        return self.upload(path, data, metadata)

    def upload_file(self, local_path: str, remote_path: str, metadata: Optional[Dict[str, str]] = None) -> FileInfo:
        """上传本地文件"""
        with open(local_path, "rb") as f:
            return self.upload(remote_path, f, metadata)

    def download(self, path: str) -> bytes:
        """
        下载文件

        Args:
            path: 存储路径
        """
        data = self._backend.read(path)
        with self._lock:
            self._stats["total_reads"] += 1
            self._stats["total_bytes_read"] += len(data)
        return data

    def download_to_file(self, path: str, local_path: str) -> None:
        """下载到本地文件"""
        data = self.download(path)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)

    def delete(self, path: str) -> bool:
        """删除文件"""
        result = self._backend.delete(path)
        if result:
            with self._lock:
                self._stats["total_deletes"] += 1
        return result

    def exists(self, path: str) -> bool:
        """文件是否存在"""
        return self._backend.exists(path)

    def list_files(self, prefix: str = "") -> List[FileInfo]:
        """列出文件"""
        return self._backend.list_files(prefix)

    def get_info(self, path: str) -> Optional[FileInfo]:
        """获取文件信息"""
        return self._backend.get_info(path)

    def move(self, src: str, dst: str) -> bool:
        """移动文件"""
        return self._backend.move(src, dst)

    def copy(self, src: str, dst: str) -> bool:
        """复制文件"""
        return self._backend.copy(src, dst)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return self._stats.copy()

    def close(self) -> None:
        """关闭适配器"""
        if self._backend:
            self._backend.close()
            self._backend = None
        self.logger.info("存储适配器已关闭")


def get_storage_adapter(config: Optional[StorageConfig] = None, name: str = "default") -> StorageAdapter:
    """获取存储适配器实例"""
    return StorageAdapter(config, name)


def demo_storage_adapter():
    """演示文件存储适配器"""
    print("=" * 60)
    print("文件存储适配器模块验证")
    print("=" * 60)
    print()

    # 内存存储测试
    print("1. 内存存储 - 上传文件:")
    mem_storage = StorageAdapter(StorageConfig(storage_type=StorageType.MEMORY), name="mem_demo")
    info = mem_storage.upload("docs/readme.txt", b"Hello, Storage Adapter!")
    print(f"   ✓ 文件已上传: {info.path}, 大小: {info.size}, 校验和: {info.checksum}")
    print()

    print("2. 内存存储 - 下载文件:")
    data = mem_storage.download("docs/readme.txt")
    print(f"   ✓ 文件内容: {data.decode()}")
    print()

    print("3. 内存存储 - 文件信息:")
    file_info = mem_storage.get_info("docs/readme.txt")
    print(f"   ✓ 信息: {file_info.to_dict() if file_info else 'None'}")
    print()

    print("4. 内存存储 - 列出文件:")
    mem_storage.upload("docs/guide.md", b"# Guide")
    mem_storage.upload("images/logo.png", b"PNG_DATA")
    files = mem_storage.list_files()
    print(f"   ✓ 文件列表 ({len(files)}):")
    for f in files:
        print(f"      - {f.path} ({f.size} bytes)")
    print()

    print("5. 内存存储 - 复制/移动/删除:")
    mem_storage.copy("docs/readme.txt", "docs/readme_backup.txt")
    print(f"   ✓ 复制成功")
    mem_storage.move("docs/guide.md", "docs/moved_guide.md")
    print(f"   ✓ 移动成功")
    mem_storage.delete("images/logo.png")
    print(f"   ✓ 删除成功")
    print()

    print("6. 本地存储测试:")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        local_storage = StorageAdapter(
            StorageConfig(storage_type=StorageType.LOCAL, base_path=tmpdir),
            name="local_demo",
        )
        local_storage.upload("test/file.txt", b"Local storage test")
        print(f"   ✓ 本地文件已写入")
        data = local_storage.download("test/file.txt")
        print(f"   ✓ 本地文件已读取: {data.decode()}")
        files = local_storage.list_files()
        print(f"   ✓ 本地文件列表: {len(files)} 个文件")
        local_storage.close()
    print()

    print("7. 统计信息:")
    stats = mem_storage.get_stats()
    print(f"   ✓ 统计: {stats}")
    print()

    mem_storage.close()

    print("=" * 60)
    print("文件存储适配器模块验证成功")
    print("=" * 60)
    print()
    print("✓ 统一存储接口（本地/内存）")
    print("✓ 文件上传下载")
    print("✓ 路径管理")
    print("✓ 存储后端切换")
    print()


if __name__ == "__main__":
    demo_storage_adapter()
