#!/usr/bin/env python3
"""
阶段74验证脚本：文件存储适配器

测试内容：
1. 上传/下载（内存存储）
2. 上传/下载（本地存储）
3. 文件信息
4. 列出文件
5. 复制/移动/删除
6. 路径安全
7. 统计信息
8. 线程安全
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.storage_adapter import (
    FileInfo,
    LocalStorageBackend,
    MemoryStorageBackend,
    StorageAdapter,
    StorageConfig,
    StorageType,
    get_storage_adapter,
)


def test_memory_storage() -> bool:
    print("[Test] Memory Storage - 内存存储")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_mem")

        # Upload
        info = storage.upload("test.txt", b"Hello, Memory!")
        assert info.path == "test.txt"
        assert info.size == len(b"Hello, Memory!")
        assert info.checksum != ""
        print(f"  ✓ 上传: {info.path}, 大小: {info.size}")

        # Download
        data = storage.download("test.txt")
        assert data == b"Hello, Memory!"
        print(f"  ✓ 下载: {data.decode()}")

        # Exists
        assert storage.exists("test.txt") is True
        assert storage.exists("not_exist.txt") is False
        print(f"  ✓ 存在检查正确")

        storage.close()
        print("[Pass] Memory Storage\n")
        return True
    except Exception as e:
        print(f"[Fail] Memory Storage: {e}\n")
        return False


def test_local_storage() -> bool:
    print("[Test] Local Storage - 本地存储")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = get_storage_adapter(
                StorageConfig(storage_type=StorageType.LOCAL, base_path=tmpdir),
                name="test_local",
            )

            # Upload
            info = storage.upload("docs/readme.md", b"# README\nHello!")
            assert info.size == len(b"# README\nHello!")
            print(f"  ✓ 上传: {info.path}")

            # Download
            data = storage.download("docs/readme.md")
            assert data == b"# README\nHello!"
            print(f"  ✓ 下载正确")

            # File exists on disk
            assert os.path.exists(os.path.join(tmpdir, "docs", "readme.md"))
            print(f"  ✓ 文件已写入磁盘")

            storage.close()

        print("[Pass] Local Storage\n")
        return True
    except Exception as e:
        print(f"[Fail] Local Storage: {e}\n")
        return False


def test_file_info() -> bool:
    print("[Test] File Info - 文件信息")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_info")

        storage.upload("info.txt", b"test data", metadata={"author": "test"})
        info = storage.get_info("info.txt")

        assert info is not None
        assert info.name == "info.txt"
        assert info.size == len(b"test data")
        assert info.metadata.get("author") == "test"
        print(f"  ✓ 文件信息: {info.to_dict()}")

        # Not found
        info_none = storage.get_info("not_found.txt")
        assert info_none is None
        print(f"  ✓ 不存在的文件返回 None")

        storage.close()
        print("[Pass] File Info\n")
        return True
    except Exception as e:
        print(f"[Fail] File Info: {e}\n")
        return False


def test_list_files() -> bool:
    print("[Test] List Files - 列出文件")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_list")

        storage.upload("a/1.txt", b"1")
        storage.upload("a/2.txt", b"2")
        storage.upload("b/3.txt", b"3")

        all_files = storage.list_files()
        assert len(all_files) == 3
        print(f"  ✓ 全部文件: {len(all_files)}")

        prefix_files = storage.list_files("a/")
        assert len(prefix_files) == 2
        print(f"  ✓ 前缀过滤: {len(prefix_files)}")

        storage.close()
        print("[Pass] List Files\n")
        return True
    except Exception as e:
        print(f"[Fail] List Files: {e}\n")
        return False


def test_copy_move_delete() -> bool:
    print("[Test] Copy/Move/Delete - 复制移动删除")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_cmd")

        storage.upload("src.txt", b"source")

        # Copy
        result = storage.copy("src.txt", "dst.txt")
        assert result is True
        assert storage.exists("dst.txt") is True
        assert storage.download("dst.txt") == b"source"
        print(f"  ✓ 复制成功")

        # Move
        result = storage.move("dst.txt", "moved.txt")
        assert result is True
        assert storage.exists("dst.txt") is False
        assert storage.exists("moved.txt") is True
        print(f"  ✓ 移动成功")

        # Delete
        result = storage.delete("moved.txt")
        assert result is True
        assert storage.exists("moved.txt") is False
        print(f"  ✓ 删除成功")

        storage.close()
        print("[Pass] Copy/Move/Delete\n")
        return True
    except Exception as e:
        print(f"[Fail] Copy/Move/Delete: {e}\n")
        return False


def test_path_security() -> bool:
    print("[Test] Path Security - 路径安全")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_security")

        # 正常路径
        storage.upload("safe/path.txt", b"safe")
        print(f"  ✓ 正常路径允许")

        storage.close()
        print("[Pass] Path Security\n")
        return True
    except Exception as e:
        print(f"[Fail] Path Security: {e}\n")
        return False


def test_stats() -> bool:
    print("[Test] Stats - 统计信息")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_stats")

        storage.upload("stats1.txt", b"a")
        storage.upload("stats2.txt", b"bb")
        storage.download("stats1.txt")
        storage.delete("stats2.txt")

        stats = storage.get_stats()
        assert stats["total_writes"] == 2
        assert stats["total_reads"] == 1
        assert stats["total_deletes"] == 1
        assert stats["total_bytes_written"] == 3
        assert stats["total_bytes_read"] == 1
        print(f"  ✓ 统计: {stats}")

        storage.close()
        print("[Pass] Stats\n")
        return True
    except Exception as e:
        print(f"[Fail] Stats: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] Thread Safety - 线程安全")
    try:
        storage = get_storage_adapter(StorageConfig(storage_type=StorageType.MEMORY), name="test_thread")
        errors = []

        def worker():
            try:
                for i in range(10):
                    storage.upload(f"thread/{i}.txt", b"data")
                    storage.list_files()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        print(f"  ✓ 5线程并发操作无错误")

        storage.close()
        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段74验证脚本：文件存储适配器")
    print("=" * 60 + "\n")

    results = []
    results.append(("Memory Storage", test_memory_storage()))
    results.append(("Local Storage", test_local_storage()))
    results.append(("File Info", test_file_info()))
    results.append(("List Files", test_list_files()))
    results.append(("Copy/Move/Delete", test_copy_move_delete()))
    results.append(("Path Security", test_path_security()))
    results.append(("Stats", test_stats()))
    results.append(("Thread Safety", test_thread_safety()))

    print("=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("🎉 所有测试通过！阶段74验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
