#!/usr/bin/env python3
"""
阶段50验证脚本：产品化发布准备

测试内容：
1. 发布管理器初始化
2. 版本号管理
3. 发布说明生成
4. 发布检查清单
"""

from __future__ import annotations

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.product_release import (
    ChecklistError,
    PackageBuilder,
    ReleaseConfig,
    ReleaseManager,
    ReleaseNotes,
    ReleaseType,
    VersionError,
    VersionManager,
)


def test_version_manager() -> bool:
    print("[Test] VersionManager - 版本号管理")
    try:
        v = VersionManager("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.is_stable()
        assert not v.is_prerelease()
        print("  ✓ 基本解析通过")

        v2 = VersionManager("2.0.0-alpha.1+build.123")
        assert v2.major == 2
        assert v2.prerelease == "alpha.1"
        assert v2.buildmetadata == "build.123"
        print("  ✓ 预发布和构建元数据解析通过")

        v3 = v.bump(ReleaseType.MAJOR)
        assert str(v3) == "2.0.0"
        print("  ✓ Major bump: 1.2.3 -> 2.0.0")

        v4 = v.bump(ReleaseType.MINOR)
        assert str(v4) == "1.3.0"
        print("  ✓ Minor bump: 1.2.3 -> 1.3.0")

        v5 = v.bump(ReleaseType.PATCH)
        assert str(v5) == "1.2.4"
        print("  ✓ Patch bump: 1.2.3 -> 1.2.4")

        v6 = v.bump(ReleaseType.PRE, "beta")
        assert str(v6) == "1.2.3-beta.1"
        print("  ✓ Pre-release bump: 1.2.3 -> 1.2.3-beta.1")

        v7 = v6.bump(ReleaseType.PRE, "beta")
        assert str(v7) == "1.2.3-beta.2"
        print("  ✓ Pre-release increment: 1.2.3-beta.1 -> 1.2.3-beta.2")

        assert v < v3
        assert v == VersionManager("1.2.3")
        assert v < v2
        print("  ✓ 版本比较通过")

        try:
            VersionManager("invalid")
            assert False, "应该抛出 VersionError"
        except VersionError:
            print("  ✓ 无效版本号异常捕获通过")

        print("[Pass] VersionManager\n")
        return True
    except Exception as e:
        print(f"[Fail] VersionManager: {e}\n")
        return False


def test_release_notes() -> bool:
    print("[Test] ReleaseNotes - 发布说明生成")
    try:
        config = ReleaseConfig(
            name="MyProduct",
            version="1.0.0",
            release_date="2026-05-31",
            author="Team",
            description="Test release",
        )
        notes = ReleaseNotes(config)
        notes.add_entry("feature", "新增用户登录功能")
        notes.add_entry("feature", "支持多语言")
        notes.add_entry("fix", "修复内存泄漏")
        notes.set_metadata("build_id", "12345")

        md = notes.generate("markdown")
        assert "Release 1.0.0" in md
        assert "新增用户登录功能" in md
        assert "修复内存泄漏" in md
        print("  ✓ Markdown 格式生成通过")

        txt = notes.generate("txt")
        assert "Release 1.0.0" in txt
        assert "[Feature]" in txt
        print("  ✓ TXT 格式生成通过")

        js = notes.generate("json")
        assert '"version": "1.0.0"' in js
        assert "新增用户登录功能" in js
        print("  ✓ JSON 格式生成通过")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "notes.md")
            notes.save(path, "markdown")
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Release 1.0.0" in content
            print("  ✓ 文件保存通过")

        print("[Pass] ReleaseNotes\n")
        return True
    except Exception as e:
        print(f"[Fail] ReleaseNotes: {e}\n")
        return False


def test_package_builder() -> bool:
    print("[Test] PackageBuilder - 包构建器")
    try:
        config = ReleaseConfig(name="TestPkg", version="0.1.0", output_dir="dist_test")
        builder = PackageBuilder(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "main.py"), "w") as f:
                f.write("print('hello')")
            with open(os.path.join(src_dir, "README.md"), "w") as f:
                f.write("# README")

            builder.add_source(src_dir)
            zip_path = builder.build_zip()
            assert os.path.exists(zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
            assert any("main.py" in n for n in names)
            print(f"  ✓ ZIP 构建通过: {zip_path}")

            tar_path = builder.build_tar(compression="gz")
            assert os.path.exists(tar_path)
            print(f"  ✓ TAR.GZ 构建通过: {tar_path}")

            # 清理
            os.remove(zip_path)
            os.remove(tar_path)
            os.rmdir(config.output_dir)

        print("[Pass] PackageBuilder\n")
        return True
    except Exception as e:
        print(f"[Fail] PackageBuilder: {e}\n")
        return False


def test_release_manager_init() -> bool:
    print("[Test] ReleaseManager - 发布管理器初始化")
    try:
        config = ReleaseConfig(
            name="AwesomeProduct",
            version="0.5.0",
            author="ReleaseBot",
            output_dir="dist_release",
        )
        manager = ReleaseManager(config)
        assert manager.version_manager.version == "0.5.0"
        assert len(manager.checklist) == 10
        print("  ✓ 初始化配置正确")

        status = manager.get_checklist_status()
        assert status["total"] == 10
        assert status["checked"] == 0
        assert status["required"] == 8
        print(f"  ✓ 检查清单状态: total={status['total']}, required={status['required']}")

        print("[Pass] ReleaseManager Init\n")
        return True
    except Exception as e:
        print(f"[Fail] ReleaseManager Init: {e}\n")
        return False


def test_release_checklist() -> bool:
    print("[Test] ReleaseManager - 发布检查清单")
    try:
        config = ReleaseConfig(name="Test", version="1.0.0")
        manager = ReleaseManager(config)

        valid, errors = manager.validate_checklist()
        assert not valid
        assert len(errors) > 0
        print("  ✓ 未勾选时验证失败")

        manager.check_item("version_bump", True)
        manager.check_item("changelog_update", True)
        manager.check_item("tests_pass", True)
        manager.check_item("code_review", True)
        manager.check_item("docs_complete", True)
        manager.check_item("security_scan", True)
        manager.check_item("package_build", True)
        manager.check_item("release_notes", True)

        valid, errors = manager.validate_checklist()
        assert valid, f"Expected valid but got errors: {errors}"
        assert len(errors) == 0
        print("  ✓ 所有必需项勾选后验证通过")

        manager.add_checklist_item("custom_check", "自定义检查项", required=True)
        valid, errors = manager.validate_checklist()
        assert not valid
        print("  ✓ 新增必需未勾选项后验证失败")

        manager.check_item("custom_check", True)
        valid, errors = manager.validate_checklist()
        assert valid
        print("  ✓ 自定义项勾选后验证通过")

        status = manager.get_checklist_status()
        expected_pct = round(status["checked"] / status["total"] * 100, 2)
        assert status["percentage"] == expected_pct
        print(f"  ✓ 检查清单完成度 {status['percentage']}%")

        print("[Pass] Release Checklist\n")
        return True
    except Exception as e:
        print(f"[Fail] Release Checklist: {e}\n")
        return False


def test_release_pipeline() -> bool:
    print("[Test] ReleaseManager - 发布流水线")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ReleaseConfig(
                name="PipelineTest",
                version="1.0.0",
                output_dir=os.path.join(tmpdir, "dist"),
            )
            manager = ReleaseManager(config)

            # 勾选所有必需项
            for item in manager.checklist:
                if item.required:
                    manager.check_item(item.name, True)

            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "app.py"), "w") as f:
                f.write("# app")

            result = manager.run_release_pipeline(
                source_paths=[src_dir],
                notes_entries={
                    "feature": ["新增模块"],
                    "fix": ["修复Bug"],
                },
                package_format="zip",
            )

            assert result["version"] == "1.0.0"
            assert os.path.exists(result["package_path"])
            assert os.path.exists(result["notes_path"])
            print(f"  ✓ 流水线执行成功")
            print(f"  ✓ 包路径: {result['package_path']}")
            print(f"  ✓ 说明路径: {result['notes_path']}")

            # 测试 prepare_release
            manager.prepare_release(ReleaseType.MINOR)
            assert manager.config.version == "1.1.0"
            assert manager.version_manager.version == "1.1.0"
            print("  ✓ prepare_release 版本升级: 1.0.0 -> 1.1.0")

            # 测试状态保存
            state_path = os.path.join(tmpdir, "state.json")
            manager.save_state(state_path)
            assert os.path.exists(state_path)
            print("  ✓ 状态保存通过")

        print("[Pass] Release Pipeline\n")
        return True
    except Exception as e:
        print(f"[Fail] Release Pipeline: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段50验证脚本：产品化发布准备")
    print("=" * 60 + "\n")

    results = []
    results.append(("VersionManager", test_version_manager()))
    results.append(("ReleaseNotes", test_release_notes()))
    results.append(("PackageBuilder", test_package_builder()))
    results.append(("ReleaseManager Init", test_release_manager_init()))
    results.append(("Release Checklist", test_release_checklist()))
    results.append(("Release Pipeline", test_release_pipeline()))

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
        print("🎉 所有测试通过！阶段50验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
