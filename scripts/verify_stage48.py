#!/usr/bin/env python3
"""阶段48验收验证脚本 - 测试增强CLI模块。"""

from __future__ import annotations

import io
import sys
import time
from typing import Any

sys.path.insert(0, "/workspace/src")

from common.cli_enhanced import (
    Choice,
    ColorCode,
    ColorOutput,
    ColumnDef,
    EnhancedCLI,
    InteractivePrompt,
    ProgressBar,
    ProgressConfig,
    TableConfig,
    TableFormatter,
)


def test_color_output() -> None:
    print("[Test] ColorOutput")
    # 在非TTY环境中强制启用以测试颜色功能
    color = ColorOutput(enabled=True)
    color.enable()
    assert color.colorize("hello", ColorCode.RED) != "hello"
    assert color.red("test") != "test"
    assert color.green("test") != "test"
    assert color.yellow("test") != "test"
    assert color.blue("test") != "test"
    assert color.cyan("test") != "test"
    assert color.magenta("test") != "test"
    assert color.bold("test") != "test"

    color.disable()
    assert color.colorize("hello", ColorCode.RED) == "hello"
    assert color.red("test") == "test"

    color.enable()
    assert color.colorize("hello", ColorCode.RED) != "hello"
    print("  ✓ ColorOutput 测试通过")


def test_progress_bar() -> None:
    print("[Test] ProgressBar")
    config = ProgressConfig(width=10, show_percentage=True, show_count=True)
    pb = ProgressBar(total=5, config=config)
    assert pb.total == 5
    assert pb.current == 0
    assert pb.percentage == 0.0

    pb.start()
    assert pb._started is True

    pb.update(2)
    assert pb.current == 2
    assert pb.percentage == 40.0

    pb.set_progress(4)
    assert pb.current == 4

    pb.finish()
    assert pb._finished is True

    # context manager
    with ProgressBar(total=3, config=config) as p:
        p.update(1)
        p.update(1)
        p.update(1)
    print("  ✓ ProgressBar 测试通过")


def test_progress_bar_iter() -> None:
    print("[Test] ProgressBar iter")
    config = ProgressConfig(width=5)
    pb = ProgressBar(total=3, config=config)
    items = list(pb.iter(iter([1, 2, 3])))
    assert items == [1, 2, 3]
    assert pb._finished is True
    print("  ✓ ProgressBar iter 测试通过")


def test_progress_bar_validation() -> None:
    print("[Test] ProgressBar validation")
    try:
        ProgressBar(total=0)
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "positive" in str(e)
    print("  ✓ ProgressBar validation 测试通过")


def test_table_formatter() -> None:
    print("[Test] TableFormatter")
    columns = [
        ColumnDef(name="Name", width=10),
        ColumnDef(name="Age", width=5, align="right"),
        ColumnDef(name="City", width=10),
    ]
    config = TableConfig(columns=columns)
    table = TableFormatter(config=config)
    table.add_row(["Alice", "30", "Beijing"])
    table.add_row(["Bob", "25", "Shanghai"])

    rendered = table.render()
    assert "Alice" in rendered
    assert "Beijing" in rendered
    assert "┌" in rendered
    assert "┘" in rendered

    table.clear()
    assert table._rows == []
    print("  ✓ TableFormatter 测试通过")


def test_table_formatter_validation() -> None:
    print("[Test] TableFormatter validation")
    columns = [ColumnDef(name="A", width=5)]
    config = TableConfig(columns=columns)
    table = TableFormatter(config=config)
    try:
        table.add_row(["a", "b"])
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "does not match" in str(e)
    print("  ✓ TableFormatter validation 测试通过")


def test_interactive_prompt_confirm(monkeypatch: Any = None) -> None:
    print("[Test] InteractivePrompt confirm")
    prompt = InteractivePrompt(color_output=ColorOutput(enabled=False))

    # simulate EOF -> default
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("")
    result = prompt.confirm("Continue", default=True)
    sys.stdin = old_stdin
    assert result is True

    sys.stdin = io.StringIO("n")
    result = prompt.confirm("Continue", default=True)
    sys.stdin = old_stdin
    assert result is False

    sys.stdin = io.StringIO("y")
    result = prompt.confirm("Continue", default=False)
    sys.stdin = old_stdin
    assert result is True
    print("  ✓ InteractivePrompt confirm 测试通过")


def test_interactive_prompt_select() -> None:
    print("[Test] InteractivePrompt select")
    prompt = InteractivePrompt(color_output=ColorOutput(enabled=False))
    choices = [
        Choice("1", "Option A", "a"),
        Choice("2", "Option B", "b"),
    ]
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("2")
    result = prompt.select("Choose", choices)
    sys.stdin = old_stdin
    assert result == "b"
    print("  ✓ InteractivePrompt select 测试通过")


def test_interactive_prompt_input_text() -> None:
    print("[Test] InteractivePrompt input_text")
    prompt = InteractivePrompt(color_output=ColorOutput(enabled=False))
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("hello")
    result = prompt.input_text("Enter name")
    sys.stdin = old_stdin
    assert result == "hello"

    sys.stdin = io.StringIO("")
    result = prompt.input_text("Enter name", default="world")
    sys.stdin = old_stdin
    assert result == "world"
    print("  ✓ InteractivePrompt input_text 测试通过")


def test_interactive_prompt_input_number() -> None:
    print("[Test] InteractivePrompt input_number")
    prompt = InteractivePrompt(color_output=ColorOutput(enabled=False))
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("42")
    result = prompt.input_number("Enter number", integer=True)
    sys.stdin = old_stdin
    assert result == 42

    sys.stdin = io.StringIO("3.14")
    result = prompt.input_number("Enter number")
    sys.stdin = old_stdin
    assert result == 3.14
    print("  ✓ InteractivePrompt input_number 测试通过")


def test_interactive_prompt_multi_select() -> None:
    print("[Test] InteractivePrompt multi_select")
    prompt = InteractivePrompt(color_output=ColorOutput(enabled=False))
    choices = [
        Choice("a", "Apple", "apple"),
        Choice("b", "Banana", "banana"),
        Choice("c", "Cherry", "cherry"),
    ]
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("a,c")
    result = prompt.multi_select("Select fruits", choices)
    sys.stdin = old_stdin
    assert set(result) == {"apple", "cherry"}

    sys.stdin = io.StringIO("all")
    result = prompt.multi_select("Select fruits", choices)
    sys.stdin = old_stdin
    assert set(result) == {"apple", "banana", "cherry"}
    print("  ✓ InteractivePrompt multi_select 测试通过")


def test_enhanced_cli_init() -> None:
    print("[Test] EnhancedCLI init")
    cli = EnhancedCLI(color_enabled=False)
    assert cli.color is not None
    assert cli.table is not None
    assert cli.prompt is not None
    print("  ✓ EnhancedCLI init 测试通过")


def test_enhanced_cli_progress() -> None:
    print("[Test] EnhancedCLI progress")
    cli = EnhancedCLI(color_enabled=False)
    pb = cli.create_progress(total=10)
    assert isinstance(pb, ProgressBar)
    pb.update(5)
    assert pb.current == 5
    pb.finish()
    print("  ✓ EnhancedCLI progress 测试通过")


def test_enhanced_cli_table() -> None:
    print("[Test] EnhancedCLI table")
    cli = EnhancedCLI(color_enabled=False)
    table = cli.create_table()
    assert isinstance(table, TableFormatter)
    columns = [
        ColumnDef(name="ID", width=5),
        ColumnDef(name="Value", width=10),
    ]
    table.set_columns(columns)
    table.add_row(["1", "test"])
    rendered = table.render()
    assert "ID" in rendered
    assert "test" in rendered
    print("  ✓ EnhancedCLI table 测试通过")


def test_enhanced_cli_spinner() -> None:
    print("[Test] EnhancedCLI spinner")
    cli = EnhancedCLI(color_enabled=False)

    def slow_task() -> str:
        time.sleep(0.15)
        return "done"

    result = cli.spinner("Working...", slow_task)
    assert result == "done"
    print("  ✓ EnhancedCLI spinner 测试通过")


def test_enhanced_cli_box() -> None:
    print("[Test] EnhancedCLI box")
    cli = EnhancedCLI(color_enabled=False)
    # capture output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    cli.box("Hello\nWorld", color=ColorCode.GREEN)
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    assert "Hello" in output
    assert "World" in output
    print("  ✓ EnhancedCLI box 测试通过")


def test_enhanced_cli_messages() -> None:
    print("[Test] EnhancedCLI messages")
    cli = EnhancedCLI(color_enabled=False)
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    cli.success("ok")
    cli.error("fail")
    cli.warning("warn")
    cli.info("info")
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    assert "ok" in output
    assert "fail" in output
    assert "warn" in output
    assert "info" in output
    print("  ✓ EnhancedCLI messages 测试通过")


def main() -> int:
    print("=" * 60)
    print("阶段48 验收验证 - 增强CLI模块")
    print("=" * 60)

    tests = [
        test_color_output,
        test_progress_bar,
        test_progress_bar_iter,
        test_progress_bar_validation,
        test_table_formatter,
        test_table_formatter_validation,
        test_interactive_prompt_confirm,
        test_interactive_prompt_select,
        test_interactive_prompt_input_text,
        test_interactive_prompt_input_number,
        test_interactive_prompt_multi_select,
        test_enhanced_cli_init,
        test_enhanced_cli_progress,
        test_enhanced_cli_table,
        test_enhanced_cli_spinner,
        test_enhanced_cli_box,
        test_enhanced_cli_messages,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__} 失败: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed} / 失败 {failed} / 总计 {passed + failed}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
