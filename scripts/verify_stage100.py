"""
阶段100验证脚本：系统发布
功能：发布检查清单、版本确认、文档完整性检查、最终验收
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.utils import GlobalConfig


RELEASE_VERSION = "1.0.0"
RELEASE_DATE = "2026-05-31"


def check_directory_structure() -> bool:
    """检查目录结构完整性"""
    required_dirs = [
        GlobalConfig.SRC_DIR / "common",
        GlobalConfig.SRC_DIR / "agents",
        GlobalConfig.SRC_DIR / "code",
        GlobalConfig.SRC_DIR / "workflow",
        GlobalConfig.CONFIGS_DIR,
        GlobalConfig.DOCS_DIR,
        GlobalConfig.LOGS_DIR,
        Path(__file__).parent.parent / "scripts",
        Path(__file__).parent.parent / "tests",
    ]
    all_exist = True
    for d in required_dirs:
        if not d.exists():
            print(f"  ✗ 目录缺失: {d}")
            all_exist = False
    if all_exist:
        print("  ✓ 目录结构完整")
    return all_exist


def check_core_modules() -> bool:
    """检查核心模块存在性"""
    required_modules = [
        GlobalConfig.SRC_DIR / "common" / "utils.py",
        GlobalConfig.SRC_DIR / "common" / "cleanup_tool.py",
        GlobalConfig.SRC_DIR / "common" / "backup_restore.py",
        GlobalConfig.SRC_DIR / "common" / "system_diagnostic.py",
        GlobalConfig.SRC_DIR / "agents" / "base.py",
        GlobalConfig.SRC_DIR / "code" / "parser.py",
        GlobalConfig.SRC_DIR / "workflow" / "orchestrator.py",
        GlobalConfig.SRC_DIR / "main.py",
    ]
    all_exist = True
    for m in required_modules:
        if not m.exists():
            print(f"  ✗ 模块缺失: {m}")
            all_exist = False
    if all_exist:
        print("  ✓ 核心模块完整")
    return all_exist


def check_documentation() -> bool:
    """检查文档完整性"""
    required_docs = [
        GlobalConfig.DOCS_DIR / "stage96_验收报告.md",
        GlobalConfig.DOCS_DIR / "stage97_验收报告.md",
        GlobalConfig.DOCS_DIR / "stage98_验收报告.md",
        GlobalConfig.DOCS_DIR / "stage99_验收报告.md",
        GlobalConfig.DOCS_DIR / "stage100_验收报告.md",
        Path(__file__).parent.parent / "README.md",
    ]
    all_exist = True
    for d in required_docs:
        if not d.exists():
            print(f"  ✗ 文档缺失: {d}")
            all_exist = False
    if all_exist:
        print("  ✓ 文档完整")
    return all_exist


def check_verification_scripts() -> bool:
    """检查验证脚本存在性"""
    required_scripts = [
        Path(__file__).parent.parent / "scripts" / "verify_stage96.py",
        Path(__file__).parent.parent / "scripts" / "verify_stage97.py",
        Path(__file__).parent.parent / "scripts" / "verify_stage98.py",
        Path(__file__).parent.parent / "scripts" / "verify_stage99.py",
        Path(__file__).parent.parent / "scripts" / "verify_stage100.py",
    ]
    all_exist = True
    for s in required_scripts:
        if not s.exists():
            print(f"  ✗ 验证脚本缺失: {s}")
            all_exist = False
    if all_exist:
        print("  ✓ 验证脚本完整")
    return all_exist


def check_configs() -> bool:
    """检查配置文件"""
    configs = list(GlobalConfig.CONFIGS_DIR.glob("*.yaml"))
    if configs:
        print(f"  ✓ 配置文件存在 ({len(configs)} 个)")
        return True
    print("  ! 未找到 YAML 配置文件")
    return True


def check_requirements() -> bool:
    """检查依赖文件"""
    req_file = Path(__file__).parent.parent / "requirements.txt"
    if req_file.exists():
        print("  ✓ requirements.txt 存在")
        return True
    print("  ! requirements.txt 不存在")
    return True


def run_all_verifications() -> bool:
    """运行所有阶段验证脚本"""
    import subprocess
    scripts = [96, 97, 98, 99]
    all_pass = True
    for stage in scripts:
        script = Path(__file__).parent.parent / "scripts" / f"verify_stage{stage}.py"
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                print(f"  ✓ 阶段{stage}验证通过")
            else:
                print(f"  ✗ 阶段{stage}验证失败")
                all_pass = False
        except Exception as e:
            print(f"  ✗ 阶段{stage}验证异常: {e}")
            all_pass = False
    return all_pass


def generate_release_report() -> dict:
    """生成发布报告"""
    return {
        "version": RELEASE_VERSION,
        "release_date": RELEASE_DATE,
        "verified_at": datetime.now().isoformat(),
        "checks": {
            "directory_structure": check_directory_structure(),
            "core_modules": check_core_modules(),
            "documentation": check_documentation(),
            "verification_scripts": check_verification_scripts(),
            "configs": check_configs(),
            "requirements": check_requirements(),
        },
    }


def main():
    print("=" * 60)
    print("阶段100验证：系统发布")
    print("=" * 60)
    print()

    print("1. 发布检查清单:")
    report = generate_release_report()
    all_pass = all(report["checks"].values())
    print()

    print("2. 运行各阶段验证:")
    verify_pass = run_all_verifications()
    print()

    print("3. 版本确认:")
    print(f"   版本号: {RELEASE_VERSION}")
    print(f"   发布日期: {RELEASE_DATE}")
    print(f"   验证时间: {report['verified_at']}")
    print()

    print("4. 最终验收:")
    if all_pass and verify_pass:
        print("   ✓ 所有检查通过")
        print("   ✓ 所有验证通过")
        print("   ✓ 系统可以发布")
    else:
        print("   ✗ 部分检查未通过，请修复后重试")
        return 1
    print()

    print("=" * 60)
    print("阶段100验证全部通过 ✓")
    print("=" * 60)
    print()
    print("发布总结:")
    print(f"  版本: {RELEASE_VERSION}")
    print(f"  日期: {RELEASE_DATE}")
    print("  ✓ 目录结构完整")
    print("  ✓ 核心模块完整")
    print("  ✓ 文档完整")
    print("  ✓ 验证脚本完整")
    print("  ✓ 阶段96-99验证通过")
    print("  ✓ 系统发布就绪")
    return 0


if __name__ == "__main__":
    sys.exit(main())
