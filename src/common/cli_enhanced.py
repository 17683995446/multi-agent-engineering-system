"""增强CLI模块 - 提供彩色输出、进度条、表格格式化和交互式提示功能。"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Iterator, Protocol, TypeVar


class ColorCode(Enum):
    """ANSI颜色代码。"""

    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class ColorOutput:
    """彩色输出工具类。"""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and sys.stdout.isatty()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def colorize(self, text: str, *codes: ColorCode) -> str:
        if not self._enabled:
            return text
        prefix = "".join(code.value for code in codes)
        return f"{prefix}{text}{ColorCode.RESET.value}"

    def red(self, text: str) -> str:
        return self.colorize(text, ColorCode.RED)

    def green(self, text: str) -> str:
        return self.colorize(text, ColorCode.GREEN)

    def yellow(self, text: str) -> str:
        return self.colorize(text, ColorCode.YELLOW)

    def blue(self, text: str) -> str:
        return self.colorize(text, ColorCode.BLUE)

    def cyan(self, text: str) -> str:
        return self.colorize(text, ColorCode.CYAN)

    def magenta(self, text: str) -> str:
        return self.colorize(text, ColorCode.MAGENTA)

    def bold(self, text: str) -> str:
        return self.colorize(text, ColorCode.BOLD)

    def print(
        self,
        text: str,
        *codes: ColorCode,
        end: str = "\n",
        flush: bool = False,
    ) -> None:
        output = self.colorize(text, *codes) if codes else text
        print(output, end=end, flush=flush)

    def success(self, text: str, end: str = "\n", flush: bool = False) -> None:
        self.print(text, ColorCode.GREEN, end=end, flush=flush)

    def error(self, text: str, end: str = "\n", flush: bool = False) -> None:
        self.print(text, ColorCode.RED, end=end, flush=flush)

    def warning(self, text: str, end: str = "\n", flush: bool = False) -> None:
        self.print(text, ColorCode.YELLOW, end=end, flush=flush)

    def info(self, text: str, end: str = "\n", flush: bool = False) -> None:
        self.print(text, ColorCode.BLUE, end=end, flush=flush)


@dataclass
class ProgressConfig:
    """进度条配置。"""

    width: int = 40
    fill_char: str = "█"
    empty_char: str = "░"
    prefix: str = "Progress:"
    suffix: str = ""
    show_percentage: bool = True
    show_count: bool = True
    color: ColorCode | None = ColorCode.CYAN


class ProgressBar:
    """进度条组件。"""

    def __init__(
        self,
        total: int,
        config: ProgressConfig | None = None,
        color_output: ColorOutput | None = None,
    ) -> None:
        if total <= 0:
            raise ValueError("total must be positive")
        self._total = total
        self._current = 0
        self._config = config or ProgressConfig()
        self._color = color_output or ColorOutput()
        self._started = False
        self._finished = False
        self._start_time: float | None = None

    @property
    def total(self) -> int:
        return self._total

    @property
    def current(self) -> int:
        return self._current

    @property
    def percentage(self) -> float:
        return (self._current / self._total) * 100.0

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._start_time = time.time()
        self._render()

    def update(self, step: int = 1) -> None:
        if not self._started:
            self.start()
        self._current = min(self._current + step, self._total)
        self._render()
        if self._current >= self._total:
            self.finish()

    def set_progress(self, value: int) -> None:
        if not self._started:
            self.start()
        self._current = max(0, min(value, self._total))
        self._render()
        if self._current >= self._total:
            self.finish()

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._render(final=True)
        print()

    def _render(self, final: bool = False) -> None:
        if not self._started:
            return
        ratio = self._current / self._total
        filled = int(ratio * self._config.width)
        empty = self._config.width - filled
        bar = self._config.fill_char * filled + self._config.empty_char * empty

        parts: list[str] = []
        if self._config.prefix:
            parts.append(self._config.prefix)
        if self._config.color:
            parts.append(self._color.colorize(bar, self._config.color))
        else:
            parts.append(bar)

        if self._config.show_percentage:
            parts.append(f" {ratio * 100:5.1f}%")
        if self._config.show_count:
            parts.append(f" [{self._current}/{self._total}]")
        if self._config.suffix:
            parts.append(f" {self._config.suffix}")
        if final and self._start_time is not None:
            elapsed = time.time() - self._start_time
            parts.append(f" (elapsed: {elapsed:.2f}s)")

        line = " ".join(parts)
        print(f"\r{line}", end="", flush=True)

    def __enter__(self) -> ProgressBar:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.finish()

    def iter(self, iterable: Iterator[Any]) -> Iterator[Any]:
        self.start()
        for item in iterable:
            yield item
            self.update(1)
        self.finish()


@dataclass
class ColumnDef:
    """表格列定义。"""

    name: str
    width: int = 20
    align: str = "left"
    color: ColorCode | None = None


@dataclass
class TableConfig:
    """表格配置。"""

    columns: list[ColumnDef] = field(default_factory=list)
    header_color: ColorCode = ColorCode.BOLD
    border_color: ColorCode | None = ColorCode.BRIGHT_BLACK
    show_border: bool = True
    padding: int = 1


class TableFormatter:
    """表格格式化组件。"""

    def __init__(
        self,
        config: TableConfig | None = None,
        color_output: ColorOutput | None = None,
    ) -> None:
        self._config = config or TableConfig()
        self._color = color_output or ColorOutput()
        self._rows: list[list[str]] = []

    def set_columns(self, columns: list[ColumnDef]) -> TableFormatter:
        self._config.columns = columns
        return self

    def add_row(self, row: list[str]) -> TableFormatter:
        if len(row) != len(self._config.columns):
            raise ValueError(
                f"Row length {len(row)} does not match column count {len(self._config.columns)}"
            )
        self._rows.append(row)
        return self

    def add_rows(self, rows: list[list[str]]) -> TableFormatter:
        for row in rows:
            self.add_row(row)
        return self

    def clear(self) -> None:
        self._rows.clear()

    def _pad(self, text: str, width: int, align: str) -> str:
        if align == "center":
            return text.center(width)
        if align == "right":
            return text.rjust(width)
        return text.ljust(width)

    def _format_cell(
        self, text: str, col: ColumnDef, color: ColorCode | None = None
    ) -> str:
        padded = self._pad(text, col.width, col.align)
        if color:
            return self._color.colorize(padded, color)
        if col.color:
            return self._color.colorize(padded, col.color)
        return padded

    def _border_line(self, left: str, mid: str, right: str, fill: str) -> str:
        segments = []
        for col in self._config.columns:
            segments.append(fill * (col.width + self._config.padding * 2))
        line = mid.join(segments)
        if self._config.border_color:
            line = self._color.colorize(line, self._config.border_color)
        return left + line + right

    def _data_line(self, cells: list[str], colors: list[ColorCode | None] | None = None) -> str:
        parts = []
        for i, col in enumerate(self._config.columns):
            text = cells[i] if i < len(cells) else ""
            color = colors[i] if colors and i < len(colors) else None
            cell = self._format_cell(text, col, color)
            pad = " " * self._config.padding
            parts.append(pad + cell + pad)
        sep = "│"
        if self._config.border_color:
            sep = self._color.colorize(sep, self._config.border_color)
        line = sep.join(parts)
        return "│" + line + "│"

    def render(self) -> str:
        if not self._config.columns:
            return ""
        lines: list[str] = []
        if self._config.show_border:
            lines.append(self._border_line("┌", "┬", "┐", "─"))

        header_cells = [col.name for col in self._config.columns]
        lines.append(self._data_line(header_cells, [self._config.header_color] * len(header_cells)))

        if self._config.show_border:
            lines.append(self._border_line("├", "┼", "┤", "─"))

        for row in self._rows:
            lines.append(self._data_line(row))

        if self._config.show_border:
            lines.append(self._border_line("└", "┴", "┘", "─"))

        return "\n".join(lines)

    def print(self) -> None:
        print(self.render())


T = TypeVar("T")


@dataclass
class Choice(Generic[T]):
    """交互式选项。"""

    key: str
    label: str
    value: T
    color: ColorCode | None = None


class InteractivePrompt:
    """交互式提示组件。"""

    def __init__(self, color_output: ColorOutput | None = None) -> None:
        self._color = color_output or ColorOutput()

    def confirm(self, message: str, default: bool = False) -> bool:
        default_str = "Y/n" if default else "y/N"
        prompt = f"{message} [{default_str}]: "
        self._color.print(prompt, ColorCode.CYAN, end="", flush=True)
        try:
            response = input().strip().lower()
        except EOFError:
            return default
        if not response:
            return default
        return response in ("y", "yes")

    def select(self, message: str, choices: list[Choice[T]]) -> T:
        self._color.print(message, ColorCode.BOLD)
        for choice in choices:
            label = choice.label
            if choice.color:
                label = self._color.colorize(label, choice.color)
            self._color.print(f"  [{choice.key}] {label}")
        while True:
            self._color.print("Enter choice: ", ColorCode.CYAN, end="", flush=True)
            try:
                response = input().strip()
            except EOFError:
                response = ""
            for choice in choices:
                if response == choice.key:
                    return choice.value
            self._color.error("Invalid choice, please try again.")

    def input_text(self, message: str, default: str = "") -> str:
        prompt = message
        if default:
            prompt = f"{message} [{default}]: "
        else:
            prompt = f"{message}: "
        self._color.print(prompt, ColorCode.CYAN, end="", flush=True)
        try:
            response = input().strip()
        except EOFError:
            response = ""
        return response if response else default

    def input_number(
        self, message: str, default: float | None = None, integer: bool = False
    ) -> float | int:
        while True:
            default_str = str(default) if default is not None else ""
            response = self.input_text(message, default_str)
            if not response:
                if default is not None:
                    return int(default) if integer else default
                self._color.error("Input is required.")
                continue
            try:
                value = int(response) if integer else float(response)
                return value
            except ValueError:
                self._color.error("Invalid number, please try again.")

    def password(self, message: str) -> str:
        import getpass

        self._color.print(f"{message}: ", ColorCode.CYAN, end="", flush=True)
        try:
            return getpass.getpass("")
        except EOFError:
            return ""

    def multi_select(self, message: str, choices: list[Choice[T]]) -> list[T]:
        self._color.print(message, ColorCode.BOLD)
        self._color.print("(Enter multiple choices separated by commas, or 'all')")
        for choice in choices:
            label = choice.label
            if choice.color:
                label = self._color.colorize(label, choice.color)
            self._color.print(f"  [{choice.key}] {label}")
        while True:
            self._color.print("Enter choices: ", ColorCode.CYAN, end="", flush=True)
            try:
                response = input().strip()
            except EOFError:
                response = ""
            if response.lower() == "all":
                return [c.value for c in choices]
            keys = [k.strip() for k in response.split(",") if k.strip()]
            result: list[T] = []
            invalid: list[str] = []
            for key in keys:
                matched = False
                for choice in choices:
                    if key == choice.key:
                        result.append(choice.value)
                        matched = True
                        break
                if not matched:
                    invalid.append(key)
            if invalid:
                self._color.error(f"Invalid choices: {', '.join(invalid)}")
                continue
            return result


class EnhancedCLI:
    """增强命令行界面。"""

    def __init__(self, color_enabled: bool = True) -> None:
        self.color = ColorOutput(enabled=color_enabled)
        self.progress: ProgressBar | None = None
        self.table = TableFormatter(color_output=self.color)
        self.prompt = InteractivePrompt(color_output=self.color)

    def header(self, text: str) -> None:
        width = 60
        line = "═" * width
        self.color.print(f"╔{line}╗", ColorCode.CYAN)
        centered = text.center(width)
        self.color.print(f"║{centered}║", ColorCode.CYAN)
        self.color.print(f"╚{line}╝", ColorCode.CYAN)

    def section(self, text: str) -> None:
        self.color.print(f"\n▶ {text}", ColorCode.BOLD, ColorCode.BLUE)
        self.color.print("─" * (len(text) + 3), ColorCode.BRIGHT_BLACK)

    def success(self, text: str) -> None:
        self.color.print(f"✓ {text}", ColorCode.GREEN)

    def error(self, text: str) -> None:
        self.color.print(f"✗ {text}", ColorCode.RED)

    def warning(self, text: str) -> None:
        self.color.print(f"⚠ {text}", ColorCode.YELLOW)

    def info(self, text: str) -> None:
        self.color.print(f"ℹ {text}", ColorCode.BLUE)

    def create_progress(
        self, total: int, config: ProgressConfig | None = None
    ) -> ProgressBar:
        self.progress = ProgressBar(total=total, config=config, color_output=self.color)
        return self.progress

    def create_table(self, config: TableConfig | None = None) -> TableFormatter:
        self.table = TableFormatter(config=config, color_output=self.color)
        return self.table

    def spinner(
        self,
        message: str,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        import threading

        result: Any = None
        exception: BaseException | None = None
        done = threading.Event()

        def target() -> None:
            nonlocal result, exception
            try:
                result = func(*args, **kwargs)
            except BaseException as e:
                exception = e
            finally:
                done.set()

        thread = threading.Thread(target=target)
        thread.start()

        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        idx = 0
        while not done.is_set():
            char = chars[idx % len(chars)]
            self.color.print(
                f"\r{char} {message}",
                ColorCode.CYAN,
                end="",
                flush=True,
            )
            time.sleep(0.1)
            idx += 1
        print("\r" + " " * (len(message) + 4) + "\r", end="")
        thread.join()
        if exception is not None:
            raise exception
        return result

    def box(self, text: str, color: ColorCode = ColorCode.BLUE) -> None:
        lines = text.split("\n")
        max_len = max(len(line) for line in lines) if lines else 0
        padding = 2
        width = max_len + padding * 2
        self.color.print(f"┌{'─' * width}┐", color)
        for line in lines:
            padded = line.ljust(max_len)
            self.color.print(f"│{' ' * padding}{padded}{' ' * padding}│", color)
        self.color.print(f"└{'─' * width}┘", color)
