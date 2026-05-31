"""
阶段94验证脚本：部署工具模块
"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.deploy_tool import (
    CheckSeverity,
    DeployStatus,
    DeployTool,
    EnvironmentChecker,
    RollbackManager,
)


def test_env_checker_python_version():
    """测试Python版本检查"""
    checker = EnvironmentChecker()
    result = checker.check_python_version((3, 8))
    assert result.passed is True
    assert result.check_name == "python_version"
    print("✓ Python版本检查测试通过")


def test_env_checker_disk_space():
    """测试磁盘空间检查"""
    checker = EnvironmentChecker()
    result = checker.check_disk_space(min_gb=0.01)
    assert result.passed is True
    assert result.check_name == "disk_space"
    assert "GB" in result.message
    print("✓ 磁盘空间检查测试通过")


def test_env_checker_env_var():
    """测试环境变量检查"""
    checker = EnvironmentChecker()
    result = checker.check_env_var("PATH")
    assert result.passed is True
    assert "PATH" in result.check_name
    print("✓ 环境变量检查测试通过")


def test_env_checker_directory_writable():
    """测试目录可写检查"""
    checker = EnvironmentChecker()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = checker.check_directory_writable(tmpdir)
        assert result.passed is True
    print("✓ 目录可写检查测试通过")


def test_env_checker_all():
    """测试批量环境检查"""
    checker = EnvironmentChecker()
    checker.register(lambda: checker.check_python_version())
    checker.register(lambda: checker.check_disk_space(min_gb=0.01))
    results = checker.check_all()
    assert len(results) == 2
    assert all(r.passed for r in results)
    print("✓ 批量环境检查测试通过")


def test_rollback_snapshot():
    """测试快照创建与回滚"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target = tmpdir / "deploy_target"
        target.mkdir()
        (target / "file.txt").write_text("original", encoding="utf-8")

        backup_dir = tmpdir / "backups"
        mgr = RollbackManager(backup_dir)
        snapshot = mgr.create_snapshot("test_deploy", target)

        assert snapshot.exists()
        assert (snapshot / "file.txt").read_text(encoding="utf-8") == "original"

        # 模拟部署修改
        (target / "file.txt").write_text("modified", encoding="utf-8")

        # 回滚
        success = mgr.rollback("test_deploy", target)
        assert success is True
        assert (target / "file.txt").read_text(encoding="utf-8") == "original"
        print("✓ 快照与回滚测试通过")


def test_rollback_cleanup():
    """测试旧快照清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = RollbackManager(tmpdir)
        for i in range(3):
            d = tmpdir / f"snap_{i}"
            d.mkdir()
            time.sleep(0.01)
        mgr.snapshots["d1"] = tmpdir / "snap_0"
        mgr.snapshots["d2"] = tmpdir / "snap_1"
        mgr.cleanup_old_snapshots(keep_count=2)
        remaining = list(tmpdir.iterdir())
        assert len(remaining) <= 2
        print("✓ 旧快照清理测试通过")


def test_deploy_executor():
    """测试部署执行器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        mgr = RollbackManager(tmpdir / "backups")
        executor = DeployTool(tmpdir / "backups").executor
        executor.register_script("test", ["echo hello", "echo world"])

        steps = executor.execute_script("test")
        assert len(steps) == 2
        assert steps[0].status == DeployStatus.SUCCESS
        assert "hello" in steps[0].output
        print("✓ 部署执行器测试通过")


def test_deploy_tool_success():
    """测试完整部署流程（成功）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target = tmpdir / "target"
        target.mkdir()

        tool = DeployTool(backup_dir=tmpdir / "backups")
        tool.executor.register_script("deploy_ok", ["echo step1", "echo step2"])

        report = tool.deploy("deploy_1", target, "deploy_ok")
        assert report.status == DeployStatus.SUCCESS
        assert len(report.env_checks) > 0
        assert len(report.steps) == 2
        assert report.duration_seconds >= 0
        print("✓ 完整部署流程（成功）测试通过")


def test_deploy_tool_fail_and_rollback():
    """测试部署失败回滚"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        target = tmpdir / "target"
        target.mkdir()
        (target / "data.txt").write_text("original", encoding="utf-8")

        tool = DeployTool(backup_dir=tmpdir / "backups")
        tool.executor.register_script("deploy_fail", ["echo ok", "exit 1"])

        report = tool.deploy("deploy_2", target, "deploy_fail")
        assert report.status == DeployStatus.ROLLED_BACK
        assert (target / "data.txt").read_text(encoding="utf-8") == "original"
        print("✓ 部署失败回滚测试通过")


def test_deploy_report_save():
    """测试部署报告保存"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tool = DeployTool()
        report = tool.deploy("r1", tmpdir, "none")
        path = tool.save_report(report, tmpdir)
        assert path.exists()
        assert "deploy_r1" in path.name
        print("✓ 部署报告保存测试通过")


def test_deploy_history():
    """测试部署历史"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tool = DeployTool()
        tool.executor.register_script("h", ["echo x"])
        tool.deploy("h1", tmpdir, "h")
        tool.deploy("h2", tmpdir, "h")
        history = tool.get_history()
        assert len(history) == 2
        print("✓ 部署历史测试通过")


def main():
    print("=" * 60)
    print("阶段94验证：部署工具模块")
    print("=" * 60)

    test_env_checker_python_version()
    test_env_checker_disk_space()
    test_env_checker_env_var()
    test_env_checker_directory_writable()
    test_env_checker_all()
    test_rollback_snapshot()
    test_rollback_cleanup()
    test_deploy_executor()
    test_deploy_tool_success()
    test_deploy_tool_fail_and_rollback()
    test_deploy_report_save()
    test_deploy_history()

    print("=" * 60)
    print("阶段94验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
