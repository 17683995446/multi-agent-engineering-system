import functools
import time
import tracemalloc
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar
from collections import defaultdict
import json
from datetime import datetime

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class MetricRecord:
    name: str
    start_time: float
    end_time: float
    duration_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    cpu_percent: Optional[float] = None
    throughput: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    def __init__(self):
        self.records: List[MetricRecord] = []
        self._lock = threading.Lock()
        self._trace_started = False

    def _start_trace(self):
        if not self._trace_started:
            tracemalloc.start()
            self._trace_started = True

    def _get_cpu_percent(self) -> Optional[float]:
        try:
            import psutil
            return psutil.Process(os.getpid()).cpu_percent(interval=None)
        except Exception:
            return None

    def _get_memory_mb(self) -> float:
        if self._trace_started:
            current, _ = tracemalloc.get_traced_memory()
            return current / (1024 * 1024)
        try:
            import psutil
            return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def record(self, name: str, duration_ms: float, memory_before_mb: float,
               memory_after_mb: float, cpu_percent: Optional[float] = None,
               throughput: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> MetricRecord:
        record = MetricRecord(
            name=name,
            start_time=time.time() - duration_ms / 1000.0,
            end_time=time.time(),
            duration_ms=duration_ms,
            memory_before_mb=memory_before_mb,
            memory_after_mb=memory_after_mb,
            memory_delta_mb=memory_after_mb - memory_before_mb,
            cpu_percent=cpu_percent,
            throughput=throughput,
            metadata=metadata or {},
        )
        with self._lock:
            self.records.append(record)
        return record

    def profile(self, func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._start_trace()
            mem_before = self._get_memory_mb()
            cpu_before = self._get_cpu_percent()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            finally:
                end = time.perf_counter()
                mem_after = self._get_memory_mb()
                cpu_after = self._get_cpu_percent()
                duration_ms = (end - start) * 1000.0
                cpu = cpu_after if cpu_after is not None else cpu_before
                self.record(
                    name=func.__qualname__,
                    duration_ms=duration_ms,
                    memory_before_mb=mem_before,
                    memory_after_mb=mem_after,
                    cpu_percent=cpu,
                    metadata={"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
                )
            return result
        return wrapper  # type: ignore[return-value]

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self.records)
        if not records:
            return {}
        durations = [r.duration_ms for r in records]
        memories = [r.memory_delta_mb for r in records]
        return {
            "total_records": len(records),
            "total_duration_ms": sum(durations),
            "avg_duration_ms": sum(durations) / len(durations),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "avg_memory_delta_mb": sum(memories) / len(memories) if memories else 0.0,
            "max_memory_delta_mb": max(memories) if memories else 0.0,
        }

    def identify_bottlenecks(self, top_n: int = 5) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self.records)
        grouped: Dict[str, List[MetricRecord]] = defaultdict(list)
        for r in records:
            grouped[r.name].append(r)
        stats = []
        for name, items in grouped.items():
            durations = [i.duration_ms for i in items]
            mems = [i.memory_delta_mb for i in items]
            stats.append({
                "name": name,
                "call_count": len(items),
                "total_duration_ms": sum(durations),
                "avg_duration_ms": sum(durations) / len(durations),
                "max_duration_ms": max(durations),
                "avg_memory_delta_mb": sum(mems) / len(mems),
                "max_memory_delta_mb": max(mems),
            })
        stats.sort(key=lambda x: x["total_duration_ms"], reverse=True)
        return stats[:top_n]

    def reset(self):
        with self._lock:
            self.records.clear()


class BenchmarkRunner:
    def __init__(self, profiler: Optional[PerformanceProfiler] = None):
        self.profiler = profiler or PerformanceProfiler()

    def run(self, func: Callable[[], Any], iterations: int = 100, warmup: int = 10) -> Dict[str, Any]:
        for _ in range(warmup):
            func()
        self.profiler.reset()
        for i in range(iterations):
            mem_before = self.profiler._get_memory_mb()
            start = time.perf_counter()
            result = func()
            end = time.perf_counter()
            mem_after = self.profiler._get_memory_mb()
            duration_ms = (end - start) * 1000.0
            throughput = 1000.0 / duration_ms if duration_ms > 0 else None
            self.profiler.record(
                name=func.__qualname__ if hasattr(func, "__qualname__") else "benchmark_func",
                duration_ms=duration_ms,
                memory_before_mb=mem_before,
                memory_after_mb=mem_after,
                throughput=throughput,
                metadata={"iteration": i},
            )
        summary = self.profiler.get_summary()
        summary["iterations"] = iterations
        summary["warmup"] = warmup
        return summary

    def compare(self, candidates: Dict[str, Callable[[], Any]], iterations: int = 100, warmup: int = 10) -> Dict[str, Any]:
        results = {}
        for name, func in candidates.items():
            runner = BenchmarkRunner()
            results[name] = runner.run(func, iterations=iterations, warmup=warmup)
        return results


class PerformanceReport:
    def __init__(self, profiler: PerformanceProfiler):
        self.profiler = profiler

    def generate_text(self) -> str:
        summary = self.profiler.get_summary()
        bottlenecks = self.profiler.identify_bottlenecks(top_n=5)
        lines = [
            "=" * 60,
            "Performance Report",
            "=" * 60,
            f"Generated at: {datetime.now().isoformat()}",
            "",
            "[Summary]",
            f"  Total Records: {summary.get('total_records', 0)}",
            f"  Total Duration (ms): {summary.get('total_duration_ms', 0):.4f}",
            f"  Avg Duration (ms): {summary.get('avg_duration_ms', 0):.4f}",
            f"  Max Duration (ms): {summary.get('max_duration_ms', 0):.4f}",
            f"  Min Duration (ms): {summary.get('min_duration_ms', 0):.4f}",
            f"  Avg Memory Delta (MB): {summary.get('avg_memory_delta_mb', 0):.4f}",
            f"  Max Memory Delta (MB): {summary.get('max_memory_delta_mb', 0):.4f}",
            "",
            "[Top Bottlenecks]",
        ]
        for idx, b in enumerate(bottlenecks, start=1):
            lines.append(f"  {idx}. {b['name']}")
            lines.append(f"     Calls: {b['call_count']}, Total: {b['total_duration_ms']:.4f} ms, Avg: {b['avg_duration_ms']:.4f} ms, MaxMemDelta: {b['max_memory_delta_mb']:.4f} MB")
        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_json(self) -> str:
        summary = self.profiler.get_summary()
        bottlenecks = self.profiler.identify_bottlenecks(top_n=5)
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "bottlenecks": bottlenecks,
            "records": [
                {
                    "name": r.name,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "duration_ms": r.duration_ms,
                    "memory_before_mb": r.memory_before_mb,
                    "memory_after_mb": r.memory_after_mb,
                    "memory_delta_mb": r.memory_delta_mb,
                    "cpu_percent": r.cpu_percent,
                    "throughput": r.throughput,
                    "metadata": r.metadata,
                }
                for r in self.profiler.records
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save(self, path: str, fmt: str = "text"):
        if fmt == "json":
            content = self.generate_json()
        else:
            content = self.generate_text()
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
