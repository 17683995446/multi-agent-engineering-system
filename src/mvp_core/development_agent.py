"""
MVP阶段5: 开发Agent
遵循第一性原理：责任正交性、状态分离、原子化规范
"""

import ast
import inspect
import os
import shutil
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus
from src.common.utils import setup_logger, AgentException

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class CodeSnippet:
    """代码片段 - 原子化代码单元"""
    name: str
    code_type: str  # function, class, module
    source: str
    docstring: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeChange:
    """代码变更记录"""
    file_path: str
    original: Optional[str]
    modified: str
    change_type: str  # add, modify, delete
    timestamp: datetime = field(default_factory=datetime.now)
    backup_path: Optional[str] = None


@dataclass
class AnalysisResult:
    """代码分析结果"""
    file_path: str
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CodeGenerator - 代码生成器
# ---------------------------------------------------------------------------

class CodeGenerator:
    """
    代码生成器 - 负责生成符合原子化规范的代码

    核心方法：
    - generate_function: 生成函数模板
    - generate_class: 生成类模板
    - generate_module: 生成模块模板
    """

    @staticmethod
    def generate_function(
        name: str,
        params: Optional[List[Tuple[str, Optional[str], Optional[str]]]] = None,
        return_type: Optional[str] = None,
        docstring: Optional[str] = None,
        body: Optional[List[str]] = None,
        decorators: Optional[List[str]] = None
    ) -> CodeSnippet:
        """
        生成函数模板

        Args:
            name: 函数名
            params: 参数列表 [(name, type_hint, default), ...]
            return_type: 返回类型注解
            docstring: 文档字符串
            body: 函数体代码行列表
            decorators: 装饰器列表
        """
        lines: List[str] = []

        # 装饰器
        if decorators:
            for dec in decorators:
                lines.append(f"@{dec}")

        # 函数签名
        param_str = CodeGenerator._build_param_string(params or [])
        ret = f" -> {return_type}" if return_type else ""
        lines.append(f"def {name}({param_str}){ret}:")

        # 文档字符串
        if docstring:
            ds = docstring.strip()
            lines.append(f'    """{ds}"""')

        # 函数体
        if body:
            for line in body:
                lines.append(f"    {line}")
        else:
            lines.append("    pass")

        source = "\n".join(lines) + "\n"
        return CodeSnippet(
            name=name,
            code_type="function",
            source=source,
            docstring=docstring,
        )

    @staticmethod
    def generate_class(
        name: str,
        bases: Optional[List[str]] = None,
        docstring: Optional[str] = None,
        methods: Optional[List[CodeSnippet]] = None,
        attributes: Optional[List[Tuple[str, Optional[str], Optional[str]]]] = None,
        decorators: Optional[List[str]] = None
    ) -> CodeSnippet:
        """
        生成类模板

        Args:
            name: 类名
            bases: 基类列表
            docstring: 文档字符串
            methods: 方法列表（CodeSnippet）
            attributes: 属性列表 [(name, type_hint, default), ...]
            decorators: 装饰器列表
        """
        lines: List[str] = []

        if decorators:
            for dec in decorators:
                lines.append(f"@{dec}")

        base_str = f"({', '.join(bases)})" if bases else ""
        lines.append(f"class {name}{base_str}:")

        if docstring:
            lines.append(f'    """{docstring.strip()}"""')

        # 类属性
        if attributes:
            for attr_name, attr_type, attr_default in attributes:
                type_ann = f": {attr_type}" if attr_type else ""
                default = f" = {attr_default}" if attr_default is not None else ""
                lines.append(f"    {attr_name}{type_ann}{default}")
            lines.append("")

        # 方法
        if methods:
            for method in methods:
                # 缩进方法体
                indented = textwrap.indent(method.source, "    ")
                lines.append(indented)
                lines.append("")
        else:
            lines.append("    pass")

        source = "\n".join(lines) + "\n"
        deps = [b for b in (bases or []) if b not in ("object", "ABC")]
        return CodeSnippet(
            name=name,
            code_type="class",
            source=source,
            docstring=docstring,
            dependencies=deps,
        )

    @staticmethod
    def generate_module(
        module_name: str,
        docstring: Optional[str] = None,
        imports: Optional[List[str]] = None,
        snippets: Optional[List[CodeSnippet]] = None
    ) -> CodeSnippet:
        """
        生成模块模板

        Args:
            module_name: 模块名
            docstring: 模块文档字符串
            imports: 导入语句列表
            snippets: 模块内代码片段列表
        """
        lines: List[str] = []

        if docstring:
            lines.append(f'"""{docstring.strip()}"""')
            lines.append("")

        if imports:
            for imp in imports:
                lines.append(imp)
            lines.append("")

        all_deps: List[str] = []
        if snippets:
            for snippet in snippets:
                lines.append(snippet.source)
                lines.append("")
                all_deps.extend(snippet.dependencies)

        source = "\n".join(lines)
        return CodeSnippet(
            name=module_name,
            code_type="module",
            source=source,
            docstring=docstring,
            dependencies=list(set(all_deps)),
        )

    @staticmethod
    def _build_param_string(params: List[Tuple[str, Optional[str], Optional[str]]]) -> str:
        """构建参数字符串"""
        parts: List[str] = []
        for name, type_hint, default in params:
            part = name
            if type_hint:
                part += f": {type_hint}"
            if default is not None:
                part += f" = {default}"
            parts.append(part)
        return ", ".join(parts)


# ---------------------------------------------------------------------------
# CodeModifier - 代码修改器
# ---------------------------------------------------------------------------

class CodeModifier:
    """
    代码修改器 - 安全修改代码文件

    核心方法：
    - modify_file: 修改文件内容
    - insert_after: 在指定内容后插入
    - replace_section: 替换代码段
    - delete_section: 删除代码段
    """

    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = backup_dir or ".backups"
        self.history: List[CodeChange] = []
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

    def _backup(self, file_path: str) -> str:
        """备份原文件"""
        src = Path(file_path)
        if not src.exists():
            return ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{src.stem}_{timestamp}{src.suffix}"
        backup_path = Path(self.backup_dir) / backup_name
        shutil.copy2(src, backup_path)
        logger.info(f"文件已备份: {backup_path}")
        return str(backup_path)

    def modify_file(self, file_path: str, new_content: str) -> CodeChange:
        """安全修改文件内容（全量替换）"""
        original = ""
        path = Path(file_path)
        if path.exists():
            original = path.read_text(encoding="utf-8")

        backup = self._backup(file_path) if path.exists() else None

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")

        change = CodeChange(
            file_path=file_path,
            original=original,
            modified=new_content,
            change_type="modify" if original else "add",
            backup_path=backup,
        )
        self.history.append(change)
        logger.info(f"文件已修改: {file_path}")
        return change

    def insert_after(self, file_path: str, target: str, new_code: str) -> CodeChange:
        """在目标代码后插入新代码"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        original = path.read_text(encoding="utf-8")
        if target not in original:
            raise ValueError(f"目标代码未找到: {target}")

        modified = original.replace(target, target + "\n" + new_code, 1)
        return self.modify_file(file_path, modified)

    def replace_section(self, file_path: str, old_section: str, new_section: str) -> CodeChange:
        """替换代码段"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        original = path.read_text(encoding="utf-8")
        if old_section not in original:
            raise ValueError(f"旧代码段未找到: {old_section[:50]}...")

        modified = original.replace(old_section, new_section, 1)
        return self.modify_file(file_path, modified)

    def delete_section(self, file_path: str, section: str) -> CodeChange:
        """删除代码段"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        original = path.read_text(encoding="utf-8")
        if section not in original:
            raise ValueError(f"代码段未找到: {section[:50]}...")

        modified = original.replace(section, "", 1)
        return self.modify_file(file_path, modified)

    def get_history(self) -> List[CodeChange]:
        """获取修改历史"""
        return self.history.copy()

    def rollback(self, file_path: str) -> bool:
        """回滚最近一次的修改"""
        for change in reversed(self.history):
            if change.file_path == file_path and change.backup_path:
                shutil.copy2(change.backup_path, file_path)
                logger.info(f"文件已回滚: {file_path}")
                return True
        return False


# ---------------------------------------------------------------------------
# DevelopmentAgent - 开发Agent
# ---------------------------------------------------------------------------

class DevelopmentAgent(AgentBase):
    """
    开发Agent - 负责代码生成、修改、重构和分析

    核心职责：
    - 代码生成：根据需求生成Python代码
    - 代码修改：修改现有代码文件
    - 代码重构：执行简单重构操作
    - 代码分析：分析代码结构
    """

    def __init__(self, name: str = "development_agent", message_bus: Optional[MessageBus] = None):
        super().__init__(name=name, message_bus=message_bus)
        self.generator = CodeGenerator()
        self.modifier = CodeModifier()
        self._generated_snippets: Dict[str, CodeSnippet] = {}
        logger.info(f"DevelopmentAgent初始化完成: {name}")

    # ------------------------------
    # 代码生成
    # ------------------------------

    def generate_code(self, task: Dict[str, Any]) -> CodeSnippet:
        """
        根据需求生成代码

        task格式：
        {
            "type": "function" | "class" | "module",
            "name": str,
            ... 其他参数
        }
        """
        code_type = task.get("type", "function")
        name = task.get("name", "unnamed")

        if code_type == "function":
            snippet = self.generator.generate_function(
                name=name,
                params=task.get("params"),
                return_type=task.get("return_type"),
                docstring=task.get("docstring"),
                body=task.get("body"),
                decorators=task.get("decorators"),
            )
        elif code_type == "class":
            methods = task.get("methods", [])
            method_snippets = []
            for m in methods:
                method_snippets.append(self.generator.generate_function(**m))
            snippet = self.generator.generate_class(
                name=name,
                bases=task.get("bases"),
                docstring=task.get("docstring"),
                methods=method_snippets,
                attributes=task.get("attributes"),
                decorators=task.get("decorators"),
            )
        elif code_type == "module":
            snippets = task.get("snippets", [])
            snippet_snippets = []
            for s in snippets:
                snippet_snippets.append(self.generate_code(s))
            snippet = self.generator.generate_module(
                module_name=name,
                docstring=task.get("docstring"),
                imports=task.get("imports"),
                snippets=snippet_snippets,
            )
        else:
            raise AgentException(f"不支持的代码类型: {code_type}")

        self._generated_snippets[name] = snippet
        logger.info(f"代码生成完成: {name} ({code_type})")
        return snippet

    # ------------------------------
    # 代码修改
    # ------------------------------

    def modify_code(self, task: Dict[str, Any]) -> CodeChange:
        """
        修改现有代码文件

        task格式：
        {
            "file_path": str,
            "operation": "modify" | "insert_after" | "replace" | "delete",
            ... 其他参数
        }
        """
        file_path = task["file_path"]
        operation = task.get("operation", "modify")

        if operation == "modify":
            return self.modifier.modify_file(file_path, task["content"])
        elif operation == "insert_after":
            return self.modifier.insert_after(file_path, task["target"], task["content"])
        elif operation == "replace":
            return self.modifier.replace_section(file_path, task["old_section"], task["new_section"])
        elif operation == "delete":
            return self.modifier.delete_section(file_path, task["section"])
        else:
            raise AgentException(f"不支持的操作类型: {operation}")

    # ------------------------------
    # 代码重构
    # ------------------------------

    def refactor_code(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行简单重构操作

        task格式：
        {
            "file_path": str,
            "refactor_type": "extract_method" | "rename" | "reorder",
            ... 其他参数
        }
        """
        refactor_type = task.get("refactor_type")
        file_path = task.get("file_path")

        if refactor_type == "rename":
            return self._refactor_rename(file_path, task["old_name"], task["new_name"])
        elif refactor_type == "reorder":
            return self._refactor_reorder(file_path, task.get("order", []))
        else:
            raise AgentException(f"不支持的重构类型: {refactor_type}")

    def _refactor_rename(self, file_path: str, old_name: str, new_name: str) -> Dict[str, Any]:
        """重命名标识符"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")
        # 简单文本替换（生产环境应使用AST）
        modified = content.replace(old_name, new_name)
        change = self.modifier.modify_file(file_path, modified)

        return {
            "refactor_type": "rename",
            "old_name": old_name,
            "new_name": new_name,
            "change": change,
        }

    def _refactor_reorder(self, file_path: str, order: List[str]) -> Dict[str, Any]:
        """按指定顺序重排类或函数"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")
        # 解析并重新排序（简化实现）
        tree = ast.parse(content)
        nodes: Dict[str, ast.AST] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                nodes[node.name] = node

        # 按order顺序提取源代码段
        lines = content.splitlines(keepends=True)
        new_lines: List[str] = []
        imported = set()

        # 保留导入和模块级语句
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                start = node.lineno - 1
                end = getattr(node, 'end_lineno', node.lineno)
                for i in range(start, end):
                    if i < len(lines):
                        new_lines.append(lines[i])
                        imported.add(i)

        new_lines.append("\n")

        for name in order:
            if name in nodes:
                node = nodes[name]
                start = node.lineno - 1
                end = getattr(node, 'end_lineno', node.lineno)
                for i in range(start, end):
                    if i < len(lines) and i not in imported:
                        new_lines.append(lines[i])
                        imported.add(i)
                new_lines.append("\n")

        modified = "".join(new_lines)
        change = self.modifier.modify_file(file_path, modified)

        return {
            "refactor_type": "reorder",
            "order": order,
            "change": change,
        }

    # ------------------------------
    # 代码分析
    # ------------------------------

    def analyze_code(self, task: Dict[str, Any]) -> AnalysisResult:
        """
        分析代码结构

        task格式：
        {
            "file_path": str,
            "analysis_type": "structure" | "metrics" | "all"
        }
        """
        file_path = task["file_path"]
        analysis_type = task.get("analysis_type", "all")
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = path.read_text(encoding="utf-8")
        result = AnalysisResult(file_path=file_path)

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            result.issues.append(f"语法错误: {e}")
            return result

        # 统一解析AST节点，供structure和metrics共用
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                result.classes.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "methods": methods,
                    "bases": [ast.unparse(b) for b in node.bases],
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.functions.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result.imports.append(alias.name)
                else:
                    module = node.module or ""
                    for alias in node.names:
                        result.imports.append(f"{module}.{alias.name}")

        if analysis_type in ("metrics", "all"):
            result.metrics = {
                "total_lines": len(content.splitlines()),
                "code_lines": len([l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]),
                "class_count": len(result.classes),
                "function_count": len(result.functions),
                "import_count": len(result.imports),
            }

        # 若仅metrics模式，清空明细列表以符合语义
        if analysis_type == "metrics":
            result.classes.clear()
            result.functions.clear()
            result.imports.clear()

        logger.info(f"代码分析完成: {file_path}")
        return result

    # ------------------------------
    # AgentBase 抽象方法实现
    # ------------------------------

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务 - DevelopmentAgent核心入口

        task格式：
        {
            "action": "generate" | "modify" | "refactor" | "analyze",
            ... 其他参数
        }
        """
        action = task.get("action")
        self.status = AgentStatus.BUSY

        try:
            if action == "generate":
                snippet = self.generate_code(task)
                return {
                    "success": True,
                    "action": action,
                    "snippet": snippet,
                }
            elif action == "modify":
                change = self.modify_code(task)
                return {
                    "success": True,
                    "action": action,
                    "change": change,
                }
            elif action == "refactor":
                result = self.refactor_code(task)
                return {
                    "success": True,
                    "action": action,
                    "result": result,
                }
            elif action == "analyze":
                result = self.analyze_code(task)
                return {
                    "success": True,
                    "action": action,
                    "result": result,
                }
            else:
                raise AgentException(f"不支持的操作: {action}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"任务执行失败: {e}")
            return {
                "success": False,
                "action": action,
                "error": str(e),
            }
        finally:
            self.status = AgentStatus.IDLE
