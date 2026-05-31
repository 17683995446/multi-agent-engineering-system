"""
文档生成器模块
遵循第一性原理：信息最小熵公理

核心功能：
1. API文档生成（从函数/类签名提取）
2. 模块文档生成
3. 变更文档生成
4. 使用指南生成
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class DocType(Enum):
    """文档类型"""
    API = "api"
    MODULE = "module"
    CHANGELOG = "changelog"
    GUIDE = "guide"


@dataclass
class APIDocEntry:
    """API文档条目"""
    name: str
    doc_type: str
    signature: str
    docstring: str
    parameters: List[Dict[str, str]] = field(default_factory=list)
    returns: str = ""
    raises: List[str] = field(default_factory=list)
    module: str = ""
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.doc_type,
            "signature": self.signature,
            "docstring": self.docstring,
            "parameters": self.parameters,
            "returns": self.returns,
            "raises": self.raises,
            "module": self.module,
            "line_number": self.line_number,
        }


@dataclass
class ChangeEntry:
    """变更记录条目"""
    version: str
    date: str
    changes: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "date": self.date,
            "changes": self.changes,
        }


@dataclass
class ModuleDoc:
    """模块文档"""
    module_name: str
    description: str
    classes: List[APIDocEntry] = field(default_factory=list)
    functions: List[APIDocEntry] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "description": self.description,
            "classes": [c.to_dict() for c in self.classes],
            "functions": [f.to_dict() for f in self.functions],
            "dependencies": self.dependencies,
        }


class APIDocGenerator:
    """API文档生成器"""

    def __init__(self):
        self.entries: List[APIDocEntry] = []

    def generate_from_file(self, file_path: Union[str, Path]) -> List[APIDocEntry]:
        """从Python文件生成API文档"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.warning(f"语法错误，跳过: {file_path}")
            return []

        module_name = file_path.stem
        entries = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                entry = self._parse_class(node, module_name)
                entries.append(entry)
            elif isinstance(node, ast.FunctionDef):
                entry = self._parse_function(node, module_name)
                entries.append(entry)

        self.entries.extend(entries)
        logger.info(f"API文档生成完成: {file_path} ({len(entries)} 条目)")
        return entries

    def _parse_class(self, node: ast.ClassDef, module_name: str) -> APIDocEntry:
        """解析类定义"""
        docstring = ast.get_docstring(node) or ""
        bases = [self._get_name(base) for base in node.bases]
        signature = f"class {node.name}({', '.join(bases)})"

        methods = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                methods.append(child.name)

        return APIDocEntry(
            name=node.name,
            doc_type="class",
            signature=signature,
            docstring=docstring,
            parameters=[{"name": "methods", "type": "list", "default": str(methods)}],
            module=module_name,
            line_number=node.lineno,
        )

    def _parse_function(self, node: ast.FunctionDef, module_name: str) -> APIDocEntry:
        """解析函数定义"""
        docstring = ast.get_docstring(node) or ""
        args = node.args
        params = []

        all_args = args.args + args.kwonlyargs
        defaults_offset = len(all_args) - len(args.defaults) - len(args.kw_defaults)

        for i, arg in enumerate(all_args):
            param_info = {
                "name": arg.arg,
                "type": self._get_annotation(arg.annotation),
                "default": "",
            }
            params.append(param_info)

        signature = f"def {node.name}({', '.join(p['name'] for p in params)})"
        returns = self._get_annotation(args.vararg) if args.vararg else ""

        return APIDocEntry(
            name=node.name,
            doc_type="function",
            signature=signature,
            docstring=docstring,
            parameters=params,
            returns=returns,
            module=module_name,
            line_number=node.lineno,
        )

    def _get_name(self, node: ast.AST) -> str:
        """获取AST节点名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return ""

    def _get_annotation(self, node: Optional[ast.AST]) -> str:
        """获取类型注解字符串"""
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            return f"{self._get_annotation(node.value)}[...]"
        return ""

    def generate_markdown(self, entries: Optional[List[APIDocEntry]] = None) -> str:
        """生成Markdown格式API文档"""
        entries = entries or self.entries
        lines = ["# API 文档\n"]

        current_module = ""
        for entry in entries:
            if entry.module != current_module:
                current_module = entry.module
                lines.append(f"## 模块: {current_module}\n")

            lines.append(f"### {entry.name}\n")
            lines.append(f"- **类型**: {entry.doc_type}\n")
            lines.append(f"- **签名**: `{entry.signature}`\n")
            if entry.docstring:
                lines.append(f"- **说明**: {entry.docstring}\n")
            if entry.parameters:
                lines.append("- **参数**:\n")
                for p in entry.parameters:
                    lines.append(f"  - `{p['name']}` ({p['type']})\n")
            lines.append("")

        return "\n".join(lines)

    def generate_json(self, entries: Optional[List[APIDocEntry]] = None) -> str:
        """生成JSON格式API文档"""
        entries = entries or self.entries
        return json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2)


class ModuleDocGenerator:
    """模块文档生成器"""

    def __init__(self):
        self.modules: Dict[str, ModuleDoc] = {}

    def generate_from_directory(self, directory: Union[str, Path]) -> Dict[str, ModuleDoc]:
        """从目录生成模块文档"""
        directory = Path(directory)
        api_gen = APIDocGenerator()

        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "__init__.py":
                continue

            entries = api_gen.generate_from_file(py_file)
            module_name = py_file.stem

            classes = [e for e in entries if e.doc_type == "class"]
            functions = [e for e in entries if e.doc_type == "function"]

            doc = ModuleDoc(
                module_name=module_name,
                description=self._extract_module_doc(py_file),
                classes=classes,
                functions=functions,
                dependencies=self._extract_imports(py_file),
            )
            self.modules[module_name] = doc

        logger.info(f"模块文档生成完成: {directory} ({len(self.modules)} 模块)")
        return self.modules

    def _extract_module_doc(self, file_path: Path) -> str:
        """提取模块文档字符串"""
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
            return ast.get_docstring(tree) or ""
        except SyntaxError:
            return ""

    def _extract_imports(self, file_path: Path) -> List[str]:
        """提取模块导入依赖"""
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        imports = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
        except SyntaxError:
            pass
        return imports

    def generate_markdown(self) -> str:
        """生成Markdown格式模块文档"""
        lines = ["# 模块文档\n"]
        for name, doc in sorted(self.modules.items()):
            lines.append(f"## {name}\n")
            if doc.description:
                lines.append(f"{doc.description}\n")
            lines.append(f"**依赖**: {', '.join(doc.dependencies) or '无'}\n")
            if doc.classes:
                lines.append(f"**类**: {len(doc.classes)} 个\n")
            if doc.functions:
                lines.append(f"**函数**: {len(doc.functions)} 个\n")
            lines.append("")
        return "\n".join(lines)


class ChangelogGenerator:
    """变更文档生成器"""

    def __init__(self):
        self.entries: List[ChangeEntry] = []

    def add_entry(self, version: str, changes: List[Dict[str, str]], date: Optional[str] = None):
        """添加变更记录"""
        entry = ChangeEntry(
            version=version,
            date=date or datetime.now().strftime("%Y-%m-%d"),
            changes=changes,
        )
        self.entries.append(entry)
        self.entries.sort(key=lambda e: e.version, reverse=True)

    def generate_markdown(self) -> str:
        """生成Markdown格式变更日志"""
        lines = ["# 变更日志\n"]
        for entry in self.entries:
            lines.append(f"## [{entry.version}] - {entry.date}\n")
            for change in entry.changes:
                change_type = change.get("type", "changed")
                desc = change.get("description", "")
                lines.append(f"- **{change_type}**: {desc}\n")
            lines.append("")
        return "\n".join(lines)

    def generate_json(self) -> str:
        """生成JSON格式变更日志"""
        return json.dumps([e.to_dict() for e in self.entries], ensure_ascii=False, indent=2)

    def parse_from_git_log(self, log_text: str) -> List[ChangeEntry]:
        """从git日志解析变更记录（简化版）"""
        entries = []
        lines = log_text.strip().split("\n")
        current_version = ""
        current_changes: List[Dict[str, str]] = []

        for line in lines:
            if line.startswith("##"):
                if current_version and current_changes:
                    entries.append(ChangeEntry(current_version, "", current_changes))
                current_version = line.strip("# []").split("-")[0].strip()
                current_changes = []
            elif line.strip().startswith("-"):
                current_changes.append({"type": "changed", "description": line.strip("- ")})

        if current_version and current_changes:
            entries.append(ChangeEntry(current_version, "", current_changes))

        self.entries.extend(entries)
        return entries


class GuideGenerator:
    """使用指南生成器"""

    def __init__(self):
        self.sections: List[Dict[str, str]] = []

    def add_section(self, title: str, content: str, level: int = 2):
        """添加指南章节"""
        self.sections.append({
            "title": title,
            "content": content,
            "level": level,
        })

    def generate_markdown(self) -> str:
        """生成Markdown格式使用指南"""
        lines = ["# 使用指南\n"]
        for section in self.sections:
            prefix = "#" * section["level"]
            lines.append(f"{prefix} {section['title']}\n")
            lines.append(f"{section['content']}\n")
        return "\n".join(lines)

    def generate_quickstart(self, module_name: str, examples: List[str]) -> str:
        """生成快速入门指南"""
        lines = [
            f"# {module_name} 快速入门\n",
            "## 安装\n",
            f"```bash\npip install {module_name}\n```\n",
            "## 基本用法\n",
        ]
        for i, example in enumerate(examples, 1):
            lines.append(f"### 示例 {i}\n")
            lines.append(f"```python\n{example}\n```\n")
        return "\n".join(lines)


class DocEngine:
    """文档引擎 - 主类"""

    def __init__(self, output_dir: Union[str, Path] = "."):
        self.output_dir = Path(output_dir)
        self.api_generator = APIDocGenerator()
        self.module_generator = ModuleDocGenerator()
        self.changelog_generator = ChangelogGenerator()
        self.guide_generator = GuideGenerator()
        logger.info("文档引擎初始化完成")

    def generate_all(self, source_dir: Union[str, Path]) -> Dict[str, Path]:
        """生成所有文档"""
        source_dir = Path(source_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        results = {}

        # API文档
        for py_file in source_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                self.api_generator.generate_from_file(py_file)
            except Exception as e:
                logger.warning(f"API文档生成失败 {py_file}: {e}")

        api_md = self.output_dir / "api_documentation.md"
        api_md.write_text(self.api_generator.generate_markdown(), encoding="utf-8")
        results["api"] = api_md

        # 模块文档
        self.module_generator.generate_from_directory(source_dir)
        module_md = self.output_dir / "module_documentation.md"
        module_md.write_text(self.module_generator.generate_markdown(), encoding="utf-8")
        results["module"] = module_md

        # 变更日志（示例）
        self.changelog_generator.add_entry("1.0.0", [
            {"type": "added", "description": "初始版本发布"},
        ])
        changelog_md = self.output_dir / "changelog.md"
        changelog_md.write_text(self.changelog_generator.generate_markdown(), encoding="utf-8")
        results["changelog"] = changelog_md

        logger.info(f"全部文档生成完成: {self.output_dir}")
        return results

    def get_status(self) -> Dict[str, Any]:
        """获取文档生成状态"""
        return {
            "api_entries": len(self.api_generator.entries),
            "modules": len(self.module_generator.modules),
            "changelog_entries": len(self.changelog_generator.entries),
            "guide_sections": len(self.guide_generator.sections),
            "output_dir": str(self.output_dir),
        }
