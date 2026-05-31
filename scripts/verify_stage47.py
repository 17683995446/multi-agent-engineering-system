import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.performance_metrics import PerformanceProfiler, BenchmarkRunner, PerformanceReport


def test_profiler_init():
    profiler = PerformanceProfiler()
    assert profiler is not None
    assert profiler.records == []
    print("[PASS] test_profiler_init")


def test_profile_decorator():
    profiler = PerformanceProfiler()

    @profiler.profile
    def sample_func(n):
        total = 0
        for i in range(n):
            total += i
        return total

    result = sample_func(1000)
    assert result == sum(range(1000))
    assert len(profiler.records) >= 1
    record = profiler.records[0]
    assert record.name.endswith("sample_func")
    assert record.duration_ms >= 0
    assert record.memory_delta_mb is not None
    print("[PASS] test_profile_decorator")


def test_memory_monitoring():
    profiler = PerformanceProfiler()

    @profiler.profile
    def allocate_memory():
        data = [0] * 100000
        return data

    allocate_memory()
    assert len(profiler.records) == 1
    record = profiler.records[0]
    assert record.memory_before_mb >= 0
    assert record.memory_after_mb >= 0
    print("[PASS] test_memory_monitoring")


def test_benchmark_runner():
    profiler = PerformanceProfiler()
    runner = BenchmarkRunner(profiler=profiler)

    def work():
        return sum(range(100))

    summary = runner.run(work, iterations=20, warmup=2)
    assert "iterations" in summary
    assert summary["iterations"] == 20
    assert "avg_duration_ms" in summary
    assert summary["avg_duration_ms"] >= 0
    print("[PASS] test_benchmark_runner")


def test_performance_report():
    profiler = PerformanceProfiler()

    @profiler.profile
    def slow_func():
        time.sleep(0.01)
        return 42

    slow_func()
    report = PerformanceReport(profiler)
    text = report.generate_text()
    assert "Performance Report" in text
    assert "Total Records" in text
    json_str = report.generate_json()
    assert "summary" in json_str
    print("[PASS] test_performance_report")


def test_bottleneck_identification():
    profiler = PerformanceProfiler()

    @profiler.profile
    def fast():
        return 1

    @profiler.profile
    def slow():
        time.sleep(0.02)
        return 2

    for _ in range(5):
        fast()
    for _ in range(3):
        slow()

    bottlenecks = profiler.identify_bottlenecks(top_n=2)
    assert len(bottlenecks) <= 2
    if bottlenecks:
        assert "name" in bottlenecks[0]
        assert "total_duration_ms" in bottlenecks[0]
    print("[PASS] test_bottleneck_identification")


def test_throughput():
    profiler = PerformanceProfiler()
    runner = BenchmarkRunner(profiler=profiler)

    def noop():
        return 1

    summary = runner.run(noop, iterations=10, warmup=1)
    assert summary["iterations"] == 10
    print("[PASS] test_throughput")


def main():
    print("=" * 50)
    print("Stage 47 Verification: Performance Metrics")
    print("=" * 50)
    test_profiler_init()
    test_profile_decorator()
    test_memory_monitoring()
    test_benchmark_runner()
    test_performance_report()
    test_bottleneck_identification()
    test_throughput()
    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
