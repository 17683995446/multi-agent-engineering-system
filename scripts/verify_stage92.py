"""
阶段92验证脚本：文档生成器模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.doc_generator import (
    APIDocGenerator,
    ChangelogGenerator,
    DocEngine,
    GuideGenerator,
    ModuleDocGenerator,
)


def create_test_file(content: str) -> Path:
    """创建临时测试文件"""
    fd, path = tempfile.mkstemp(suffix=".py")
    with open(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return Path(path)


def test_api_doc_generator():
    """测试API文档生成器"""
    source = '''
"""测试模块"""

class MyClass:
    """示例类"""
    def method(self, x: int) -> int:
        """示例方法"""
        return x * 2

def my_func(a, b=10):
    """示例函数"""
    return a + b
'''
    test_file = create_test_file(source)
    gen = APIDocGenerator()
    entries = gen.generate_from_file(test_file)

    assert len(entries) >= 2
    names = [e.name for e in entries]
    assert "MyClass" in names
    assert "my_func" in names

    md = gen.generate_markdown()
    assert "# API 文档" in md
    assert "MyClass" in md

    json_str = gen.generate_json()
    assert "MyClass" in json_str
    print("✓ API文档生成器测试通过")
    test_file.unlink()


def test_module_doc_generator():
    """测试模块文档生成器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "mod_a.py").write_text(
            '"""模块A说明"""\nimport os\nclass A:\n    pass\n', encoding="utf-8"
        )
        (tmpdir / "mod_b.py").write_text(
            '"""模块B说明"""\nfrom typing import List\ndef b():\n    pass\n', encoding="utf-8"
        )

        gen = ModuleDocGenerator()
        modules = gen.generate_from_directory(tmpdir)

        assert "mod_a" in modules
        assert "mod_b" in modules
        assert modules["mod_a"].description == "模块A说明"
        assert "os" in modules["mod_a"].dependencies

        md = gen.generate_markdown()
        assert "模块A说明" in md
        print("✓ 模块文档生成器测试通过")


def test_changelog_generator():
    """测试变更日志生成器"""
    gen = ChangelogGenerator()
    gen.add_entry("1.1.0", [
        {"type": "added", "description": "新增功能A"},
        {"type": "fixed", "description": "修复问题B"},
    ], date="2026-05-01")
    gen.add_entry("1.0.0", [
        {"type": "added", "description": "初始版本"},
    ], date="2026-04-01")

    md = gen.generate_markdown()
    assert "# 变更日志" in md
    assert "1.1.0" in md
    assert "1.0.0" in md
    assert "新增功能A" in md

    json_str = gen.generate_json()
    assert "1.1.0" in json_str
    print("✓ 变更日志生成器测试通过")


def test_guide_generator():
    """测试使用指南生成器"""
    gen = GuideGenerator()
    gen.add_section("快速开始", "这是快速开始内容")
    gen.add_section("高级用法", "这是高级用法内容", level=3)

    md = gen.generate_markdown()
    assert "# 使用指南" in md
    assert "快速开始" in md
    assert "高级用法" in md

    quickstart = gen.generate_quickstart("mylib", [
        "import mylib\nmylib.run()",
        "from mylib import helper\nhelper.do()",
    ])
    assert "mylib 快速入门" in quickstart
    assert "pip install mylib" in quickstart
    assert "import mylib" in quickstart
    print("✓ 使用指南生成器测试通过")


def test_doc_engine():
    """测试文档引擎"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "test_mod.py").write_text(
            'def hello():\n    """问候函数"""\n    return "hello"\n', encoding="utf-8"
        )

        out_dir = tmpdir / "docs"
        engine = DocEngine(output_dir=out_dir)
        results = engine.generate_all(tmpdir)

        assert "api" in results
        assert "module" in results
        assert "changelog" in results
        assert results["api"].exists()
        assert results["module"].exists()

        status = engine.get_status()
        assert status["api_entries"] > 0
        assert status["modules"] > 0
        print("✓ 文档引擎测试通过")


def main():
    print("=" * 60)
    print("阶段92验证：文档生成器模块")
    print("=" * 60)

    test_api_doc_generator()
    test_module_doc_generator()
    test_changelog_generator()
    test_guide_generator()
    test_doc_engine()

    print("=" * 60)
    print("阶段92验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
