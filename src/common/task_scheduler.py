"""
任务调度器模块
遵循第一性原理：时间触发与可靠性

核心功能：
1. 定时任务 - 指定时间执行
2. Cron表达式 - 灵活的时间规则
3. 任务依赖 - 任务间执行顺序
4. 任务重试 - 失败自动重试
"""

from __future__ import annotations

import re
import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from common.utils import setup_logger

logger = setup_logger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class ScheduleType(Enum):
    """调度类型"""
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    retry_count: int = 0

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "error": self.error,
        }


class CronExpression:
    """Cron表达式解析器"""

    def __init__(self, expression: str):
        self.expression = expression
        self.minute, self.hour, self.day, self.month, self.weekday = self._parse(expression)

    def _parse(self, expression: str) -> Tuple[Set[int], Set[int], Set[int], Set[int], Set[int]]:
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(f"Cron表达式需要5个字段: {expression}")
        return (
            self._parse_field(parts[0], 0, 59),
            self._parse_field(parts[1], 0, 23),
            self._parse_field(parts[2], 1, 31),
            self._parse_field(parts[3], 1, 12),
            self._parse_field(parts[4], 0, 6),
        )

    def _parse_field(self, field: str, min_val: int, max_val: int) -> Set[int]:
        result = set()
        for part in field.split(","):
            if part == "*":
                result.update(range(min_val, max_val + 1))
            elif "/" in part:
                base, step = part.split("/")
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                result.update(range(start, max_val + 1, int(step)))
            elif "-" in part:
                start, end = part.split("-")
                result.update(range(int(start), int(end) + 1))
            else:
                result.add(int(part))
        return result

    def next_time(self, from_time: Optional[datetime] = None) -> datetime:
        """计算下一次触发时间"""
        now = from_time or datetime.now()
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(366 * 24 * 60):  # 最多查一年
            if (candidate.minute in self.minute and
                candidate.hour in self.hour and
                candidate.day in self.day and
                candidate.month in self.month and
                candidate.weekday() in self.weekday):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError("无法计算下一次触发时间")

    def should_run(self, dt: datetime) -> bool:
        """判断给定时间是否应该执行"""
        return (dt.minute in self.minute and
                dt.hour in self.hour and
                dt.day in self.day and
                dt.month in self.month and
                dt.weekday() in self.weekday)


@dataclass
class ScheduledTask:
    """调度任务"""
    task_id: str
    name: str
    fn: Callable[..., Any]
    schedule_type: ScheduleType
    cron: Optional[CronExpression] = None
    interval_seconds: float = 0.0
    next_run_time: float = 0.0
    max_retries: int = 0
    retry_delay: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    last_result: Optional[TaskResult] = None
    run_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "status": self.status.value,
            "next_run_time": self.next_run_time,
            "run_count": self.run_count,
        }


class TaskScheduler:
    """任务调度器"""

    def __init__(self, max_workers: int = 4, check_interval: float = 1.0):
        self.max_workers = max_workers
        self.check_interval = check_interval
        self._tasks: Dict[str, ScheduledTask] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="scheduler_")
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._completed_tasks: List[TaskResult] = []
        self._max_completed = 1000

    def schedule_once(
        self,
        name: str,
        fn: Callable[..., Any],
        run_at: float,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        dependencies: Optional[List[str]] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """调度一次性任务"""
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            fn=fn,
            schedule_type=ScheduleType.ONCE,
            next_run_time=run_at,
            max_retries=max_retries,
            retry_delay=retry_delay,
            dependencies=dependencies or [],
            args=args or (),
            kwargs=kwargs or {},
        )
        with self._lock:
            self._tasks[task_id] = task
        logger.info(f"任务已调度 [once] {name} at {datetime.fromtimestamp(run_at)}")
        return task_id

    def schedule_interval(
        self,
        name: str,
        fn: Callable[..., Any],
        interval_seconds: float,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        dependencies: Optional[List[str]] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """调度间隔任务"""
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            fn=fn,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            next_run_time=time.time() + interval_seconds,
            max_retries=max_retries,
            retry_delay=retry_delay,
            dependencies=dependencies or [],
            args=args or (),
            kwargs=kwargs or {},
        )
        with self._lock:
            self._tasks[task_id] = task
        logger.info(f"任务已调度 [interval] {name} every {interval_seconds}s")
        return task_id

    def schedule_cron(
        self,
        name: str,
        fn: Callable[..., Any],
        cron_expression: str,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        dependencies: Optional[List[str]] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """调度Cron任务"""
        cron = CronExpression(cron_expression)
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            fn=fn,
            schedule_type=ScheduleType.CRON,
            cron=cron,
            next_run_time=cron.next_time().timestamp(),
            max_retries=max_retries,
            retry_delay=retry_delay,
            dependencies=dependencies or [],
            args=args or (),
            kwargs=kwargs or {},
        )
        with self._lock:
            self._tasks[task_id] = task
        logger.info(f"任务已调度 [cron] {name} '{cron_expression}'")
        return task_id

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.CANCELLED
                logger.info(f"任务已取消 {task_id}")
                return True
        return False

    def remove(self, task_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def _check_dependencies(self, task: ScheduledTask) -> bool:
        """检查任务依赖是否满足"""
        with self._lock:
            for dep_id in task.dependencies:
                dep_task = self._tasks.get(dep_id)
                if dep_task is None:
                    logger.warning(f"任务依赖不存在: {dep_id}")
                    return False
                if dep_task.last_result is None or dep_task.last_result.status != TaskStatus.SUCCESS:
                    return False
        return True

    def _execute_task(self, task: ScheduledTask) -> TaskResult:
        """执行任务（带重试）"""
        result = TaskResult(task_id=task.task_id, status=TaskStatus.RUNNING)
        retry_count = 0

        while retry_count <= task.max_retries:
            result.start_time = time.time()
            result.retry_count = retry_count
            task.status = TaskStatus.RUNNING if retry_count == 0 else TaskStatus.RETRYING

            try:
                output = task.fn(*task.args, **task.kwargs)
                result.status = TaskStatus.SUCCESS
                result.output = output
                result.end_time = time.time()
                task.run_count += 1
                logger.info(f"任务执行成功 [{task.name}], 耗时 {result.duration_ms:.2f}ms")
                return result
            except Exception as e:
                result.error = f"{e}\n{traceback.format_exc()}"
                result.end_time = time.time()
                logger.error(f"任务执行失败 [{task.name}] (重试 {retry_count}/{task.max_retries}): {e}")

                if retry_count < task.max_retries:
                    retry_count += 1
                    time.sleep(task.retry_delay)
                else:
                    result.status = TaskStatus.FAILED
                    task.run_count += 1
                    return result

        return result

    def _run_scheduler_loop(self) -> None:
        """调度器主循环"""
        while not self._stop_event.is_set():
            now = time.time()
            tasks_to_run = []

            with self._lock:
                for task in self._tasks.values():
                    if task.status == TaskStatus.CANCELLED:
                        continue
                    if now >= task.next_run_time and self._check_dependencies(task):
                        tasks_to_run.append(task)

            for task in tasks_to_run:
                self._executor.submit(self._run_task_wrapper, task)

            self._stop_event.wait(self.check_interval)

    def _run_task_wrapper(self, task: ScheduledTask) -> None:
        """任务执行包装器"""
        result = self._execute_task(task)
        task.last_result = result
        task.status = result.status

        with self._lock:
            self._completed_tasks.append(result)
            if len(self._completed_tasks) > self._max_completed:
                self._completed_tasks.pop(0)

        # 更新下次执行时间
        if task.schedule_type == ScheduleType.INTERVAL and result.status == TaskStatus.SUCCESS:
            task.next_run_time = time.time() + task.interval_seconds
        elif task.schedule_type == ScheduleType.CRON and result.status == TaskStatus.SUCCESS:
            task.next_run_time = task.cron.next_time().timestamp()

    def start(self) -> None:
        """启动调度器"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_scheduler_loop, daemon=True, name="task_scheduler")
        self._thread.start()
        logger.info("任务调度器已启动")

    def stop(self) -> None:
        """停止调度器"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._executor.shutdown(wait=True)
        logger.info("任务调度器已停止")

    def run_now(self, task_id: str) -> Optional[TaskResult]:
        """立即执行任务"""
        task = self.get_task(task_id)
        if task is None:
            return None
        return self._execute_task(task)

    def get_history(self, task_id: Optional[str] = None, limit: int = 100) -> List[TaskResult]:
        """获取执行历史"""
        with self._lock:
            results = self._completed_tasks
            if task_id:
                results = [r for r in results if r.task_id == task_id]
            return results[-limit:]

    def clear_history(self) -> None:
        """清空历史"""
        with self._lock:
            self._completed_tasks.clear()


# 便捷函数
def get_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    return TaskScheduler()
