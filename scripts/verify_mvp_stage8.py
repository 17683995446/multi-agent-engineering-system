"""
MVP阶段8验证脚本：文档Agent
测试内容：
1. 文档Agent初始化
2. API文档生成
3. README生成
4. 变更日志生成
5. 文档格式化
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mvp_core.document_agent import (
    DocumentAgent,
    APIDocGenerator,
    READMEGenerator,
    ChangelogGenerator,
    DocFormatter,
    APIDocEntry,
    ChangelogEntry,
)
from src.mvp_core.agent_base import MessageBus, AgentStatus


def test_init():
    """1. 文档Agent初始化"""
    print("[TEST] 文档Agent初始化...")

    bus = MessageBus("test_bus")
    agent = DocumentAgent(name="doc_agent", message_bus=bus)
    assert agent.name == "doc_agent"
    assert agent.status == AgentStatus.IDLE
    assert agent.api_generator is not None
    assert agent.readme_generator is not None
    assert agent.changelog_generator is not None
    assert agent.formatter is not None

    # 测试initialize/shutdown
    assert agent.initialize() is True
    assert agent.get_status()["running"] is True
    assert agent.shutdown() is True
    assert agent.get_status()["running"] is False

    print("  ✓ 初始化通过")


def test_api_doc_generation():
    """2. API文档生成"""
    print("[TEST] API文档生成...")

    source = '''
"""
示例模块文档字符串
"""

def add(a: int, b: int) -> int:
    """返回两个数的和"""
    return a + b

class Calculator:
    """计算器类"""

    def multiply(self, x: int, y: int) -> int:
        """返回两个数的乘积"""
        return x * y
'''

    generator = APIDocGenerator()
    entries = generator.extract_from_source(source, file_path="demo.py")
    assert len(entries) == 3  # module + function + class

    module_entry = entries[0]
    assert module_entry.doc_type == "module"
    assert "示例模块" in (module_entry.docstring or "")

    func_entry = next(e for e in entries if e.doc_type == "function")
    assert func_entry.name == "add"
    assert "返回两个数的和" in (func_entry.docstring or "")
    assert func_entry.returns == "int"

    class_entry = next(e for e in entries if e.doc_type == "class")
    assert class_entry.name == "Calculator"
    assert len(class_entry.args) == 1  # multiply method

    md = generator.generate_markdown(entries, title="Demo API")
    assert "# Demo API" in md
    assert "## 函数: `add`" in md
    assert "## 类: `Calculator`" in md
    assert "```python" in md

    # 通过DocumentAgent执行
    agent = DocumentAgent()
    result = agent.execute({
        "action": "api_docs",
        "source": source,
        "title": "Test API",
    })
    assert result["success"] is True
    assert "Test API" in result["content"]

    print("  ✓ API文档生成通过")


def test_readme_generation():
    """3. README生成"""
    print("[TEST] README生成...")

    generator = READMEGenerator()
    readme = generator.generate(
        project_name="TestProject",
        description="这是一个测试项目。",
        install_instructions=["```bash", "pip install testproject", "```"],
        usage_examples=[{"title": "快速开始", "code": "import testproject\ntestproject.run()"}],
    )
    assert "# TestProject" in readme
    assert "这是一个测试项目" in readme
    assert "pip install testproject" in readme
    assert "快速开始" in readme
    assert "import testproject" in readme

    # 通过DocumentAgent执行
    agent = DocumentAgent()
    result = agent.execute({
        "action": "readme",
        "project_name": "MyProject",
        "description": "我的项目描述",
    })
    assert result["success"] is True
    assert "# MyProject" in result["content"]

    print("  ✓ README生成通过")


def test_changelog_generation():
    """4. 变更日志生成"""
    print("[TEST] 变更日志生成...")

    generator = ChangelogGenerator()
    entries = [
        ChangelogEntry(
            version="1.0.0",
            date="2024-01-01",
            changes=["新增核心功能", "修复已知问题"],
            category="Added",
        ),
        ChangelogEntry(
            version="0.1.0",
            date="2023-12-01",
            changes=["初始版本"],
        ),
    ]
    changelog = generator.generate(entries)
    assert "# Changelog" in changelog
    assert "## [1.0.0] - 2024-01-01" in changelog
    assert "新增核心功能" in changelog
    assert "初始版本" in changelog

    # 测试追加
    existing = "# Changelog\n\n已有内容\n"
    updated = generator.add_entry(existing, entries[0])
    assert "## [1.0.0] - 2024-01-01" in updated
    assert "已有内容" in updated

    # 测试解析
    parsed = generator.parse_existing(updated)
    assert len(parsed) >= 1
    assert parsed[0].version == "1.0.0"

    # 通过DocumentAgent执行
    agent = DocumentAgent()
    result = agent.execute({
        "action": "changelog",
        "entries": [
            {"version": "2.0.0", "date": "2024-06-01", "changes": ["重大更新"]},
        ],
        "title": "Release Notes",
    })
    assert result["success"] is True
    assert "## [2.0.0] - 2024-06-01" in result["content"]

    print("  ✓ 变更日志生成通过")


def test_document_formatting():
    """5. 文档格式化"""
    print("[TEST] 文档格式化...")

    formatter = DocFormatter()

    # format_markdown
    raw = "# Title\n\n\n\nSome text.  \n\n\nMore text.\n\n"
    formatted = formatter.format_markdown(raw)
    assert formatted.count("\n\n") <= 2  # 合并连续空行
    assert formatted.endswith("\n")

    # normalize_headers
    headers = "#### 太深\n\n##### 更深"
    normalized = formatter.normalize_headers(headers, max_level=3)
    assert "### 太深" in normalized
    assert "### 更深" in normalized

    # wrap_code_blocks
    code = "    def hello():\n        pass\n"
    wrapped = formatter.wrap_code_blocks(code)
    assert "```python" in wrapped

    # 通过DocumentAgent执行
    agent = DocumentAgent()
    result = agent.execute({
        "action": "format",
        "content": "# Hello\n\n\nWorld  \n",
        "operations": ["markdown"],
    })
    assert result["success"] is True
    assert "# Hello" in result["content"]
    assert "World" in result["content"]

    print("  ✓ 文档格式化通过")


def test_file_output():
    """测试文件输出能力"""
    print("[TEST] 文件输出...")

    with tempfile.TemporaryDirectory() as tmpdir:
        agent = DocumentAgent()

        # API文档输出到文件
        api_path = Path(tmpdir) / "api.md"
        agent.execute({
            "action": "api_docs",
            "source": 'def foo():\n    """Foo doc."""\n    pass',
            "output_path": str(api_path),
        })
        assert api_path.exists()
        assert "Foo doc." in api_path.read_text(encoding="utf-8")

        # README输出到文件
        readme_path = Path(tmpdir) / "README.md"
        agent.execute({
            "action": "readme",
            "project_name": "TmpProject",
            "description": "临时项目",
            "output_path": str(readme_path),
        })
        assert readme_path.exists()

        # Changelog输出到文件
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        agent.execute({
            "action": "changelog",
            "entries": [{"version": "0.1.0", "date": "2024-01-01", "changes": ["init"]}],
            "output_path": str(changelog_path),
        })
        assert changelog_path.exists()

    print("  ✓ 文件输出通过")


def main():
    print("=" * 60)
    print("MVP阶段8验证: 文档Agent")
    print("=" * 60)
    print()

    try:
        test_init()
        test_api_doc_generation()
        test_readme_generation()
        test_changelog_generation()
        test_document_formatting()
        test_file_output()
    except AssertionError as e:
        print(f"\n✗ 验证失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 验证异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 60)
    print("✓ MVP阶段8验证全部通过")
    print("=" * 60)
    print()
    print("验证项总结:")
    print("  1. 文档Agent初始化        ✓")
    print("  2. API文档生成            ✓")
    print("  3. README生成             ✓")
    print("  4. 变更日志生成           ✓")
    print("  5. 文档格式化             ✓")
    print("  6. 文件输出               ✓")
    print()


if __name__ == "__main__":
    main()
