#!/usr/bin/env python3
"""
阶段69验证脚本：命令模式

测试内容：
1. 命令封装
2. 命令队列
3. 撤销/重做
4. 宏命令
5. 函数命令
6. 命令调用器
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.command_pattern import (
    Command,
    CommandException,
    CommandInvoker,
    CommandQueue,
    FunctionCommand,
    MacroCommand,
    UndoableCommand,
    UndoableFunctionCommand,
)


class IncrementCommand(UndoableCommand):
    """测试用增量命令"""

    def __init__(self, target: List[int], amount: int = 1):
        super().__init__("Increment")
        self.target = target
        self.amount = amount
        self.previous = 0

    def execute(self) -> int:
        self.previous = self.target[0]
        self.target[0] += self.amount
        return self.target[0]

    def undo(self) -> int:
        self.target[0] = self.previous
        return self.target[0]


class SetCommand(UndoableCommand):
    """测试用设置命令"""

    def __init__(self, target: List[int], value: int):
        super().__init__("Set")
        self.target = target
        self.value = value
        self.previous = 0

    def execute(self) -> int:
        self.previous = self.target[0]
        self.target[0] = self.value
        return self.target[0]

    def undo(self) -> int:
        self.target[0] = self.previous
        return self.target[0]


def test_command_encapsulation() -> bool:
    print("[Test] 命令封装")
    try:
        value = [0]
        cmd = IncrementCommand(value, 5)

        assert cmd.name == "Increment"
        assert not cmd.executed
        print("  ✓ 命令初始化正确")

        result = cmd.run()
        assert result == 5
        assert value[0] == 5
        assert cmd.executed
        assert cmd.execution_time_ms >= 0
        print(f"  ✓ 命令执行: value={value[0]}, time={cmd.execution_time_ms:.3f}ms")

        # 不可撤销命令
        class SimpleCommand(Command):
            def execute(self):
                return 42

        simple = SimpleCommand()
        assert not simple.can_undo()
        try:
            simple.undo()
            assert False, "应该抛出异常"
        except CommandException:
            print("  ✓ 不可撤销命令抛出异常")

        print("[Pass] 命令封装\n")
        return True
    except Exception as e:
        print(f"[Fail] 命令封装: {e}\n")
        return False


def test_command_queue() -> bool:
    print("[Test] 命令队列")
    try:
        queue = CommandQueue()
        value = [0]

        # 入队
        queue.enqueue(IncrementCommand(value, 1))
        queue.enqueue(IncrementCommand(value, 2))
        queue.enqueue(IncrementCommand(value, 3))
        assert queue.size() == 3
        print("  ✓ 命令入队")

        # 执行所有
        results = queue.execute_all()
        assert results == [1, 3, 6]
        assert value[0] == 6
        assert queue.size() == 0
        print(f"  ✓ 队列执行结果: {results}")

        # 清空
        queue.clear()
        assert queue.size() == 0
        print("  ✓ 队列清空")

        # 队列满
        small_queue = CommandQueue(max_size=2)
        small_queue.enqueue(IncrementCommand(value, 1))
        small_queue.enqueue(IncrementCommand(value, 1))
        try:
            small_queue.enqueue(IncrementCommand(value, 1))
            assert False, "应该抛出异常"
        except CommandException:
            print("  ✓ 队列满时抛出异常")

        print("[Pass] 命令队列\n")
        return True
    except Exception as e:
        print(f"[Fail] 命令队列: {e}\n")
        return False


def test_undo_redo() -> bool:
    print("[Test] 撤销/重做")
    try:
        queue = CommandQueue()
        value = [0]

        # 执行命令
        queue.enqueue(IncrementCommand(value, 5))
        queue.enqueue(IncrementCommand(value, 3))
        queue.execute_all()
        assert value[0] == 8
        print(f"  ✓ 执行后: value={value[0]}")

        # 撤销
        result = queue.undo()
        assert result == 5
        assert value[0] == 5
        print(f"  ✓ 撤销1次: value={value[0]}")

        result = queue.undo()
        assert result == 0
        assert value[0] == 0
        print(f"  ✓ 撤销2次: value={value[0]}")

        # 无更多可撤销
        result = queue.undo()
        assert result is None
        print("  ✓ 无更多可撤销返回None")

        # 重做
        result = queue.redo()
        assert value[0] == 5
        print(f"  ✓ 重做1次: value={value[0]}")

        result = queue.redo()
        assert value[0] == 8
        print(f"  ✓ 重做2次: value={value[0]}")

        # 无更多可重做
        result = queue.redo()
        assert result is None
        print("  ✓ 无更多可重做返回None")

        # can_undo / can_redo
        assert not queue.can_redo()
        queue.undo()
        assert queue.can_redo()
        assert queue.can_undo()
        print("  ✓ can_undo/can_redo正确")

        print("[Pass] 撤销/重做\n")
        return True
    except Exception as e:
        print(f"[Fail] 撤销/重做: {e}\n")
        return False


def test_history_management() -> bool:
    print("[Test] 历史记录管理")
    try:
        queue = CommandQueue()
        value = [0]

        queue.enqueue(IncrementCommand(value, 1))
        queue.enqueue(SetCommand(value, 10))
        queue.execute_all()

        history = queue.get_history()
        assert len(history) == 2
        assert history[0]["name"] == "Increment"
        assert history[1]["name"] == "Set"
        assert history[1]["is_current"]
        print(f"  ✓ 历史记录: {history}")

        # 撤销后历史状态变化
        queue.undo()
        history = queue.get_history()
        assert history[0]["is_current"]
        print("  ✓ 撤销后历史状态更新")

        # 新命令覆盖未来历史
        queue.enqueue(IncrementCommand(value, 5))
        queue.execute_all()
        history = queue.get_history()
        assert len(history) == 2  # Set被覆盖了
        print("  ✓ 新命令覆盖未来历史")

        print("[Pass] 历史记录管理\n")
        return True
    except Exception as e:
        print(f"[Fail] 历史记录管理: {e}\n")
        return False


def test_macro_command() -> bool:
    print("[Test] 宏命令")
    try:
        value = [0]
        macro = MacroCommand("AddSequence")

        macro.add_command(IncrementCommand(value, 2))
        macro.add_command(IncrementCommand(value, 3))
        macro.add_command(IncrementCommand(value, 5))

        assert len(macro.get_commands()) == 3
        assert macro.can_undo()
        print("  ✓ 宏命令组装")

        results = macro.run()
        assert results == [2, 5, 10]
        assert value[0] == 10
        print(f"  ✓ 宏执行: value={value[0]}, results={results}")

        macro.undo()
        assert value[0] == 0
        print(f"  ✓ 宏撤销: value={value[0]}")

        # 包含不可撤销命令的宏
        class NoUndoCommand(Command):
            def execute(self):
                return "done"

        macro2 = MacroCommand("Mixed")
        macro2.add_command(NoUndoCommand())
        macro2.add_command(IncrementCommand(value, 1))
        assert macro2.can_undo()  # 因为有一个可撤销
        macro2.run()
        macro2.undo()
        print("  ✓ 混合宏命令撤销")

        print("[Pass] 宏命令\n")
        return True
    except Exception as e:
        print(f"[Fail] 宏命令: {e}\n")
        return False


def test_function_command() -> bool:
    print("[Test] 函数命令")
    try:
        data = {"count": 0}

        def do_inc():
            data["count"] += 1
            return data["count"]

        # 简单函数命令
        cmd = FunctionCommand(do_inc, "increment")
        result = cmd.run()
        assert result == 1
        assert data["count"] == 1
        print("  ✓ FunctionCommand执行")

        # 可撤销函数命令
        def do_dec():
            data["count"] -= 1
            return data["count"]

        undoable = UndoableFunctionCommand(do_inc, do_dec, "counter")
        undoable.run()
        assert data["count"] == 2
        undoable.undo()
        assert data["count"] == 1
        print("  ✓ UndoableFunctionCommand撤销")

        # redo测试
        undoable.redo()
        assert data["count"] == 2
        print("  ✓ UndoableFunctionCommand重做")

        print("[Pass] 函数命令\n")
        return True
    except Exception as e:
        print(f"[Fail] 函数命令: {e}\n")
        return False


def test_command_invoker() -> bool:
    print("[Test] 命令调用器")
    try:
        invoker = CommandInvoker()
        value = [0]

        # 注册命令
        invoker.register_command("increment", IncrementCommand)
        invoker.register_command("set", SetCommand)
        print("  ✓ 命令注册")

        # 创建并执行
        cmd = invoker.create_command("increment", value, 5)
        invoker.execute(cmd)
        assert value[0] == 5
        print("  ✓ 创建并执行命令")

        # 立即执行函数
        data = {"x": 0}
        result = invoker.execute_immediate(lambda: data.update({"x": 10}) or data["x"], "set_x")
        assert data["x"] == 10
        print("  ✓ 立即执行函数")

        # 撤销
        invoker.undo()
        print("  ✓ 调用器撤销")

        # 不存在的命令
        try:
            invoker.create_command("not_exist")
            assert False, "应该抛出异常"
        except CommandException:
            print("  ✓ 不存在的命令抛出异常")

        # 历史
        history = invoker.get_history()
        assert len(history) > 0
        print(f"  ✓ 历史记录: {len(history)}条")

        print("[Pass] 命令调用器\n")
        return True
    except Exception as e:
        print(f"[Fail] 命令调用器: {e}\n")
        return False


def test_error_handling() -> bool:
    print("[Test] 错误处理")
    try:
        class ErrorCommand(Command):
            def execute(self):
                raise ValueError("Test error")

        cmd = ErrorCommand()
        try:
            cmd.run()
            assert False, "应该抛出异常"
        except ValueError:
            assert cmd.error == "Test error"
            print("  ✓ 命令异常被捕获")

        # 异常不影响队列
        queue = CommandQueue()
        value = [0]
        queue.enqueue(IncrementCommand(value, 1))
        queue.enqueue(ErrorCommand())
        try:
            queue.execute_all()
        except ValueError:
            pass
        # 第一个命令已执行
        assert value[0] == 1
        print("  ✓ 异常前命令已执行")

        print("[Pass] 错误处理\n")
        return True
    except Exception as e:
        print(f"[Fail] 错误处理: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段69验证脚本：命令模式")
    print("=" * 60 + "\n")

    results = []
    results.append(("命令封装", test_command_encapsulation()))
    results.append(("命令队列", test_command_queue()))
    results.append(("撤销/重做", test_undo_redo()))
    results.append(("历史记录管理", test_history_management()))
    results.append(("宏命令", test_macro_command()))
    results.append(("函数命令", test_function_command()))
    results.append(("命令调用器", test_command_invoker()))
    results.append(("错误处理", test_error_handling()))

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
        print("🎉 所有测试通过！阶段69验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
