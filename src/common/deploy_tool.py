"""
部署工具模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 部署脚本执行
2. 环境检查
3. 回滚机制
4. 部署报告生成
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class DeployStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class CheckSeverity(Enum):
    """检查严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class EnvCheckResult:
    """环境检查结果"""
    check_name: str
    passed: bool
    severity: CheckSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class DeployStep:
    """部署步骤"""
    name: str
    status: DeployStatus
    start_time: str = ""
    end_time: str = ""
    message: str = ""
    output: str = ""

    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "message": self.message,
            "output": self.output,
        }


@dataclass
class DeployReport:
    """部署报告"""
    deploy_id: str
    target: str
    status: DeployStatus
    steps: List[DeployStep] = field(default_factory=list)
    env_checks: List[EnvCheckResult] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    rollback_info: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now().isoformat()

    @property
    def duration_seconds(self) -> float:
        if not self.end_time:
            return 0.0
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            return (end - start).total_seconds()
        except Exception:
            return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deploy_id": self.deploy_id,
            "target": self.target,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 2),
            "steps": [s.to_dict() for s in self.steps],
            "env_checks": [c.to_dict() for c in self.env_checks],
            "rollback_info": self.rollback_info,
        }


class EnvironmentChecker:
    """环境检查器"""

    def __init__(self):
        self.checks: List[Callable[[], EnvCheckResult]] = []

    def register(self, check_func: Callable[[], EnvCheckResult]):
        """注册检查项"""
        self.checks.append(check_func)

    def check_all(self) -> List[EnvCheckResult]:
        """执行所有环境检查"""
        results = []
        for check in self.checks:
            try:
                result = check()
                results.append(result)
            except Exception as e:
                results.append(EnvCheckResult(
                    check_name="unknown",
                    passed=False,
                    severity=CheckSeverity.ERROR,
                    message=f"检查执行异常: {e}",
                ))
        return results

    def check_python_version(self, min_version: tuple = (3, 9)) -> EnvCheckResult:
        """检查Python版本"""
        current = sys.version_info[:2]
        passed = current >= min_version
        return EnvCheckResult(
            check_name="python_version",
            passed=passed,
            severity=CheckSeverity.CRITICAL if not passed else CheckSeverity.INFO,
            message=f"Python版本: {current} (要求 >= {min_version})",
            details={"current": current, "required": min_version},
        )

    def check_disk_space(self, min_gb: float = 1.0, path: str = "/") -> EnvCheckResult:
        """检查磁盘空间"""
        try:
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024 ** 3)
            passed = free_gb >= min_gb
            return EnvCheckResult(
                check_name="disk_space",
                passed=passed,
                severity=CheckSeverity.ERROR if not passed else CheckSeverity.INFO,
                message=f"磁盘剩余: {free_gb:.2f} GB (要求 >= {min_gb} GB)",
                details={"free_gb": round(free_gb, 2), "required_gb": min_gb},
            )
        except Exception as e:
            return EnvCheckResult(
                check_name="disk_space",
                passed=False,
                severity=CheckSeverity.ERROR,
                message=f"磁盘检查失败: {e}",
            )

    def check_env_var(self, var_name: str, required: bool = True) -> EnvCheckResult:
        """检查环境变量"""
        value = os.environ.get(var_name)
        passed = value is not None if required else True
        severity = CheckSeverity.ERROR if required and not passed else CheckSeverity.INFO
        return EnvCheckResult(
            check_name=f"env_var_{var_name}",
            passed=passed,
            severity=severity,
            message=f"环境变量 {var_name}: {'已设置' if value else '未设置'}",
            details={"var_name": var_name, "value": value},
        )

    def check_directory_writable(self, path: str) -> EnvCheckResult:
        """检查目录可写"""
        try:
            test_path = Path(path)
            test_path.mkdir(parents=True, exist_ok=True)
            test_file = test_path / ".deploy_write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            return EnvCheckResult(
                check_name="directory_writable",
                passed=True,
                severity=CheckSeverity.INFO,
                message=f"目录可写: {path}",
            )
        except Exception as e:
            return EnvCheckResult(
                check_name="directory_writable",
                passed=False,
                severity=CheckSeverity.ERROR,
                message=f"目录不可写: {path} - {e}",
            )


class RollbackManager:
    """回滚管理器"""

    def __init__(self, backup_dir: Union[str, Path] = ".deploy_backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        self.snapshots: Dict[str, Path] = {}

    def create_snapshot(self, deploy_id: str, target_dir: Union[str, Path]) -> Path:
        """创建部署前快照"""
        target_dir = Path(target_dir)
        snapshot_path = self.backup_dir / f"{deploy_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        snapshot_path.mkdir(exist_ok=True, parents=True)

        if target_dir.exists():
            for item in target_dir.iterdir():
                dest = snapshot_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        self.snapshots[deploy_id] = snapshot_path
        logger.info(f"快照已创建: {snapshot_path}")
        return snapshot_path

    def rollback(self, deploy_id: str, target_dir: Union[str, Path]) -> bool:
        """执行回滚"""
        snapshot = self.snapshots.get(deploy_id)
        if not snapshot or not snapshot.exists():
            logger.error(f"回滚失败: 找不到快照 {deploy_id}")
            return False

        target_dir = Path(target_dir)
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(snapshot, target_dir, dirs_exist_ok=True)
            logger.info(f"回滚完成: {target_dir}")
            return True
        except Exception as e:
            logger.error(f"回滚异常: {e}")
            return False

    def cleanup_old_snapshots(self, keep_count: int = 5):
        """清理旧快照"""
        snapshots = sorted(self.backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in snapshots[keep_count:]:
            shutil.rmtree(old)
            logger.info(f"已清理旧快照: {old}")


class DeployExecutor:
    """部署执行器"""

    def __init__(self, rollback_manager: RollbackManager):
        self.rollback_manager = rollback_manager
        self.scripts: Dict[str, List[str]] = {}

    def register_script(self, name: str, commands: List[str]):
        """注册部署脚本"""
        self.scripts[name] = commands

    def execute_step(self, name: str, command: str, cwd: Optional[str] = None) -> DeployStep:
        """执行单个部署步骤"""
        step = DeployStep(name=name, status=DeployStatus.RUNNING)
        logger.info(f"执行部署步骤: {name}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            step.output = result.stdout + result.stderr
            if result.returncode == 0:
                step.status = DeployStatus.SUCCESS
                step.message = "执行成功"
            else:
                step.status = DeployStatus.FAILED
                step.message = f"退出码: {result.returncode}"
        except subprocess.TimeoutExpired:
            step.status = DeployStatus.FAILED
            step.message = "执行超时"
        except Exception as e:
            step.status = DeployStatus.FAILED
            step.message = f"执行异常: {e}"

        step.end_time = datetime.now().isoformat()
        return step

    def execute_script(self, name: str, cwd: Optional[str] = None) -> List[DeployStep]:
        """执行注册脚本"""
        commands = self.scripts.get(name, [])
        steps = []
        for i, cmd in enumerate(commands):
            step = self.execute_step(f"{name}_{i}", cmd, cwd)
            steps.append(step)
            if step.status == DeployStatus.FAILED:
                break
        return steps


class DeployTool:
    """部署工具 - 主类"""

    def __init__(self, backup_dir: Union[str, Path] = ".deploy_backups"):
        self.env_checker = EnvironmentChecker()
        self.rollback_manager = RollbackManager(backup_dir)
        self.executor = DeployExecutor(self.rollback_manager)
        self.reports: List[DeployReport] = []
        logger.info("部署工具初始化完成")

    def check_environment(self) -> List[EnvCheckResult]:
        """执行环境检查"""
        self.env_checker.register(lambda: self.env_checker.check_python_version())
        self.env_checker.register(lambda: self.env_checker.check_disk_space())
        self.env_checker.register(lambda: self.env_checker.check_directory_writable("."))
        return self.env_checker.check_all()

    def deploy(self, deploy_id: str, target_dir: Union[str, Path],
               script_name: str, cwd: Optional[str] = None) -> DeployReport:
        """执行部署"""
        target_dir = Path(target_dir)
        report = DeployReport(
            deploy_id=deploy_id,
            target=str(target_dir),
            status=DeployStatus.RUNNING,
        )

        # 环境检查
        env_results = self.check_environment()
        report.env_checks = env_results
        critical_failed = any(not r.passed and r.severity == CheckSeverity.CRITICAL for r in env_results)
        if critical_failed:
            report.status = DeployStatus.FAILED
            report.end_time = datetime.now().isoformat()
            report.steps.append(DeployStep(
                name="env_check",
                status=DeployStatus.FAILED,
                message="关键环境检查未通过",
            ))
            self.reports.append(report)
            return report

        # 创建快照
        snapshot = self.rollback_manager.create_snapshot(deploy_id, target_dir)
        report.rollback_info = {"snapshot_path": str(snapshot)}

        # 执行部署脚本
        steps = self.executor.execute_script(script_name, cwd)
        report.steps.extend(steps)

        # 判断结果
        if any(s.status == DeployStatus.FAILED for s in steps):
            report.status = DeployStatus.FAILED
            logger.error(f"部署失败，准备回滚: {deploy_id}")
            self.rollback_manager.rollback(deploy_id, target_dir)
            report.status = DeployStatus.ROLLED_BACK
        else:
            report.status = DeployStatus.SUCCESS

        report.end_time = datetime.now().isoformat()
        self.reports.append(report)
        logger.info(f"部署完成: {deploy_id} -> {report.status.value}")
        return report

    def generate_report(self, report: DeployReport) -> str:
        """生成部署报告文本"""
        lines = [
            f"部署报告: {report.deploy_id}",
            f"目标: {report.target}",
            f"状态: {report.status.value}",
            f"耗时: {report.duration_seconds:.2f} 秒",
            "",
            "环境检查:",
        ]
        for check in report.env_checks:
            status = "✓" if check.passed else "✗"
            lines.append(f"  {status} {check.check_name}: {check.message}")

        lines.extend(["", "部署步骤:"])
        for step in report.steps:
            status = "✓" if step.status == DeployStatus.SUCCESS else "✗"
            lines.append(f"  {status} {step.name}: {step.message}")

        return "\n".join(lines)

    def get_history(self) -> List[Dict[str, Any]]:
        """获取部署历史"""
        return [r.to_dict() for r in self.reports]

    def save_report(self, report: DeployReport, output_dir: Union[str, Path] = ".") -> Path:
        """保存部署报告到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        path = output_dir / f"deploy_{report.deploy_id}.json"
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path
