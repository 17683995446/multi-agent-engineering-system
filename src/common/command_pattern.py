"""
命令模式模块
遵循第一性原理：行为封装与职责分离

核心功能：
1. 命令封装 - 将请求封装为对象
2. 命令队列 - 顺序执行与批量处理
3. 撤销/重做 - 操作历史管理
4. 宏命令 - 组合多个命令
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.utils import setup_logger

logger = setup_logger(__name__)


class CommandException(Exception):
    """命令执行异常"""
    pass


class Command(ABC):
    """命令抽象基类"""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.command_id = str(uuid.uuid4())
        self.executed = False
        self.execution_time_ms: float = 0.0
        self.error: Optional[str] = None

    @abstractmethod
    def execute(self) -> Any:
        """执行命令"""
        pass

    def undo(self) -> Any:
        """撤销命令，默认不支持"""
        raise CommandException(f"Command {self.name} does not support undo")

    def redo(self) -> Any:
        """重做命令，默认重新执行"""
        return self.execute()

    def can_undo(self) -> bool:
        """是否支持撤销"""
        return False

    def run(self) -> Any:
        """运行命令并记录执行时间"""
        start = time.time()
        try:
            result = self.execute()
            self.executed = True
            self.error = None
            return result
        except Exception as e:
            self.error = str(e)
            logger.error(f"命令执行失败 [{self.name}]: {e}\n{traceback.format_exc()}")
            raise
        finally:
            self.execution_time_ms = (time.time() - start) * 1000


class UndoableCommand(Command):
    """可撤销命令基类"""

    def can_undo(self) -> bool:
        return True

    @abstractmethod
    def execute(self) -> Any:
        pass

    @abstractmethod
    def undo(self) -> Any:
        pass


class FunctionCommand(Command):
    """函数包装命令"""

    def __init__(self, func: Callable[[], Any], name: str = ""):
        super().__init__(name or func.__name__)
        self.func = func

    def execute(self) -> Any:
        return self.func()


class UndoableFunctionCommand(UndoableCommand):
    """可撤销函数命令"""

    def __init__(
        self,
        execute_func: Callable[[], Any],
        undo_func: Callable[[], Any],
        name: str = "",
    ):
        super().__init__(name or execute_func.__name__)
        self.execute_func = execute_func
        self.undo_func = undo_func

    def execute(self) -> Any:
        return self.execute_func()

    def undo(self) -> Any:
        return self.undo_func()


class MacroCommand(Command):
    """宏命令 - 组合多个命令"""

    def __init__(self, name: str = "", commands: Optional[List[Command]] = None):
        super().__init__(name)
        self._commands: List[Command] = commands or []
        self._undo_stack: List[Command] = []

    def add_command(self, command: Command) -> None:
        """添加子命令"""
        self._commands.append(command)

    def execute(self) -> List[Any]:
        """顺序执行所有子命令"""
        results = []
        self._undo_stack = []
        for cmd in self._commands:
            result = cmd.run()
            results.append(result)
            if cmd.can_undo():
                self._undo_stack.append(cmd)
        return results

    def undo(self) -> List[Any]:
        """逆序撤销所有可撤销的子命令"""
        results = []
        for cmd in reversed(self._undo_stack):
            result = cmd.undo()
            results.append(result)
        return results

    def can_undo(self) -> bool:
        return any(cmd.can_undo() for cmd in self._commands)

    def get_commands(self) -> List[Command]:
        return self._commands.copy()


class CommandQueue:
    """命令队列"""

    def __init__(self, max_size: int = 1000):
        self._queue: List[Command] = []
        self._max_size = max_size
        self._lock = threading.Lock()
        self._history: List[Command] = []
        self._history_index: int = -1
        self._history_limit = 100

    def enqueue(self, command: Command) -> None:
        """入队"""
        with self._lock:
            if len(self._queue) >= self._max_size:
                raise CommandException("Command queue is full")
            self._queue.append(command)
            logger.info(f"命令入队: {command.name}")

    def dequeue(self) -> Optional[Command]:
        """出队"""
        with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    def execute_all(self) -> List[Any]:
        """执行队列中所有命令"""
        results = []
        while True:
            cmd = self.dequeue()
            if cmd is None:
                break
            result = cmd.run()
            results.append(result)
            self._add_to_history(cmd)
        return results

    def _add_to_history(self, command: Command) -> None:
        """添加到历史记录"""
        # 清除当前位置之后的历史
        self._history = self._history[:self._history_index + 1]
        self._history.append(command)
        if len(self._history) > self._history_limit:
            self._history.pop(0)
        else:
            self._history_index += 1

    def undo(self) -> Optional[Any]:
        """撤销上一个命令"""
        with self._lock:
            if self._history_index < 0:
                return None
            cmd = self._history[self._history_index]
            if not cmd.can_undo():
                return None
            result = cmd.undo()
            self._history_index -= 1
            logger.info(f"撤销命令: {cmd.name}")
            return result

    def redo(self) -> Optional[Any]:
        """重做下一个命令"""
        with self._lock:
            if self._history_index >= len(self._history) - 1:
                return None
            self._history_index += 1
            cmd = self._history[self._history_index]
            result = cmd.redo()
            logger.info(f"重做命令: {cmd.name}")
            return result

    def can_undo(self) -> bool:
        """是否可以撤销"""
        with self._lock:
            if self._history_index < 0:
                return False
            return self._history[self._history_index].can_undo()

    def can_redo(self) -> bool:
        """是否可以重做"""
        with self._lock:
            return self._history_index < len(self._history) - 1

    def get_history(self) -> List[Dict[str, Any]]:
        """获取历史记录信息"""
        with self._lock:
            return [
                {
                    "name": cmd.name,
                    "executed": cmd.executed,
                    "can_undo": cmd.can_undo(),
                    "is_current": i == self._history_index,
                }
                for i, cmd in enumerate(self._history)
            ]

    def clear(self) -> None:
        """清空队列和历史"""
        with self._lock:
            self._queue.clear()
            self._history.clear()
            self._history_index = -1

    def size(self) -> int:
        """队列大小"""
        with self._lock:
            return len(self._queue)


class CommandInvoker:
    """
    命令调用器

    统一管理命令的执行、撤销、重做
    """

    def __init__(self):
        self._queue = CommandQueue()
        self._commands: Dict[str, type] = {}

    def register_command(self, name: str, command_class: type) -> None:
        """注册命令类"""
        self._commands[name] = command_class
        logger.info(f"注册命令: {name}")

    def create_command(self, name: str, *args: Any, **kwargs: Any) -> Command:
        """创建命令实例"""
        cmd_class = self._commands.get(name)
        if cmd_class is None:
            raise CommandException(f"Command not found: {name}")
        return cmd_class(*args, **kwargs)

    def execute(self, command: Command) -> Any:
        """执行命令"""
        result = command.run()
        self._queue._add_to_history(command)
        return result

    def execute_immediate(self, func: Callable[[], Any], name: str = "") -> Any:
        """立即执行函数命令"""
        cmd = FunctionCommand(func, name)
        return self.execute(cmd)

    def undo(self) -> Optional[Any]:
        """撤销"""
        return self._queue.undo()

    def redo(self) -> Optional[Any]:
        """重做"""
        return self._queue.redo()

    def can_undo(self) -> bool:
        return self._queue.can_undo()

    def can_redo(self) -> bool:
        return self._queue.can_redo()

    def get_history(self) -> List[Dict[str, Any]]:
        return self._queue.get_history()


def demo_command_pattern():
    """演示命令模式"""
    print("=" * 60)
    print("命令模式演示")
    print("=" * 60)
    print()

    # 1. 简单命令
    print("1. 简单命令:")
    value = [0]

    class IncrementCommand(UndoableCommand):
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

    cmd = IncrementCommand(value, 5)
    result = cmd.run()
    print(f"   执行: value = {result}")
    result = cmd.undo()
    print(f"   撤销: value = {result}")
    print()

    # 2. 命令队列
    print("2. 命令队列:")
    queue = CommandQueue()
    value[0] = 0

    queue.enqueue(IncrementCommand(value, 1))
    queue.enqueue(IncrementCommand(value, 2))
    queue.enqueue(IncrementCommand(value, 3))
    queue.execute_all()
    print(f"   执行队列后: value = {value[0]}")

    queue.undo()
    print(f"   撤销1次: value = {value[0]}")
    queue.undo()
    print(f"   撤销2次: value = {value[0]}")
    queue.redo()
    print(f"   重做1次: value = {value[0]}")
    print()

    # 3. 宏命令
    print("3. 宏命令:")
    value[0] = 0
    macro = MacroCommand("AddTen")
    macro.add_command(IncrementCommand(value, 2))
    macro.add_command(IncrementCommand(value, 3))
    macro.add_command(IncrementCommand(value, 5))
    macro.run()
    print(f"   宏执行: value = {value[0]}")
    macro.undo()
    print(f"   宏撤销: value = {value[0]}")
    print()

    # 4. 函数命令
    print("4. 函数命令:")
    data = {"count": 0}

    def do_inc():
        data["count"] += 1
        return data["count"]

    def do_dec():
        data["count"] -= 1
        return data["count"]

    func_cmd = UndoableFunctionCommand(do_inc, do_dec, "inc_dec")
    func_cmd.run()
    print(f"   函数命令: count = {data['count']}")
    func_cmd.undo()
    print(f"   撤销后: count = {data['count']}")
    print()

    # 5. 命令调用器
    print("5. 命令调用器:")
    invoker = CommandInvoker()
    invoker.register_command("increment", IncrementCommand)

    value[0] = 0
    cmd = invoker.create_command("increment", value, 10)
    invoker.execute(cmd)
    print(f"   调用器执行: value = {value[0]}")
    invoker.undo()
    print(f"   调用器撤销: value = {value[0]}")
    print()

    print("=" * 60)
    print("命令模式演示完成")
    print("=" * 60)
    print()
    print("✓ 命令封装")
    print("✓ 命令队列")
    print("✓ 撤销/重做")
    print("✓ 宏命令")
    print()


if __name__ == "__main__":
    demo_command_pattern()
