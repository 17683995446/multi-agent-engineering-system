"""
模板引擎模块
遵循第一性原理：声明式渲染公理

核心功能：
1. 变量替换 - {{ variable }} 语法
2. 条件渲染 - {% if %} {% else %} {% endif %}
3. 循环渲染 - {% for %} {% endfor %}
4. 模板继承 - {% extends %} {% block %}
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.utils import setup_logger

logger = setup_logger(__name__)


class TemplateSyntaxError(Exception):
    """模板语法错误"""
    pass


class TemplateContext:
    """模板渲染上下文"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = data or {}
        self._blocks: Dict[str, str] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值，支持点号访问（如 user.name）"""
        keys = key.split(".")
        value = self._data.get(keys[0], default)
        for k in keys[1:]:
            if value is None:
                return default
            if isinstance(value, dict):
                value = value.get(k, default)
            elif hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置变量"""
        self._data[key] = value

    def update(self, data: Dict[str, Any]) -> None:
        """批量更新变量"""
        self._data.update(data)

    def set_block(self, name: str, content: str) -> None:
        """设置块内容"""
        self._blocks[name] = content

    def get_block(self, name: str) -> Optional[str]:
        """获取块内容"""
        return self._blocks.get(name)

    def copy(self) -> TemplateContext:
        """复制上下文"""
        new_ctx = TemplateContext(self._data.copy())
        new_ctx._blocks = self._blocks.copy()
        return new_ctx


class TemplateNode(ABC):
    """模板节点抽象基类"""

    @abstractmethod
    def render(self, context: TemplateContext) -> str:
        pass


class TextNode(TemplateNode):
    """文本节点"""

    def __init__(self, text: str):
        self.text = text

    def render(self, context: TemplateContext) -> str:
        return self.text


class VariableNode(TemplateNode):
    """变量节点"""

    def __init__(self, name: str):
        self.name = name.strip()

    def render(self, context: TemplateContext) -> str:
        value = context.get(self.name)
        if value is None:
            return ""
        return str(value)


class IfNode(TemplateNode):
    """条件节点"""

    def __init__(self, condition: str, true_nodes: List[TemplateNode], false_nodes: List[TemplateNode]):
        self.condition = condition.strip()
        self.true_nodes = true_nodes
        self.false_nodes = false_nodes

    def _eval_condition(self, context: TemplateContext) -> bool:
        """评估条件表达式"""
        cond = self.condition

        # 处理 not
        negate = False
        if cond.startswith("not "):
            negate = True
            cond = cond[4:].strip()

        # 处理 > 和 <
        if ">" in cond and "==" not in cond and "!=" not in cond:
            left, right = cond.split(">", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            result = left_val > right_val
        elif "<" in cond and "==" not in cond and "!=" not in cond:
            left, right = cond.split("<", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            result = left_val < right_val
        elif "==" in cond:
            left, right = cond.split("==", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            result = left_val == right_val
        elif "!=" in cond:
            left, right = cond.split("!=", 1)
            left_val = self._resolve_value(left.strip(), context)
            right_val = self._resolve_value(right.strip(), context)
            result = left_val != right_val
        else:
            value = self._resolve_value(cond, context)
            result = bool(value)

        return not result if negate else result

    def _resolve_value(self, expr: str, context: TemplateContext) -> Any:
        """解析表达式值"""
        expr = expr.strip()

        # 字符串字面量
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # 数字字面量
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # 布尔值
        if expr == "True":
            return True
        if expr == "False":
            return False

        # 变量
        return context.get(expr)

    def render(self, context: TemplateContext) -> str:
        nodes = self.true_nodes if self._eval_condition(context) else self.false_nodes
        return "".join(node.render(context) for node in nodes)


class ForNode(TemplateNode):
    """循环节点"""

    def __init__(self, var_name: str, iterable_name: str, nodes: List[TemplateNode]):
        self.var_name = var_name.strip()
        self.iterable_name = iterable_name.strip()
        self.nodes = nodes

    def render(self, context: TemplateContext) -> str:
        iterable = context.get(self.iterable_name)
        if iterable is None:
            return ""

        result = []
        for item in iterable:
            loop_context = context.copy()
            loop_context.set(self.var_name, item)
            result.append("".join(node.render(loop_context) for node in self.nodes))
        return "".join(result)


class BlockNode(TemplateNode):
    """块节点"""

    def __init__(self, name: str, nodes: List[TemplateNode]):
        self.name = name.strip()
        self.nodes = nodes

    def render(self, context: TemplateContext) -> str:
        # 如果上下文中有覆盖的块内容，使用覆盖内容
        block_content = context.get_block(self.name)
        if block_content is not None:
            return block_content
        return "".join(node.render(context) for node in self.nodes)


class Template:
    """模板"""

    def __init__(self, source: str, name: str = ""):
        self.source = source
        self.name = name
        self._nodes: List[TemplateNode] = []
        self._extends: Optional[str] = None
        self._blocks: Dict[str, List[TemplateNode]] = {}
        self._parse()

    def _parse(self) -> None:
        """解析模板源"""
        tokens = self._tokenize(self.source)
        self._nodes = self._build_ast(tokens)

    def _tokenize(self, source: str) -> List[tuple]:
        """词法分析"""
        tokens = []
        pos = 0

        patterns = [
            ("comment", r"\{#.*?#\}"),
            ("tag", r"\{%\s*(.*?)\s*%\}"),
            ("variable", r"\{\{\s*(.*?)\s*\}\}"),
        ]

        while pos < len(source):
            matched = False
            for token_type, pattern in patterns:
                regex = re.compile(pattern, re.DOTALL)
                m = regex.match(source, pos)
                if m:
                    if pos > m.start():
                        text = source[pos:m.start()]
                        if text:
                            tokens.append(("text", text))
                    if token_type == "tag":
                        tokens.append(("tag", m.group(1).strip()))
                    elif token_type == "variable":
                        tokens.append(("variable", m.group(1).strip()))
                    pos = m.end()
                    matched = True
                    break

            if not matched:
                # 找到下一个token的开始位置
                next_pos = len(source)
                for _, pattern in patterns:
                    m = re.search(pattern, source[pos:])
                    if m:
                        next_pos = min(next_pos, pos + m.start())
                tokens.append(("text", source[pos:next_pos]))
                pos = next_pos

        return tokens

    def _build_ast(self, tokens: List[tuple]) -> List[TemplateNode]:
        """构建抽象语法树"""
        nodes, _ = self._parse_nodes(tokens, 0)
        return nodes

    def _parse_nodes(self, tokens: List[tuple], start: int) -> tuple:
        """递归解析节点"""
        nodes = []
        i = start

        while i < len(tokens):
            token_type, value = tokens[i]

            if token_type == "text":
                nodes.append(TextNode(value))
                i += 1

            elif token_type == "variable":
                nodes.append(VariableNode(value))
                i += 1

            elif token_type == "tag":
                if value.startswith("if "):
                    condition = value[3:].strip()
                    true_nodes, i = self._parse_nodes(tokens, i + 1)
                    false_nodes = []

                    # 检查是否有else
                    if i < len(tokens) and tokens[i][0] == "tag" and tokens[i][1] == "else":
                        false_nodes, i = self._parse_nodes(tokens, i + 1)

                    if i >= len(tokens) or tokens[i][0] != "tag" or tokens[i][1] != "endif":
                        raise TemplateSyntaxError("Missing endif")
                    i += 1
                    nodes.append(IfNode(condition, true_nodes, false_nodes))

                elif value == "else" or value == "endif" or value == "endfor" or value.startswith("endblock"):
                    # 结束当前块
                    return nodes, i

                elif value.startswith("for "):
                    # 解析 for item in iterable
                    match = re.match(r"(\w+)\s+in\s+(.+)", value[4:].strip())
                    if not match:
                        raise TemplateSyntaxError(f"Invalid for syntax: {value}")
                    var_name = match.group(1)
                    iterable_name = match.group(2).strip()
                    loop_nodes, i = self._parse_nodes(tokens, i + 1)

                    if i >= len(tokens) or tokens[i][0] != "tag" or tokens[i][1] != "endfor":
                        raise TemplateSyntaxError("Missing endfor")
                    i += 1
                    nodes.append(ForNode(var_name, iterable_name, loop_nodes))

                elif value.startswith("extends "):
                    self._extends = value[8:].strip().strip('"').strip("'")
                    i += 1

                elif value.startswith("block "):
                    block_name = value[6:].strip()
                    block_nodes, i = self._parse_nodes(tokens, i + 1)

                    if i >= len(tokens) or tokens[i][0] != "tag" or not tokens[i][1].startswith("endblock"):
                        raise TemplateSyntaxError(f"Missing endblock for {block_name}")
                    i += 1

                    self._blocks[block_name] = block_nodes
                    nodes.append(BlockNode(block_name, block_nodes))

                else:
                    i += 1
            else:
                i += 1

        return nodes, i

    def render(self, context: Optional[TemplateContext] = None, **kwargs: Any) -> str:
        """渲染模板"""
        if context is None:
            context = TemplateContext(kwargs)
        elif kwargs:
            context.update(kwargs)

        return "".join(node.render(context) for node in self._nodes)

    @property
    def extends(self) -> Optional[str]:
        return self._extends

    @property
    def blocks(self) -> Dict[str, List[TemplateNode]]:
        return self._blocks.copy()


class TemplateEngine:
    """
    模板引擎

    管理模板加载、继承和渲染
    """

    def __init__(self):
        self._templates: Dict[str, Template] = {}

    def register(self, name: str, source: str) -> Template:
        """注册模板"""
        template = Template(source, name)
        self._templates[name] = template
        logger.info(f"注册模板: {name}")
        return template

    def get(self, name: str) -> Optional[Template]:
        """获取模板"""
        return self._templates.get(name)

    def render(self, template_name: str, context: Optional[TemplateContext] = None, **kwargs: Any) -> str:
        """渲染指定模板"""
        template = self._templates.get(template_name)
        if template is None:
            raise TemplateSyntaxError(f"Template not found: {template_name}")

        ctx = context or TemplateContext()
        if kwargs:
            ctx.update(kwargs)

        # 处理模板继承
        if template.extends:
            parent = self._templates.get(template.extends)
            if parent is None:
                raise TemplateSyntaxError(f"Parent template not found: {template.extends}")

            # 收集子模板块内容
            for block_name, block_nodes in template.blocks.items():
                block_content = "".join(node.render(ctx) for node in block_nodes)
                ctx.set_block(block_name, block_content)

            # 渲染父模板
            return parent.render(ctx)

        return template.render(ctx)


def demo_template_engine():
    """演示模板引擎"""
    print("=" * 60)
    print("模板引擎演示")
    print("=" * 60)
    print()

    engine = TemplateEngine()

    # 1. 变量替换
    print("1. 变量替换:")
    engine.register("vars", "Hello, {{ name }}! You are {{ age }} years old.")
    result = engine.render("vars", name="Alice", age=25)
    print(f"   {result}")
    print()

    # 2. 嵌套变量
    print("2. 嵌套变量:")
    engine.register("nested", "User: {{ user.name }}, City: {{ user.address.city }}")
    result = engine.render("nested", user={"name": "Bob", "address": {"city": "Beijing"}})
    print(f"   {result}")
    print()

    # 3. 条件渲染
    print("3. 条件渲染:")
    engine.register("if", "{% if is_vip %}Welcome, VIP!{% else %}Welcome, regular user.{% endif %}")
    result = engine.render("if", is_vip=True)
    print(f"   VIP: {result}")
    result = engine.render("if", is_vip=False)
    print(f"   Regular: {result}")
    print()

    # 4. 循环渲染
    print("4. 循环渲染:")
    engine.register("for", "Items: {% for item in items %}[{{ item }}]{% endfor %}")
    result = engine.render("for", items=["apple", "banana", "cherry"])
    print(f"   {result}")
    print()

    # 5. 循环+条件
    print("5. 循环+条件:")
    engine.register("for_if", "{% for num in numbers %}{% if num > 3 %}{{ num }} {% endif %}{% endfor %}")
    result = engine.render("for_if", numbers=[1, 2, 3, 4, 5])
    print(f"   >3: {result}")
    print()

    # 6. 模板继承
    print("6. 模板继承:")
    engine.register("base", "<html><head><title>{% block title %}Default Title{% endblock %}</title></head><body>{% block content %}{% endblock %}</body></html>")
    engine.register("child", '{% extends "base" %}{% block title %}My Page{% endblock %}{% block content %}<h1>Hello World</h1>{% endblock %}')
    result = engine.render("child")
    print(f"   {result}")
    print()

    print("=" * 60)
    print("模板引擎演示完成")
    print("=" * 60)
    print()
    print("✓ 变量替换")
    print("✓ 条件渲染")
    print("✓ 循环渲染")
    print("✓ 模板继承")
    print()


if __name__ == "__main__":
    demo_template_engine()
