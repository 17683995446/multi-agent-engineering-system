#!/usr/bin/env python3
"""
MVP阶段5验证脚本
测试内容：
1. 开发Agent初始化
2. 代码生成
3. 代码修改
4. 代码分析
5. 原子规范遵循
"""

import os
import sys
import tempfile
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.mvp_core.development_agent import (
    DevelopmentAgent,
    CodeGenerator,
    CodeModifier,
    CodeSnippet,
    CodeChange,
    AnalysisResult,
)
from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

_tests_passed = 0
_tests_failed = 0


def assert_true(condition: bool, message: str):
    global _tests_passed, _tests_failed
    if condition:
        print(f"  {PASS} {message}")
        _tests_passed += 1
    else:
        print(f"  {FAIL} {message}")
        _tests_failed += 1


def assert_equal(actual, expected, message: str):
    assert_true(actual == expected, f"{message} (expected={expected}, actual={actual})")


# ---------------------------------------------------------------------------
# 测试1: 开发Agent初始化
# ---------------------------------------------------------------------------

def test_agent_initialization():
    print("\n[测试1] 开发Agent初始化")

    # 1.1 无消息总线初始化
    agent = DevelopmentAgent(name="dev_agent_1")
    assert_equal(agent.name, "dev_agent_1", "Agent名称正确")
    assert_equal(agent.status, AgentStatus.IDLE, "初始状态为IDLE")
    assert_true(isinstance(agent.generator, CodeGenerator), "包含CodeGenerator")
    assert_true(isinstance(agent.modifier, CodeModifier), "包含CodeModifier")

    # 1.2 带消息总线初始化
    bus = MessageBus(name="test_bus")
    agent2 = DevelopmentAgent(name="dev_agent_2", message_bus=bus)
    assert_equal(agent2.message_bus, bus, "消息总线已绑定")

    # 1.3 initialize/shutdown
    ok = agent2.initialize()
    assert_true(ok, "initialize返回True")
    assert_equal(agent2.status, AgentStatus.IDLE, "initialize后状态为IDLE")
    assert_true(agent2._running, "_running标志为True")

    ok = agent2.shutdown()
    assert_true(ok, "shutdown返回True")
    assert_equal(agent2.status, AgentStatus.STOPPED, "shutdown后状态为STOPPED")

    # 1.4 继承AgentBase
    assert_true(issubclass(DevelopmentAgent, AgentBase), "DevelopmentAgent继承AgentBase")


# ---------------------------------------------------------------------------
# 测试2: 代码生成
# ---------------------------------------------------------------------------

def test_code_generation():
    print("\n[测试2] 代码生成")

    agent = DevelopmentAgent(name="gen_agent")

    # 2.1 生成函数
    task = {
        "action": "generate",
        "type": "function",
        "name": "calculate_sum",
        "params": [("a", "int", None), ("b", "int", "0")],
        "return_type": "int",
        "docstring": "计算两个数的和",
        "body": ["return a + b"],
    }
    result = agent.execute(task)
    assert_true(result["success"], "生成函数成功")
    snippet = result["snippet"]
    assert_true(isinstance(snippet, CodeSnippet), "返回CodeSnippet")
    assert_equal(snippet.name, "calculate_sum", "函数名正确")
    assert_equal(snippet.code_type, "function", "代码类型为function")
    assert_true("def calculate_sum(a: int, b: int = 0) -> int:" in snippet.source, "函数签名正确")
    assert_true('"""计算两个数的和"""' in snippet.source, "文档字符串正确")
    assert_true("return a + b" in snippet.source, "函数体正确")

    # 2.2 生成类
    task_class = {
        "action": "generate",
        "type": "class",
        "name": "Calculator",
        "bases": ["object"],
        "docstring": "简单计算器类",
        "attributes": [("value", "int", "0")],
        "methods": [
            {
                "name": "add",
                "params": [("self", None, None), ("x", "int", None)],
                "return_type": "int",
                "body": ["return self.value + x"],
            }
        ],
    }
    result = agent.execute(task_class)
    assert_true(result["success"], "生成类成功")
    snippet = result["snippet"]
    assert_equal(snippet.code_type, "class", "代码类型为class")
    assert_true("class Calculator(object):" in snippet.source, "类定义正确")
    assert_true("value: int = 0" in snippet.source, "类属性正确")
    assert_true("def add(self, x: int) -> int:" in snippet.source, "方法定义正确")

    # 2.3 生成模块
    task_module = {
        "action": "generate",
        "type": "module",
        "name": "math_utils",
        "docstring": "数学工具模块",
        "imports": ["from typing import List"],
        "snippets": [
            {
                "type": "function",
                "name": "sum_list",
                "params": [("numbers", "List[int]", None)],
                "return_type": "int",
                "body": ["return sum(numbers)"],
            }
        ],
    }
    result = agent.execute(task_module)
    assert_true(result["success"], "生成模块成功")
    snippet = result["snippet"]
    assert_equal(snippet.code_type, "module", "代码类型为module")
    assert_true('"""数学工具模块"""' in snippet.source, "模块文档字符串正确")
    assert_true("from typing import List" in snippet.source, "导入语句正确")
    assert_true("def sum_list(numbers: List[int]) -> int:" in snippet.source, "模块内函数正确")


# ---------------------------------------------------------------------------
# 测试3: 代码修改
# ---------------------------------------------------------------------------

def test_code_modification():
    print("\n[测试3] 代码修改")

    agent = DevelopmentAgent(name="mod_agent")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_module.py")
        original_content = "# Original module\ndef foo():\n    pass\n"
        Path(test_file).write_text(original_content, encoding="utf-8")

        # 3.1 全量修改
        new_content = "# Modified module\ndef bar():\n    return 42\n"
        result = agent.execute({
            "action": "modify",
            "file_path": test_file,
            "operation": "modify",
            "content": new_content,
        })
        assert_true(result["success"], "全量修改成功")
        change = result["change"]
        assert_true(isinstance(change, CodeChange), "返回CodeChange")
        assert_equal(change.change_type, "modify", "变更类型为modify")
        assert_true(change.backup_path is not None, "已创建备份")
        assert_true(os.path.exists(change.backup_path), "备份文件存在")
        assert_equal(Path(test_file).read_text(encoding="utf-8"), new_content, "文件内容已更新")

        # 3.2 insert_after
        result = agent.execute({
            "action": "modify",
            "file_path": test_file,
            "operation": "insert_after",
            "target": "def bar():",
            "content": '    """Bar function."""',
        })
        assert_true(result["success"], "insert_after成功")
        content = Path(test_file).read_text(encoding="utf-8")
        assert_true('    """Bar function."""' in content, "插入内容正确")

        # 3.3 replace_section
        result = agent.execute({
            "action": "modify",
            "file_path": test_file,
            "operation": "replace",
            "old_section": "def bar():\n    \"\"\"Bar function.\"\"\"\n    return 42",
            "new_section": "def baz():\n    return 99",
        })
        assert_true(result["success"], "replace_section成功")
        content = Path(test_file).read_text(encoding="utf-8")
        assert_true("def baz():" in content, "替换后内容正确")

        # 3.4 delete_section
        result = agent.execute({
            "action": "modify",
            "file_path": test_file,
            "operation": "delete",
            "section": "# Modified module\n",
        })
        assert_true(result["success"], "delete_section成功")
        content = Path(test_file).read_text(encoding="utf-8")
        assert_true("# Modified module" not in content, "删除后内容正确")

        # 3.5 回滚
        ok = agent.modifier.rollback(test_file)
        assert_true(ok, "回滚成功")
        # 回滚到最近一次备份（delete前的状态）


# ---------------------------------------------------------------------------
# 测试4: 代码分析
# ---------------------------------------------------------------------------

def test_code_analysis():
    print("\n[测试4] 代码分析")

    agent = DevelopmentAgent(name="anal_agent")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "sample.py")
        sample_code = '''"""Sample module."""
from typing import List

class Point:
    """A point in 2D space."""
    x: float = 0.0
    y: float = 0.0

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

def distance(p1: Point, p2: Point) -> float:
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5
'''
        Path(test_file).write_text(sample_code, encoding="utf-8")

        # 4.1 结构分析
        result = agent.execute({
            "action": "analyze",
            "file_path": test_file,
            "analysis_type": "structure",
        })
        assert_true(result["success"], "结构分析成功")
        analysis = result["result"]
        assert_true(isinstance(analysis, AnalysisResult), "返回AnalysisResult")
        assert_equal(len(analysis.classes), 1, "检测到1个类")
        assert_equal(analysis.classes[0]["name"], "Point", "类名正确")
        assert_true("move" in analysis.classes[0]["methods"], "类方法正确")
        assert_equal(len(analysis.functions), 1, "检测到1个函数")
        assert_equal(analysis.functions[0]["name"], "distance", "函数名正确")
        assert_equal(len(analysis.imports), 1, "检测到1个导入")
        assert_true("typing.List" in analysis.imports[0], "导入内容正确")

        # 4.2 指标分析
        result = agent.execute({
            "action": "analyze",
            "file_path": test_file,
            "analysis_type": "metrics",
        })
        assert_true(result["success"], "指标分析成功")
        analysis = result["result"]
        assert_true(analysis.metrics["total_lines"] > 0, "总行数大于0")
        assert_equal(analysis.metrics["class_count"], 1, "类数为1")
        assert_equal(analysis.metrics["function_count"], 1, "函数数为1")
        assert_equal(analysis.metrics["import_count"], 1, "导入数为1")

        # 4.3 全部分析
        result = agent.execute({
            "action": "analyze",
            "file_path": test_file,
            "analysis_type": "all",
        })
        assert_true(result["success"], "全部分析成功")
        analysis = result["result"]
        assert_equal(len(analysis.classes), 1, "all模式包含类信息")
        assert_true("total_lines" in analysis.metrics, "all模式包含指标")


# ---------------------------------------------------------------------------
# 测试5: 原子规范遵循
# ---------------------------------------------------------------------------

def test_atomic_compliance():
    print("\n[测试5] 原子规范遵循")

    agent = DevelopmentAgent(name="atomic_agent")

    # 5.1 每个函数只做一件事
    task = {
        "action": "generate",
        "type": "function",
        "name": "single_purpose_func",
        "params": [("x", "int", None)],
        "return_type": "int",
        "docstring": "只做一件事：返回输入值的平方",
        "body": ["return x * x"],
    }
    result = agent.execute(task)
    assert_true(result["success"], "单职责函数生成成功")
    src = result["snippet"].source
    assert_true(src.count("return") == 1, "函数只有一个return，职责单一")

    # 5.2 类职责单一
    task = {
        "action": "generate",
        "type": "class",
        "name": "DataContainer",
        "docstring": "仅用于存储数据的简单容器",
        "attributes": [("data", "dict", "{}"), ("count", "int", "0")],
        "methods": [
            {
                "name": "get_data",
                "params": [("self", None, None)],
                "return_type": "dict",
                "body": ["return self.data"],
            }
        ],
    }
    result = agent.execute(task)
    assert_true(result["success"], "单职责类生成成功")
    snippet = result["snippet"]
    assert_true(len(snippet.dependencies) == 0, "简单容器无外部依赖，职责单一")

    # 5.3 模块边界清晰
    task = {
        "action": "generate",
        "type": "module",
        "name": "atomic_module",
        "docstring": "原子化模块：仅包含相关工具函数",
        "imports": ["from typing import List, Dict"],
        "snippets": [
            {
                "type": "function",
                "name": "helper_a",
                "params": [],
                "body": ["pass"],
            },
            {
                "type": "function",
                "name": "helper_b",
                "params": [],
                "body": ["pass"],
            },
        ],
    }
    result = agent.execute(task)
    assert_true(result["success"], "原子化模块生成成功")
    src = result["snippet"].source
    assert_true("helper_a" in src and "helper_b" in src, "模块内函数边界清晰")

    # 5.4 CodeModifier原子操作（备份+修改）
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "atomic.txt")
        Path(test_file).write_text("original", encoding="utf-8")
        change = agent.modifier.modify_file(test_file, "modified")
        assert_true(change.backup_path is not None, "修改前自动备份")
        assert_true(os.path.exists(change.backup_path), "备份文件存在")
        assert_equal(Path(test_file).read_text(encoding="utf-8"), "modified", "修改生效")

    # 5.5 DevelopmentAgent状态分离
    assert_true(hasattr(agent, "generator"), "生成器状态独立")
    assert_true(hasattr(agent, "modifier"), "修改器状态独立")
    assert_true(hasattr(agent, "_generated_snippets"), "生成历史状态独立")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("MVP阶段5验证: 开发Agent")
    print("=" * 60)

    test_agent_initialization()
    test_code_generation()
    test_code_modification()
    test_code_analysis()
    test_atomic_compliance()

    print("\n" + "=" * 60)
    print(f"测试结果: {_tests_passed} 通过, {_tests_failed} 失败")
    print("=" * 60)

    if _tests_failed > 0:
        sys.exit(1)
    else:
        print("\n✓ MVP阶段5验证全部通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
