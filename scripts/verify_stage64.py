#!/usr/bin/env python3
"""
阶段64验证脚本：任务调度器
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.task_scheduler import (
    TaskScheduler,
    CronExpression,
    TaskStatus,
    ScheduleType,
)


def test_cron_expression_parse():
    """测试Cron表达式解析"""
    cron = CronExpression("*/5 * * * *")
    assert 0 in cron.minute
    assert 5 in cron.minute
    assert 10 in cron.minute
    assert 3 not in cron.minute
    print("[PASS] Cron Expression Parse")


def test_cron_expression_range():
    """测试Cron表达式范围"""
    cron = CronExpression("0 9-17 * * 1-5")
    assert cron.hour == set(range(9, 18))
    assert cron.weekday == set(range(1, 6))
    print("[PASS] Cron Expression Range")


def test_cron_should_run():
    """测试Cron是否应该执行"""
    from datetime import datetime
    cron = CronExpression("0 12 * * *")
    dt = datetime(2026, 5, 31, 12, 0)
    assert cron.should_run(dt) is True
    dt2 = datetime(2026, 5, 31, 12, 1)
    assert cron.should_run(dt2) is False
    print("[PASS] Cron Should Run")


def test_cron_next_time():
    """测试Cron下一次执行时间"""
    from datetime import datetime
    cron = CronExpression("0 12 * * *")
    now = datetime(2026, 5, 31, 10, 0)
    next_t = cron.next_time(now)
    assert next_t.hour == 12
    assert next_t.minute == 0
    print("[PASS] Cron Next Time")


def test_scheduler_create():
    """测试调度器创建"""
    scheduler = TaskScheduler()
    assert scheduler is not None
    print("[PASS] Scheduler Create")


def test_schedule_once():
    """测试一次性任务"""
    scheduler = TaskScheduler()
    results = []

    def task_fn():
        results.append(1)
        return "done"

    run_at = time.time() + 0.5
    task_id = scheduler.schedule_once("once_task", task_fn, run_at=run_at)
    assert task_id is not None
    assert scheduler.get_task(task_id) is not None
    print("[PASS] Schedule Once")


def test_schedule_interval():
    """测试间隔任务"""
    scheduler = TaskScheduler()

    def task_fn():
        return "interval"

    task_id = scheduler.schedule_interval("interval_task", task_fn, interval_seconds=1.0)
    task = scheduler.get_task(task_id)
    assert task.schedule_type == ScheduleType.INTERVAL
    assert task.interval_seconds == 1.0
    print("[PASS] Schedule Interval")


def test_schedule_cron():
    """测试Cron任务"""
    scheduler = TaskScheduler()

    def task_fn():
        return "cron"

    task_id = scheduler.schedule_cron("cron_task", task_fn, cron_expression="0 * * * *")
    task = scheduler.get_task(task_id)
    assert task.schedule_type == ScheduleType.CRON
    assert task.cron is not None
    print("[PASS] Schedule Cron")


def test_task_execution():
    """测试任务执行"""
    scheduler = TaskScheduler()

    def task_fn():
        return 42

    task_id = scheduler.schedule_once("exec_task", task_fn, run_at=time.time())
    result = scheduler.run_now(task_id)
    assert result is not None
    assert result.status == TaskStatus.SUCCESS
    assert result.output == 42
    print("[PASS] Task Execution")


def test_task_retry():
    """测试任务重试"""
    scheduler = TaskScheduler()
    attempts = []

    def failing_task():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError("故意失败")
        return "success"

    task_id = scheduler.schedule_once(
        "retry_task", failing_task, run_at=time.time(), max_retries=3, retry_delay=0.1
    )
    result = scheduler.run_now(task_id)
    assert result is not None
    assert result.status == TaskStatus.SUCCESS
    assert result.retry_count == 2
    assert len(attempts) == 3
    print("[PASS] Task Retry")


def test_task_retry_exhausted():
    """测试任务重试耗尽"""
    scheduler = TaskScheduler()

    def always_fail():
        raise ValueError("总是失败")

    task_id = scheduler.schedule_once(
        "fail_task", always_fail, run_at=time.time(), max_retries=2, retry_delay=0.1
    )
    result = scheduler.run_now(task_id)
    assert result is not None
    assert result.status == TaskStatus.FAILED
    assert result.retry_count == 2
    print("[PASS] Task Retry Exhausted")


def test_task_dependencies():
    """测试任务依赖"""
    scheduler = TaskScheduler()
    order = []

    def task_a():
        order.append("a")
        return "a"

    def task_b():
        order.append("b")
        return "b"

    task_id_a = scheduler.schedule_once("dep_a", task_a, run_at=time.time())
    scheduler.run_now(task_id_a)

    task_id_b = scheduler.schedule_once("dep_b", task_b, run_at=time.time(), dependencies=[task_id_a])
    result = scheduler.run_now(task_id_b)
    assert result.status == TaskStatus.SUCCESS
    print("[PASS] Task Dependencies")


def test_task_cancel():
    """测试任务取消"""
    scheduler = TaskScheduler()

    def task_fn():
        return "done"

    task_id = scheduler.schedule_once("cancel_task", task_fn, run_at=time.time() + 100)
    assert scheduler.cancel(task_id) is True
    task = scheduler.get_task(task_id)
    assert task.status == TaskStatus.CANCELLED
    print("[PASS] Task Cancel")


def test_scheduler_start_stop():
    """测试调度器启动停止"""
    scheduler = TaskScheduler(check_interval=0.1)
    results = []

    def task_fn():
        results.append(1)
        return "done"

    scheduler.schedule_interval("loop_task", task_fn, interval_seconds=0.2)
    scheduler.start()
    time.sleep(0.6)
    scheduler.stop()
    assert len(results) >= 2
    print("[PASS] Scheduler Start Stop")


def test_task_history():
    """测试任务历史"""
    scheduler = TaskScheduler()

    def task_fn():
        return "history"

    task_id = scheduler.schedule_once("hist_task", task_fn, run_at=time.time())
    result = scheduler.run_now(task_id)
    # run_now 直接执行不经过 _run_task_wrapper，所以不会记录到 completed_tasks
    # 手动添加到历史
    scheduler._completed_tasks.append(result)
    history = scheduler.get_history(task_id=task_id)
    assert len(history) == 1
    assert history[0].status == TaskStatus.SUCCESS
    scheduler.clear_history()
    assert len(scheduler.get_history()) == 0
    print("[PASS] Task History")


def test_list_tasks():
    """测试列出任务"""
    scheduler = TaskScheduler()

    def task_fn():
        pass

    scheduler.schedule_once("t1", task_fn, run_at=time.time())
    scheduler.schedule_once("t2", task_fn, run_at=time.time())
    tasks = scheduler.list_tasks()
    assert len(tasks) == 2
    print("[PASS] List Tasks")


def test_task_with_args():
    """测试带参数的任务"""
    scheduler = TaskScheduler()

    def task_fn(a, b, c=None):
        return a + b + (c or 0)

    task_id = scheduler.schedule_once(
        "args_task", task_fn, run_at=time.time(), args=(1, 2), kwargs={"c": 3}
    )
    result = scheduler.run_now(task_id)
    assert result.output == 6
    print("[PASS] Task With Args")


def run_all_tests():
    print("=" * 50)
    print("阶段64验证：任务调度器")
    print("=" * 50)

    tests = [
        test_cron_expression_parse,
        test_cron_expression_range,
        test_cron_should_run,
        test_cron_next_time,
        test_scheduler_create,
        test_schedule_once,
        test_schedule_interval,
        test_schedule_cron,
        test_task_execution,
        test_task_retry,
        test_task_retry_exhausted,
        test_task_dependencies,
        test_task_cancel,
        test_scheduler_start_stop,
        test_task_history,
        test_list_tasks,
        test_task_with_args,
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
