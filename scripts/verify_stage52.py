#!/usr/bin/env python3
"""
阶段52验证脚本：日志系统增强

测试内容：
1. 结构化日志（JSON）
2. 日志轮转（按大小）
3. 异步日志
4. 日志分级
5. 日志管理器
6. 上下文注入
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.logging_enhanced import (
    EnhancedLogger,
    JSONFormatter,
    LogFormat,
    LogLevel,
    LogManager,
    StructuredLogRecord,
)


def test_structured_log() -> bool:
    print("[Test] 结构化日志（JSON）")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EnhancedLogger(
                "test_json",
                level=LogLevel.INFO,
                log_format=LogFormat.JSON,
                log_dir=tmpdir,
                enable_console=False,
            )
            logger.info("测试消息", user_id="123", action="login")
            logger.close()

            log_file = os.path.join(tmpdir, "test_json.log")
            assert os.path.exists(log_file)
            with open(log_file, "r", encoding="utf-8") as f:
                line = f.readline().strip()
            record = json.loads(line)
            assert record["message"] == "测试消息"
            assert record["level"] == "INFO"
            assert record["extra"]["user_id"] == "123"
            assert record["extra"]["action"] == "login"
            print("  ✓ JSON 结构化日志格式正确")

            # StructuredLogRecord 测试
            sr = StructuredLogRecord(
                timestamp="2026-05-31T10:00:00",
                level="INFO",
                logger="test",
                message="hello",
                thread="MainThread",
            )
            assert "hello" in sr.to_json()
            print("  ✓ StructuredLogRecord 序列化正确")

        print("[Pass] 结构化日志\n")
        return True
    except Exception as e:
        print(f"[Fail] 结构化日志: {e}\n")
        return False


def test_log_rotation() -> bool:
    print("[Test] 日志轮转（按大小）")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EnhancedLogger(
                "test_rotate",
                level=LogLevel.INFO,
                log_format=LogFormat.TEXT,
                log_dir=tmpdir,
                enable_console=False,
                rotate_by_size=True,
                max_bytes=512,
                backup_count=3,
            )
            for i in range(200):
                logger.info(f"测试日志轮转消息内容填充 {i}")
            logger.close()

            log_files = list(os.listdir(tmpdir))
            rotate_files = [f for f in log_files if "test_rotate" in f]
            assert len(rotate_files) > 1, f"期望多个轮转文件，实际 {rotate_files}"
            print(f"  ✓ 日志轮转文件数: {len(rotate_files)}")

        print("[Pass] 日志轮转\n")
        return True
    except Exception as e:
        print(f"[Fail] 日志轮转: {e}\n")
        return False


def test_async_logging() -> bool:
    print("[Test] 异步日志")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EnhancedLogger(
                "test_async",
                level=LogLevel.INFO,
                log_format=LogFormat.TEXT,
                log_dir=tmpdir,
                enable_console=False,
                enable_async=True,
            )
            for i in range(100):
                logger.info(f"异步日志消息 {i}")
            logger.flush()
            dropped = logger.get_dropped_count()
            logger.close()

            log_file = os.path.join(tmpdir, "test_async.log")
            assert os.path.exists(log_file)
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 100, f"期望100条日志，实际{len(lines)}"
            assert dropped == 0
            print(f"  ✓ 异步日志写入100条，丢弃{dropped}条")

        print("[Pass] 异步日志\n")
        return True
    except Exception as e:
        print(f"[Fail] 异步日志: {e}\n")
        return False


def test_log_levels() -> bool:
    print("[Test] 日志分级")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EnhancedLogger(
                "test_level",
                level=LogLevel.WARNING,
                log_format=LogFormat.TEXT,
                log_dir=tmpdir,
                enable_console=False,
            )
            logger.debug("debug_msg")
            logger.info("info_msg")
            logger.warning("warning_msg")
            logger.error("error_msg")
            logger.critical("critical_msg")
            logger.close()

            log_file = os.path.join(tmpdir, "test_level.log")
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "debug_msg" not in content
            assert "info_msg" not in content
            assert "warning_msg" in content
            assert "error_msg" in content
            assert "critical_msg" in content
            print("  ✓ 日志分级过滤正确")

            # 动态调整级别
            logger2 = EnhancedLogger(
                "test_level2",
                level=LogLevel.ERROR,
                log_format=LogFormat.TEXT,
                log_dir=tmpdir,
                enable_console=False,
            )
            logger2.set_level(LogLevel.DEBUG)
            logger2.debug("now_debug")
            logger2.close()
            with open(os.path.join(tmpdir, "test_level2.log"), "r", encoding="utf-8") as f:
                content = f.read()
            assert "now_debug" in content
            print("  ✓ 动态调整日志级别正确")

        print("[Pass] 日志分级\n")
        return True
    except Exception as e:
        print(f"[Fail] 日志分级: {e}\n")
        return False


def test_log_manager() -> bool:
    print("[Test] 日志管理器")
    try:
        LogManager._instance = None
        manager = LogManager()

        logger1 = manager.get_logger("mgr_1", level=LogLevel.INFO)
        logger2 = manager.get_logger("mgr_2", level=LogLevel.DEBUG)
        assert logger1 is not None
        assert logger2 is not None
        print("  ✓ 日志器创建成功")

        status = manager.get_status()
        assert status["logger_count"] == 2
        assert "mgr_1" in status["logger_names"]
        print(f"  ✓ 日志管理器状态: {status}")

        manager.set_global_level(LogLevel.ERROR)
        assert logger1.level == LogLevel.ERROR
        assert logger2.level == LogLevel.ERROR
        print("  ✓ 全局日志级别设置成功")

        manager.remove_logger("mgr_1")
        status = manager.get_status()
        assert status["logger_count"] == 1
        print("  ✓ 日志器移除成功")

        print("[Pass] 日志管理器\n")
        return True
    except Exception as e:
        print(f"[Fail] 日志管理器: {e}\n")
        return False


def test_context_injection() -> bool:
    print("[Test] 上下文注入")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EnhancedLogger(
                "test_ctx",
                level=LogLevel.INFO,
                log_format=LogFormat.JSON,
                log_dir=tmpdir,
                enable_console=False,
            )
            logger.add_context(request_id="req-001", trace_id="trace-123")
            logger.info("带上下文的消息")
            logger.clear_context()
            logger.info("无上下文的消息")
            logger.close()

            log_file = os.path.join(tmpdir, "test_ctx.log")
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            ctx_record = json.loads(lines[0])
            assert ctx_record["extra"]["request_id"] == "req-001"
            assert ctx_record["extra"]["trace_id"] == "trace-123"
            print("  ✓ 上下文注入正确")

            plain_record = json.loads(lines[1])
            assert "request_id" not in plain_record.get("extra", {})
            print("  ✓ 上下文清除正确")

        print("[Pass] 上下文注入\n")
        return True
    except Exception as e:
        print(f"[Fail] 上下文注入: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段52验证脚本：日志系统增强")
    print("=" * 60 + "\n")

    results = []
    results.append(("结构化日志", test_structured_log()))
    results.append(("日志轮转", test_log_rotation()))
    results.append(("异步日志", test_async_logging()))
    results.append(("日志分级", test_log_levels()))
    results.append(("日志管理器", test_log_manager()))
    results.append(("上下文注入", test_context_injection()))

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
        print("🎉 所有测试通过！阶段52验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
