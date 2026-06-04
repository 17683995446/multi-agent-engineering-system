"""
MVP阶段8: 文档Agent
遵循第一性原理：责任正交性、状态分离
"""

import ast
import os
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.mvp_core.agent_base import AgentBase, AgentStatus, MessageBus
from src.common.utils import setup_logger, AgentException, PathManager

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class APIDocEntry:
    """API文档条目"""
    name: str
    doc_type: str  # function, class, module
    signature: Optional[str] = None
    docstring: Optional[str] = None
    args: List[Dict[str, Any]] = field(default_factory=list)
    returns: Optional[str] = None
    source_file: Optional[str] = None
    lineno: int = 0


@dataclass
class ChangelogEntry:
    """变更日志条目"""
    version: str
    date: str
    changes: List[str] = field(default_factory=list)
    category: str = ""


# ---------------------------------------------------------------------------
# APIDocGenerator - API文档生成器
# ---------------------------------------------------------------------------

class APIDocGenerator:
    """
    API文档生成器 - 从Python源码提取docstring并生成Markdown

    核心方法：
    - extract_from_file: 从文件提取API文档
    - extract_from_source: 从源码字符串提取
    - generate_markdown: 生成Markdown格式文档
    """

    def extract_from_file(self, file_path: str) -> List[APIDocEntry]:
        """从Python文件提取API文档条目"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        source = path.read_text(encoding="utf-8")
        return self.extract_from_source(source, file_path=file_path)

    def extract_from_source(self, source: str, file_path: Optional[str] = None) -> List[APIDocEntry]:
        """从源码字符串提取API文档条目"""
        entries: List[APIDocEntry] = []
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.error(f"解析源码失败: {e}")
            return entries

        module_doc = ast.get_docstring(tree)
        if module_doc:
            entries.append(APIDocEntry(
                name=Path(file_path).stem if file_path else "module",
                doc_type="module",
                docstring=module_doc,
                source_file=file_path,
            ))

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                entries.append(self._parse_class(node, file_path))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entries.append(self._parse_function(node, file_path))

        return entries

    def _parse_class(self, node: ast.ClassDef, file_path: Optional[str]) -> APIDocEntry:
        """解析类定义"""
        docstring = ast.get_docstring(node)
        bases = [ast.unparse(b) for b in node.bases]
        signature = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"

        methods: List[Dict[str, Any]] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append({
                    "name": child.name,
                    "signature": self._build_func_signature(child),
                    "docstring": ast.get_docstring(child),
                })

        return APIDocEntry(
            name=node.name,
            doc_type="class",
            signature=signature,
            docstring=docstring,
            source_file=file_path,
            lineno=node.lineno,
            args=methods,
        )

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: Optional[str]) -> APIDocEntry:
        """解析函数定义"""
        docstring = ast.get_docstring(node)
        signature = self._build_func_signature(node)

        args: List[Dict[str, Any]] = []
        for arg in node.args.args:
            arg_info: Dict[str, Any] = {"name": arg.arg}
            if arg.annotation:
                arg_info["type"] = ast.unparse(arg.annotation)
            args.append(arg_info)

        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        return APIDocEntry(
            name=node.name,
            doc_type="function",
            signature=signature,
            docstring=docstring,
            args=args,
            returns=returns,
            source_file=file_path,
            lineno=node.lineno,
        )

    def _build_func_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """构建函数字符串签名"""
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        args_str = ast.unparse(node.args)
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{prefix} {node.name}({args_str}){ret}"

    def generate_markdown(self, entries: List[APIDocEntry], title: str = "API Documentation") -> str:
        """生成Markdown格式API文档"""
        lines: List[str] = [f"# {title}", ""]

        for entry in entries:
            if entry.doc_type == "module":
                lines.append(f"## 模块: {entry.name}")
            elif entry.doc_type == "class":
                lines.append(f"## 类: `{entry.name}`")
            else:
                lines.append(f"## 函数: `{entry.name}`")

            if entry.signature:
                lines.append(f"```python\n{entry.signature}\n```")

            if entry.docstring:
                lines.append(f"\n{entry.docstring}\n")

            if entry.args and entry.doc_type == "class":
                lines.append("### 方法")
                for method in entry.args:
                    lines.append(f"- **`{method['name']}`**")
                    if method.get("signature"):
                        lines.append(f"  ```python\n  {method['signature']}\n  ```")
                    if method.get("docstring"):
                        lines.append(f"  {method['docstring']}")
                lines.append("")

            if entry.args and entry.doc_type == "function":
                lines.append("**参数:**")
                for arg in entry.args:
                    type_str = f" (*{arg['type']}*)" if arg.get("type") else ""
                    lines.append(f"- `{arg['name']}`{type_str}")
                lines.append("")

            if entry.returns:
                lines.append(f"**返回:** `{entry.returns}`")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# READMEGenerator - README生成器
# ---------------------------------------------------------------------------

class READMEGenerator:
    """
    README生成器 - 自动生成项目README文档

    核心方法：
    - generate: 根据项目信息生成README
    - generate_from_project: 从项目目录自动推断信息
    """

    def generate(
        self,
        project_name: str,
        description: str,
        install_instructions: Optional[List[str]] = None,
        usage_examples: Optional[List[Dict[str, str]]] = None,
        badges: Optional[List[str]] = None,
        toc: bool = True,
    ) -> str:
        """生成README内容"""
        lines: List[str] = []

        # 标题
        lines.append(f"# {project_name}")
        lines.append("")

        # 徽章
        if badges:
            lines.append(" ".join(badges))
            lines.append("")

        # 描述
        lines.append(description)
        lines.append("")

        # 目录
        if toc:
            lines.append("## 目录")
            lines.append("")
            lines.append("- [安装](#安装)")
            lines.append("- [使用](#使用)")
            lines.append("- [贡献](#贡献)")
            lines.append("- [许可证](#许可证)")
            lines.append("")

        # 安装
        lines.append("## 安装")
        lines.append("")
        if install_instructions:
            for instruction in install_instructions:
                lines.append(instruction)
        else:
            lines.append("```bash")
            lines.append("pip install -r requirements.txt")
            lines.append("```")
        lines.append("")

        # 使用
        lines.append("## 使用")
        lines.append("")
        if usage_examples:
            for example in usage_examples:
                title = example.get("title", "示例")
                code = example.get("code", "")
                lines.append(f"### {title}")
                lines.append("")
                lines.append("```python")
                lines.append(code)
                lines.append("```")
                lines.append("")
        else:
            lines.append("```python")
            lines.append("# TODO: 添加使用示例")
            lines.append("```")
            lines.append("")

        # 贡献
        lines.append("## 贡献")
        lines.append("")
        lines.append("欢迎提交Issue和Pull Request。")
        lines.append("")

        # 许可证
        lines.append("## 许可证")
        lines.append("")
        lines.append("[MIT](LICENSE)")
        lines.append("")

        return "\n".join(lines)

    def generate_from_project(self, project_dir: str) -> str:
        """从项目目录自动生成README"""
        path = Path(project_dir)
        project_name = path.name or "Project"

        # 尝试读取现有的setup.py或pyproject.toml获取描述
        description = "项目描述待补充。"
        pyproject = path / "pyproject.toml"
        setup_py = path / "setup.py"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            m = re.search(r'description\s*=\s*"([^"]+)"', content)
            if m:
                description = m.group(1)
        elif setup_py.exists():
            content = setup_py.read_text(encoding="utf-8")
            m = re.search(r'description\s*=\s*"([^"]+)"', content)
            if m:
                description = m.group(1)

        # 检测安装方式
        install_instructions: List[str] = []
        if (path / "requirements.txt").exists():
            install_instructions.append("```bash")
            install_instructions.append("pip install -r requirements.txt")
            install_instructions.append("```")
        if (path / "setup.py").exists() or (path / "pyproject.toml").exists():
            install_instructions.append("```bash")
            install_instructions.append("pip install -e .")
            install_instructions.append("```")

        return self.generate(
            project_name=project_name,
            description=description,
            install_instructions=install_instructions or None,
        )


# ---------------------------------------------------------------------------
# ChangelogGenerator - 变更日志生成器
# ---------------------------------------------------------------------------

class ChangelogGenerator:
    """
    变更日志生成器 - 生成和维护CHANGELOG.md

    核心方法：
    - generate: 根据条目生成变更日志
    - add_entry: 添加新条目
    - parse_existing: 解析已有CHANGELOG
    """

    def generate(self, entries: List[ChangelogEntry], title: str = "Changelog") -> str:
        """生成Markdown格式变更日志"""
        lines: List[str] = [f"# {title}", ""]
        lines.append("所有项目的显著变更都将记录在此文件中。")
        lines.append("")

        for entry in entries:
            lines.append(f"## [{entry.version}] - {entry.date}")
            lines.append("")
            if entry.category:
                lines.append(f"### {entry.category}")
                lines.append("")
            for change in entry.changes:
                lines.append(f"- {change}")
            lines.append("")

        return "\n".join(lines)

    def add_entry(self, existing: str, entry: ChangelogEntry) -> str:
        """向现有变更日志添加新条目"""
        lines = existing.splitlines()
        # 在标题后插入新版本
        insert_idx = 2
        new_lines = [
            f"## [{entry.version}] - {entry.date}",
            "",
        ]
        if entry.category:
            new_lines.append(f"### {entry.category}")
            new_lines.append("")
        for change in entry.changes:
            new_lines.append(f"- {change}")
        new_lines.append("")

        for i, line in enumerate(lines):
            if line.startswith("## ["):
                insert_idx = i
                break

        result = lines[:insert_idx] + new_lines + lines[insert_idx:]
        return "\n".join(result)

    def parse_existing(self, content: str) -> List[ChangelogEntry]:
        """解析已有CHANGELOG内容"""
        entries: List[ChangelogEntry] = []
        current: Optional[ChangelogEntry] = None

        for line in content.splitlines():
            m = re.match(r"## \[(.+?)\] - (\d{4}-\d{2}-\d{2})", line)
            if m:
                if current:
                    entries.append(current)
                current = ChangelogEntry(version=m.group(1), date=m.group(2))
            elif line.startswith("### ") and current:
                current.category = line[4:].strip()
            elif line.startswith("- ") and current:
                current.changes.append(line[2:])

        if current:
            entries.append(current)

        return entries


# ---------------------------------------------------------------------------
# DocFormatter - 文档格式化器
# ---------------------------------------------------------------------------

class DocFormatter:
    """
    文档格式化器 - 统一文档格式

    核心方法：
    - format_markdown: 格式化Markdown文档
    - wrap_code_blocks: 包裹代码块
    - normalize_headers: 规范化标题层级
    """

    def format_markdown(self, content: str) -> str:
        """格式化Markdown内容"""
        lines = content.splitlines()
        result: List[str] = []
        in_code_block = False
        prev_blank = False

        for line in lines:
            stripped = line.strip()

            # 代码块边界
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                result.append(line)
                prev_blank = False
                continue

            if in_code_block:
                result.append(line)
                prev_blank = False
                continue

            # 去除行尾空格
            line = line.rstrip()

            # 合并连续空行
            if not line:
                if not prev_blank:
                    result.append("")
                    prev_blank = True
                continue
            prev_blank = False

            result.append(line)

        # 确保文件末尾有单个换行
        while result and result[-1] == "":
            result.pop()
        result.append("")

        return "\n".join(result)

    def wrap_code_blocks(self, content: str, language: str = "python") -> str:
        """为未包裹的代码片段添加代码块标记"""
        # 简单启发式：检测缩进代码块并转换为fenced code blocks
        lines = content.splitlines()
        result: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("    ") and (not result or not result[-1].startswith("```")):
                # 开始代码块
                result.append(f"```{language}")
                while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                    if lines[i].startswith("    "):
                        result.append(lines[i][4:])
                    else:
                        result.append("")
                    i += 1
                result.append("```")
                continue
            else:
                result.append(line)
                i += 1
        return "\n".join(result)

    def normalize_headers(self, content: str, max_level: int = 3) -> str:
        """规范化标题层级，确保不超过max_level"""
        lines = content.splitlines()
        result: List[str] = []
        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)", line)
            if m:
                level = len(m.group(1))
                if level > max_level:
                    line = f"{'#' * max_level} {m.group(2)}"
            result.append(line)
        return "\n".join(result)


# ---------------------------------------------------------------------------
# DocumentAgent - 文档Agent
# ---------------------------------------------------------------------------

class DocumentAgent(AgentBase):
    """
    文档Agent - 负责API文档生成、README生成、变更日志生成和文档格式化

    核心职责：
    - API文档生成：从代码提取docstring并生成Markdown
    - README生成：自动生成项目README
    - 变更日志生成：生成和维护CHANGELOG
    - 文档格式化：统一文档格式
    """

    def __init__(self, name: str = "document_agent", message_bus: Optional[MessageBus] = None):
        super().__init__(name=name, message_bus=message_bus)
        self.api_generator = APIDocGenerator()
        self.readme_generator = READMEGenerator()
        self.changelog_generator = ChangelogGenerator()
        self.formatter = DocFormatter()
        self._doc_cache: Dict[str, str] = {}
        logger.info(f"DocumentAgent初始化完成: {name}")

    # ------------------------------
    # API文档生成
    # ------------------------------

    def generate_api_docs(self, task: Dict[str, Any]) -> str:
        """
        生成API文档

        task格式：
        {
            "source": str | List[str],  # 源码字符串或文件路径列表
            "output_path": Optional[str],
            "title": str,
        }
        """
        source = task.get("source", [])
        title = task.get("title", "API Documentation")
        output_path = task.get("output_path")

        entries: List[APIDocEntry] = []
        if isinstance(source, str):
            entries.extend(self.api_generator.extract_from_source(source))
        elif isinstance(source, list):
            for path in source:
                if Path(path).exists():
                    entries.extend(self.api_generator.extract_from_file(path))
                else:
                    entries.extend(self.api_generator.extract_from_source(path))

        markdown = self.api_generator.generate_markdown(entries, title=title)
        formatted = self.formatter.format_markdown(markdown)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(formatted, encoding="utf-8")
            logger.info(f"API文档已保存: {output_path}")

        self._doc_cache[f"api_{title}"] = formatted
        return formatted

    # ------------------------------
    # README生成
    # ------------------------------

    def generate_readme(self, task: Dict[str, Any]) -> str:
        """
        生成README文档

        task格式：
        {
            "project_name": str,
            "description": str,
            "install_instructions": Optional[List[str]],
            "usage_examples": Optional[List[Dict[str, str]]],
            "output_path": Optional[str],
            "project_dir": Optional[str],  # 若提供，自动推断信息
        }
        """
        project_dir = task.get("project_dir")
        if project_dir:
            readme = self.readme_generator.generate_from_project(project_dir)
        else:
            readme = self.readme_generator.generate(
                project_name=task.get("project_name", "Project"),
                description=task.get("description", ""),
                install_instructions=task.get("install_instructions"),
                usage_examples=task.get("usage_examples"),
            )

        formatted = self.formatter.format_markdown(readme)
        output_path = task.get("output_path")
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(formatted, encoding="utf-8")
            logger.info(f"README已保存: {output_path}")

        self._doc_cache["readme"] = formatted
        return formatted

    # ------------------------------
    # 变更日志生成
    # ------------------------------

    def generate_changelog(self, task: Dict[str, Any]) -> str:
        """
        生成变更日志

        task格式：
        {
            "entries": List[Dict],  # ChangelogEntry的字典表示
            "output_path": Optional[str],
            "append_to": Optional[str],  # 追加到已有文件路径
            "title": str,
        }
        """
        entries_data = task.get("entries", [])
        title = task.get("title", "Changelog")
        entries = [
            ChangelogEntry(
                version=e.get("version", "0.0.0"),
                date=e.get("date", datetime.now().strftime("%Y-%m-%d")),
                changes=e.get("changes", []),
                category=e.get("category", ""),
            )
            for e in entries_data
        ]

        changelog = self.changelog_generator.generate(entries, title=title)
        formatted = self.formatter.format_markdown(changelog)

        append_to = task.get("append_to")
        if append_to and Path(append_to).exists():
            existing = Path(append_to).read_text(encoding="utf-8")
            for entry in entries:
                formatted = self.changelog_generator.add_entry(existing, entry)
                existing = formatted

        output_path = task.get("output_path")
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(formatted, encoding="utf-8")
            logger.info(f"变更日志已保存: {output_path}")

        self._doc_cache["changelog"] = formatted
        return formatted

    # ------------------------------
    # 文档格式化
    # ------------------------------

    def format_document(self, task: Dict[str, Any]) -> str:
        """
        格式化文档

        task格式：
        {
            "content": str,
            "operations": List[str],  # "markdown", "normalize_headers", "wrap_code"
            "output_path": Optional[str],
        }
        """
        content = task.get("content", "")
        operations = task.get("operations", ["markdown"])

        for op in operations:
            if op == "markdown":
                content = self.formatter.format_markdown(content)
            elif op == "normalize_headers":
                content = self.formatter.normalize_headers(content)
            elif op == "wrap_code":
                content = self.formatter.wrap_code_blocks(content)

        output_path = task.get("output_path")
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")
            logger.info(f"格式化文档已保存: {output_path}")

        return content

    # ------------------------------
    # AgentBase 抽象方法实现
    # ------------------------------

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务 - DocumentAgent核心入口

        task格式：
        {
            "action": "api_docs" | "readme" | "changelog" | "format",
            ... 其他参数
        }
        """
        action = task.get("action")
        self.status = AgentStatus.BUSY

        try:
            if action == "api_docs":
                result = self.generate_api_docs(task)
                return {"success": True, "action": action, "content": result}
            elif action == "readme":
                result = self.generate_readme(task)
                return {"success": True, "action": action, "content": result}
            elif action == "changelog":
                result = self.generate_changelog(task)
                return {"success": True, "action": action, "content": result}
            elif action == "format":
                result = self.format_document(task)
                return {"success": True, "action": action, "content": result}
            else:
                raise AgentException(f"不支持的操作: {action}")
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error(f"任务执行失败: {e}")
            return {"success": False, "action": action, "error": str(e)}
        finally:
            self.status = AgentStatus.IDLE
