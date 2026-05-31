#!/usr/bin/env python3
"""
阶段53验证脚本：异常处理增强

测试内容：
1. 异常分类
2. 异常记录与统计
3. 安全执行装饰器
4. 重试装饰器
5. 降级装饰器
6. 全局异常钩子
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.exception_handler import (
    ExceptionCategory,
    ExceptionClassifier,
    ExceptionHandler,
    RecoveryStrategy,
    install_global_handler,
    retry,
    safe_execute,
    with_fallback,
)


def test_exception_classification() -> bool:
    print("[Test] 异常分类")
    try:
        assert ExceptionClassifier.classify(ConnectionError("fail")) == ExceptionCategory.TRANSIENT
        assert ExceptionClassifier.classify(ValueError("bad")) == ExceptionCategory.VALIDATION
        assert ExceptionClassifier.classify(MemoryError("oom")) == ExceptionCategory.RESOURCE
        assert ExceptionClassifier.classify(RuntimeError("unknown")) == ExceptionCategory.UNKNOWN
        print("  ✓ 异常分类正确")
        print("[Pass] 异常分类\n")
        return True
    except Exception as e:
        print(f"[Fail] 异常分类: {e}\n")
        return False


def test_exception_record_and_stats() -> bool:
    print("[Test] 异常记录与统计")
    try:
        ExceptionHandler._instance = None
        handler = ExceptionHandler()
        handler.clear_records()

        try:
            raise ValueError("test error")
        except Exception as e:
            record = handler.record(e, context={"module": "test"}, recovered=False)
            assert record.exception_type == "ValueError"
            assert record.category == ExceptionCategory.VALIDATION
            assert record.context["module"] == "test"
            print("  ✓ 异常记录正确")

        stats = handler.get_statistics()
        assert stats["total"] >= 1
        assert stats["by_category"]["validation"] >= 1
        print(f"  ✓ 异常统计正确: {stats}")

        records = handler.get_records(category=ExceptionCategory.VALIDATION)
        assert len(records) >= 1
        print("  ✓ 按分类查询记录正确")

        print("[Pass] 异常记录与统计\n")
        return True
    except Exception as e:
        print(f"[Fail] 异常记录与统计: {e}\n")
        return False


def test_safe_execute() -> bool:
    print("[Test] 安全执行装饰器")
    try:
        @safe_execute(fallback="fallback_value")
        def fail_func():
            raise RuntimeError("always fail")

        result = fail_func()
        assert result == "fallback_value"
        print("  ✓ fallback 值正确")

        def fallback_fn():
            return "from_func"

        @safe_execute(fallback_func=fallback_fn)
        def fail_func2():
            raise RuntimeError("fail")

        assert fail_func2() == "from_func"
        print("  ✓ fallback 函数正确")

        @safe_execute(default_on_error="default")
        def fail_func3():
            raise RuntimeError("fail")

        assert fail_func3() == "default"
        print("  ✓ default_on_error 正确")

        print("[Pass] 安全执行装饰器\n")
        return True
    except Exception as e:
        print(f"[Fail] 安全执行装饰器: {e}\n")
        return False


def test_retry_decorator() -> bool:
    print("[Test] 重试装饰器")
    try:
        attempt_count = 0

        @retry(max_retries=2, delay=0.05, exceptions=(RuntimeError,))
        def flaky_success():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError("temp fail")
            return "ok"

        result = flaky_success()
        assert result == "ok"
        assert attempt_count == 3
        print(f"  ✓ 重试后成功，尝试 {attempt_count} 次")

        # 最终失败的情况
        @retry(max_retries=1, delay=0.05, exceptions=(RuntimeError,))
        def always_fail():
            raise RuntimeError("always")

        try:
            always_fail()
            assert False, "应该抛出异常"
        except RuntimeError:
            print("  ✓ 超过重试次数后正确抛出异常")

        print("[Pass] 重试装饰器\n")
        return True
    except Exception as e:
        print(f"[Fail] 重试装饰器: {e}\n")
        return False


def test_with_fallback() -> bool:
    print("[Test] 降级装饰器")
    try:
        def fallback():
            return "fallback_result"

        @with_fallback(fallback)
        def primary():
            raise Exception("primary fail")

        assert primary() == "fallback_result"
        print("  ✓ 降级执行结果正确")

        @with_fallback(fallback)
        def primary_ok():
            return "primary_ok"

        assert primary_ok() == "primary_ok"
        print("  ✓ 主逻辑正常时不触发降级")

        print("[Pass] 降级装饰器\n")
        return True
    except Exception as e:
        print(f"[Fail] 降级装饰器: {e}\n")
        return False


def test_global_hook() -> bool:
    print("[Test] 全局异常钩子")
    try:
        install_global_handler()
        # 仅验证安装不报错
        print("  ✓ 全局异常钩子安装成功")
        print("[Pass] 全局异常钩子\n")
        return True
    except Exception as e:
        print(f"[Fail] 全局异常钩子: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段53验证脚本：异常处理增强")
    print("=" * 60 + "\n")

    results = []
    results.append(("异常分类", test_exception_classification()))
    results.append(("异常记录与统计", test_exception_record_and_stats()))
    results.append(("安全执行装饰器", test_safe_execute()))
    results.append(("重试装饰器", test_retry_decorator()))
    results.append(("降级装饰器", test_with_fallback()))
    results.append(("全局异常钩子", test_global_hook()))

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
        print("🎉 所有测试通过！阶段53验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
