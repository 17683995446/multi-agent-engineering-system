"""
系统诊断模块
遵循第一性原理：问题可观测公理

核心功能：
1. 系统诊断
2. 问题定位
3. 诊断报告
4. 修复建议
"""

from __future__ import annotations

import os
import platform
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class DiagnosticLevel(Enum):
    """诊断级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticCategory(Enum):
    """诊断类别"""
    SYSTEM = "system"
    DISK = "disk"
    MEMORY = "memory"
    NETWORK = "network"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    SECURITY = "security"


@dataclass
class DiagnosticItem:
    """诊断项"""
    category: DiagnosticCategory
    level: DiagnosticLevel
    title: str
    message: str
    suggestion: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "suggestion": self.suggestion,
            "details": self.details,
        }


@dataclass
class DiagnosticReport:
    """诊断报告"""
    generated_at: datetime
    items: List[DiagnosticItem] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    def add_item(self, item: DiagnosticItem) -> None:
        self.items.append(item)
        key = item.level.value
        self.summary[key] = self.summary.get(key, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }

    def has_issues(self) -> bool:
        return any(
            item.level in (DiagnosticLevel.ERROR, DiagnosticLevel.CRITICAL)
            for item in self.items
        )


class DiagnosticCheck(ABC):
    """诊断检查抽象基类"""

    @abstractmethod
    def check(self) -> List[DiagnosticItem]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class SystemInfoCheck(DiagnosticCheck):
    """系统信息检查"""

    def get_name(self) -> str:
        return "system_info"

    def check(self) -> List[DiagnosticItem]:
        items = []
        items.append(
            DiagnosticItem(
                category=DiagnosticCategory.SYSTEM,
                level=DiagnosticLevel.INFO,
                title="操作系统",
                message=f"{platform.system()} {platform.release()}",
                details={"platform": platform.platform(), "processor": platform.processor()},
            )
        )
        items.append(
            DiagnosticItem(
                category=DiagnosticCategory.SYSTEM,
                level=DiagnosticLevel.INFO,
                title="Python版本",
                message=f"{platform.python_version()}",
                details={"implementation": platform.python_implementation()},
            )
        )
        return items


class DiskSpaceCheck(DiagnosticCheck):
    """磁盘空间检查"""

    def __init__(self, threshold_percent: float = 90.0, min_free_gb: float = 1.0):
        self.threshold_percent = threshold_percent
        self.min_free_gb = min_free_gb

    def get_name(self) -> str:
        return "disk_space"

    def check(self) -> List[DiagnosticItem]:
        items = []
        try:
            import shutil
            usage = shutil.disk_usage("/workspace")
            percent = (usage.used / usage.total) * 100
            free_gb = usage.free / (1024 ** 3)
            if percent >= self.threshold_percent or free_gb < self.min_free_gb:
                level = DiagnosticLevel.WARNING if percent < 95 else DiagnosticLevel.ERROR
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.DISK,
                        level=level,
                        title="磁盘空间不足",
                        message=f"磁盘使用率 {percent:.1f}%, 可用 {free_gb:.2f} GB",
                        suggestion="清理临时文件或扩展磁盘空间",
                        details={"percent": percent, "free_gb": free_gb},
                    )
                )
            else:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.DISK,
                        level=DiagnosticLevel.INFO,
                        title="磁盘空间正常",
                        message=f"磁盘使用率 {percent:.1f}%, 可用 {free_gb:.2f} GB",
                        details={"percent": percent, "free_gb": free_gb},
                    )
                )
        except Exception as e:
            items.append(
                DiagnosticItem(
                    category=DiagnosticCategory.DISK,
                    level=DiagnosticLevel.ERROR,
                    title="磁盘检查失败",
                    message=str(e),
                )
            )
        return items


class MemoryCheck(DiagnosticCheck):
    """内存检查"""

    def get_name(self) -> str:
        return "memory"

    def check(self) -> List[DiagnosticItem]:
        items = []
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent >= 90:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.MEMORY,
                        level=DiagnosticLevel.WARNING,
                        title="内存使用率过高",
                        message=f"内存使用率 {mem.percent}%",
                        suggestion="检查内存泄漏或增加内存",
                        details={"percent": mem.percent, "available_mb": mem.available / 1024 / 1024},
                    )
                )
            else:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.MEMORY,
                        level=DiagnosticLevel.INFO,
                        title="内存使用正常",
                        message=f"内存使用率 {mem.percent}%",
                        details={"percent": mem.percent, "available_mb": mem.available / 1024 / 1024},
                    )
                )
        except ImportError:
            items.append(
                DiagnosticItem(
                    category=DiagnosticCategory.MEMORY,
                    level=DiagnosticLevel.INFO,
                    title="内存检查跳过",
                    message="psutil 未安装，无法检查内存",
                    suggestion="安装 psutil 以获得更详细的内存诊断",
                )
            )
        return items


class ConfigCheck(DiagnosticCheck):
    """配置检查"""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "configs"
        self.config_dir = config_dir

    def get_name(self) -> str:
        return "config"

    def check(self) -> List[DiagnosticItem]:
        items = []
        if not self.config_dir.exists():
            items.append(
                DiagnosticItem(
                    category=DiagnosticCategory.CONFIG,
                    level=DiagnosticLevel.WARNING,
                    title="配置目录不存在",
                    message=f"配置目录 {self.config_dir} 不存在",
                    suggestion="创建配置目录并添加必要的配置文件",
                )
            )
        else:
            yaml_files = list(self.config_dir.glob("*.yaml"))
            if not yaml_files:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.CONFIG,
                        level=DiagnosticLevel.WARNING,
                        title="配置文件缺失",
                        message="配置目录中没有 YAML 配置文件",
                        suggestion="添加 agents.yaml 等必要配置文件",
                    )
                )
            else:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.CONFIG,
                        level=DiagnosticLevel.INFO,
                        title="配置检查通过",
                        message=f"发现 {len(yaml_files)} 个配置文件",
                        details={"files": [f.name for f in yaml_files]},
                    )
                )
        return items


class DependencyCheck(DiagnosticCheck):
    """依赖检查"""

    REQUIRED_MODULES = ["yaml", "requests"]

    def get_name(self) -> str:
        return "dependency"

    def check(self) -> List[DiagnosticItem]:
        items = []
        for module in self.REQUIRED_MODULES:
            try:
                __import__(module)
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.DEPENDENCY,
                        level=DiagnosticLevel.INFO,
                        title=f"依赖 {module} 已安装",
                        message=f"模块 {module} 可用",
                    )
                )
            except ImportError:
                items.append(
                    DiagnosticItem(
                        category=DiagnosticCategory.DEPENDENCY,
                        level=DiagnosticLevel.WARNING,
                        title=f"依赖 {module} 缺失",
                        message=f"模块 {module} 未安装",
                        suggestion=f"运行 pip install {module}",
                    )
                )
        return items


class LogCheck(DiagnosticCheck):
    """日志检查"""

    def __init__(self, log_dir: Optional[Path] = None):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "logs"
        self.log_dir = log_dir

    def get_name(self) -> str:
        return "log"

    def check(self) -> List[DiagnosticItem]:
        items = []
        if not self.log_dir.exists():
            items.append(
                DiagnosticItem(
                    category=DiagnosticCategory.SYSTEM,
                    level=DiagnosticLevel.WARNING,
                    title="日志目录不存在",
                    message=f"日志目录 {self.log_dir} 不存在",
                    suggestion="创建日志目录以启用日志记录",
                )
            )
        else:
            log_files = list(self.log_dir.glob("*.log"))
            items.append(
                DiagnosticItem(
                    category=DiagnosticCategory.SYSTEM,
                    level=DiagnosticLevel.INFO,
                    title="日志目录正常",
                    message=f"日志目录包含 {len(log_files)} 个日志文件",
                    details={"log_dir": str(self.log_dir), "count": len(log_files)},
                )
            )
        return items


class SystemDiagnostic:
    """
    系统诊断主类

    整合所有诊断功能:
    - 系统信息诊断
    - 磁盘空间诊断
    - 内存诊断
    - 配置诊断
    - 依赖诊断
    - 日志诊断
    """

    def __init__(self):
        self.checks: List[DiagnosticCheck] = [
            SystemInfoCheck(),
            DiskSpaceCheck(),
            MemoryCheck(),
            ConfigCheck(),
            DependencyCheck(),
            LogCheck(),
        ]
        self.logger = setup_logger(__name__)

    def add_check(self, check: DiagnosticCheck) -> None:
        """添加自定义检查"""
        self.checks.append(check)

    def run_diagnosis(self) -> DiagnosticReport:
        """运行完整诊断"""
        self.logger.info("开始系统诊断")
        report = DiagnosticReport(generated_at=datetime.now())
        for check in self.checks:
            try:
                items = check.check()
                for item in items:
                    report.add_item(item)
            except Exception as e:
                report.add_item(
                    DiagnosticItem(
                        category=DiagnosticCategory.SYSTEM,
                        level=DiagnosticLevel.ERROR,
                        title=f"检查失败: {check.get_name()}",
                        message=str(e),
                    )
                )
        self.logger.info(f"系统诊断完成: {report.summary}")
        return report

    def generate_report_text(self, report: DiagnosticReport) -> str:
        """生成文本格式的诊断报告"""
        lines = [
            "=" * 60,
            "系统诊断报告",
            f"生成时间: {report.generated_at.isoformat()}",
            "=" * 60,
            "",
            f"摘要: {report.summary}",
            "",
        ]
        for item in report.items:
            lines.append(f"[{item.level.value.upper()}] {item.category.value} - {item.title}")
            lines.append(f"  消息: {item.message}")
            if item.suggestion:
                lines.append(f"  建议: {item.suggestion}")
            lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def get_repair_suggestions(self, report: DiagnosticReport) -> List[str]:
        """获取修复建议列表"""
        suggestions = []
        for item in report.items:
            if item.level in (DiagnosticLevel.WARNING, DiagnosticLevel.ERROR, DiagnosticLevel.CRITICAL):
                if item.suggestion:
                    suggestions.append(f"[{item.category.value}] {item.title}: {item.suggestion}")
        return suggestions

    def save_report(self, report: DiagnosticReport, path: Path) -> None:
        """保存诊断报告到文件"""
        import json
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        self.logger.info(f"诊断报告已保存: {path}")


def demo_system_diagnostic():
    """演示系统诊断"""
    print("=" * 60)
    print("系统诊断演示")
    print("=" * 60)
    print()

    diagnostic = SystemDiagnostic()
    report = diagnostic.run_diagnosis()

    print(diagnostic.generate_report_text(report))
    print()

    suggestions = diagnostic.get_repair_suggestions(report)
    if suggestions:
        print("修复建议:")
        for s in suggestions:
            print(f"  - {s}")
    else:
        print("未发现需要修复的问题")
    print()

    print("=" * 60)
    print("系统诊断演示完成")
    print("=" * 60)
    print()
    print("✓ 系统信息诊断")
    print("✓ 磁盘空间诊断")
    print("✓ 内存诊断")
    print("✓ 配置诊断")
    print("✓ 依赖诊断")
    print("✓ 日志诊断")
    print()


if __name__ == "__main__":
    demo_system_diagnostic()
