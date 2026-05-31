#!/usr/bin/env python3
"""
阶段63验证脚本：分布式锁
"""

import sys
import threading
import time
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.distributed_lock import (
    DistributedLock,
    ReentrantDistributedLock,
    LockTimeoutException,
    LockNotOwnedException,
    distributed_lock,
)


def test_lock_acquire_release():
    """测试锁获取与释放"""
    lock = DistributedLock("test_basic", default_timeout=5.0)
    assert lock.acquire() is True
    assert lock.is_owned() is True
    lock.release()
    assert lock.is_owned() is False
    print("[PASS] Lock Acquire and Release")


def test_lock_context_manager():
    """测试上下文管理器"""
    lock = DistributedLock("test_ctx", default_timeout=5.0)
    with lock:
        assert lock.is_owned() is True
    assert lock.is_owned() is False
    print("[PASS] Lock Context Manager")


def test_lock_decorator():
    """测试上下文管理器函数"""
    with distributed_lock("test_deco", timeout=5.0) as lock:
        assert lock.is_owned() is True
    print("[PASS] Lock Decorator")


def test_lock_timeout():
    """测试锁超时"""
    lock1 = DistributedLock("test_timeout", default_timeout=10.0)
    lock2 = DistributedLock("test_timeout", default_timeout=10.0)

    lock1.acquire()
    try:
        # lock2 应该超时（非阻塞模式）
        result = lock2.acquire(blocking=False)
        assert result is False
        assert not lock2.is_owned()
    finally:
        lock1.release()
    print("[PASS] Lock Timeout")


def test_lock_reentrant():
    """测试可重入锁"""
    lock = DistributedLock("test_reentrant", default_timeout=5.0)
    lock.acquire()
    lock.acquire()  # 重入
    lock.acquire()  # 再次重入
    assert lock.is_owned() is True
    lock.release()  # 第一次释放
    lock.release()  # 第二次释放
    lock.release()  # 第三次释放
    assert lock.is_owned() is False
    print("[PASS] Lock Reentrant")


def test_lock_renew():
    """测试锁续期"""
    lock = DistributedLock("test_renew", default_timeout=1.0)
    lock.acquire()
    info_before = lock.get_info()
    # 不sleep，直接续期，确保时间戳有差异
    lock.renew(extend_seconds=10.0)
    info_after = lock.get_info()
    # 续期后过期时间应该大于当前时间，且renew_count增加
    assert info_after.expires_at > time.time() + 5, f"续期后过期时间应该很远: {info_after.expires_at}"
    assert info_after.renew_count == 1
    lock.release()
    print("[PASS] Lock Renew")


def test_lock_auto_renew():
    """测试自动续期"""
    lock = DistributedLock("test_auto_renew", default_timeout=2.0, auto_renew=True, renew_interval=0.5)
    lock.acquire()
    time.sleep(1.5)
    info = lock.get_info()
    assert info.renew_count >= 1
    lock.release()
    print("[PASS] Lock Auto Renew")


def test_lock_not_owned_release():
    """测试释放不属于自己的锁"""
    lock = DistributedLock("test_not_owned", default_timeout=5.0)
    # 未获取就释放应该抛异常
    try:
        lock.release()
        assert False, "应该抛出异常"
    except LockNotOwnedException:
        pass
    print("[PASS] Lock Not Owned Release")


def test_lock_is_locked():
    """测试锁状态检查"""
    lock = DistributedLock("test_status", default_timeout=5.0)
    assert lock.is_locked() is False
    lock.acquire()
    assert lock.is_locked() is True
    lock.release()
    assert lock.is_locked() is False
    print("[PASS] Lock Is Locked")


def test_lock_info():
    """测试锁信息"""
    lock = DistributedLock("test_info", default_timeout=5.0)
    lock.acquire()
    info = lock.get_info()
    assert info is not None
    assert info.lock_id is not None
    assert info.owner is not None
    assert info.acquired_at > 0
    assert info.expires_at > info.acquired_at
    lock.release()
    print("[PASS] Lock Info")


def test_concurrent_lock():
    """测试并发锁竞争"""
    lock_name = "test_concurrent"
    results = []
    lock = threading.Lock()

    def worker(worker_id):
        l = DistributedLock(lock_name, default_timeout=10.0)
        if l.acquire(blocking=True, timeout=3.0):
            with lock:
                results.append(worker_id)
            time.sleep(0.2)
            l.release()

    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(results) == 5
    print("[PASS] Concurrent Lock")


def test_reentrant_distributed_lock():
    """测试显式可重入锁"""
    lock = ReentrantDistributedLock("test_reentrant_cls", default_timeout=5.0)
    lock.acquire()
    lock.acquire()
    assert lock.is_owned() is True
    lock.release()
    lock.release()
    assert lock.is_owned() is False
    print("[PASS] Reentrant Distributed Lock")


def test_lock_expiration():
    """测试锁过期：通过is_locked观察状态变化"""
    lock1 = DistributedLock("test_expire", default_timeout=0.3)

    lock1.acquire()
    # 锁应该处于锁定状态
    assert lock1.is_locked() is True

    time.sleep(0.5)  # 等待锁过期

    # 锁应该已过期
    assert lock1.is_locked() is False, "锁应该已过期"
    print("[PASS] Lock Expiration")


def run_all_tests():
    print("=" * 50)
    print("阶段63验证：分布式锁")
    print("=" * 50)

    tests = [
        test_lock_acquire_release,
        test_lock_context_manager,
        test_lock_decorator,
        test_lock_timeout,
        test_lock_reentrant,
        test_lock_renew,
        test_lock_auto_renew,
        test_lock_not_owned_release,
        test_lock_is_locked,
        test_lock_info,
        test_concurrent_lock,
        test_reentrant_distributed_lock,
        test_lock_expiration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 50)
    print(f"结果：通过 {passed} / 失败 {failed} / 总计 {len(tests)}")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
