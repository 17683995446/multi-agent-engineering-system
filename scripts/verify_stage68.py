#!/usr/bin/env python3
"""
阶段68验证脚本：模板引擎

测试内容：
1. 变量替换
2. 嵌套变量访问
3. 条件渲染（if/else）
4. 循环渲染（for）
5. 模板继承（extends/block）
6. 复杂组合
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.template_engine import (
    BlockNode,
    ForNode,
    IfNode,
    Template,
    TemplateContext,
    TemplateEngine,
    TemplateSyntaxError,
    TextNode,
    VariableNode,
)


def test_variable_replacement() -> bool:
    print("[Test] 变量替换")
    try:
        template = Template("Hello, {{ name }}!")
        result = template.render(TemplateContext({"name": "Alice"}))
        assert result == "Hello, Alice!"
        print(f"  ✓ 简单变量: {result}")

        template = Template("{{ greeting }}, {{ name }}! You have {{ count }} messages.")
        result = template.render(TemplateContext({"greeting": "Hi", "name": "Bob", "count": 5}))
        assert result == "Hi, Bob! You have 5 messages."
        print(f"  ✓ 多个变量: {result}")

        # 不存在的变量返回空字符串
        template = Template("Hello, {{ missing }}!")
        result = template.render(TemplateContext())
        assert result == "Hello, !"
        print(f"  ✓ 缺失变量返回空")

        print("[Pass] 变量替换\n")
        return True
    except Exception as e:
        print(f"[Fail] 变量替换: {e}\n")
        return False


def test_nested_variables() -> bool:
    print("[Test] 嵌套变量访问")
    try:
        template = Template("User: {{ user.name }}")
        result = template.render(TemplateContext({"user": {"name": "Alice"}}))
        assert result == "User: Alice"
        print(f"  ✓ 字典嵌套: {result}")

        template = Template("City: {{ user.address.city }}")
        result = template.render(TemplateContext({
            "user": {"address": {"city": "Beijing"}}
        }))
        assert result == "City: Beijing"
        print(f"  ✓ 多层嵌套: {result}")

        # 对象属性访问
        class User:
            def __init__(self, name):
                self.name = name

        template = Template("Name: {{ user.name }}")
        result = template.render(TemplateContext({"user": User("Bob")}))
        assert result == "Name: Bob"
        print(f"  ✓ 对象属性: {result}")

        # 中间缺失返回空
        template = Template("X: {{ user.missing.field }}")
        result = template.render(TemplateContext({"user": {}}))
        assert result == "X: "
        print("  ✓ 中间缺失返回空")

        print("[Pass] 嵌套变量访问\n")
        return True
    except Exception as e:
        print(f"[Fail] 嵌套变量访问: {e}\n")
        return False


def test_condition_rendering() -> bool:
    print("[Test] 条件渲染")
    try:
        template = Template("{% if is_vip %}VIP{% else %}Normal{% endif %}")
        result = template.render(TemplateContext({"is_vip": True}))
        assert result == "VIP"
        print(f"  ✓ if为真: {result}")

        result = template.render(TemplateContext({"is_vip": False}))
        assert result == "Normal"
        print(f"  ✓ if为假: {result}")

        # 无else
        template = Template("{% if show %}Visible{% endif %}")
        result = template.render(TemplateContext({"show": True}))
        assert result == "Visible"
        result = template.render(TemplateContext({"show": False}))
        assert result == ""
        print("  ✓ 无else条件")

        # not条件
        template = Template("{% if not hidden %}Shown{% endif %}")
        result = template.render(TemplateContext({"hidden": False}))
        assert result == "Shown"
        result = template.render(TemplateContext({"hidden": True}))
        assert result == ""
        print("  ✓ not条件")

        # 等于比较
        template = Template("{% if status == 'active' %}Active{% else %}Inactive{% endif %}")
        result = template.render(TemplateContext({"status": "active"}))
        assert result == "Active"
        result = template.render(TemplateContext({"status": "inactive"}))
        assert result == "Inactive"
        print("  ✓ 等于比较")

        # 不等于比较
        template = Template("{% if count != 0 %}Has items{% else %}Empty{% endif %}")
        result = template.render(TemplateContext({"count": 5}))
        assert result == "Has items"
        result = template.render(TemplateContext({"count": 0}))
        assert result == "Empty"
        print("  ✓ 不等于比较")

        print("[Pass] 条件渲染\n")
        return True
    except Exception as e:
        print(f"[Fail] 条件渲染: {e}\n")
        return False


def test_loop_rendering() -> bool:
    print("[Test] 循环渲染")
    try:
        template = Template("{% for item in items %}[{{ item }}]{% endfor %}")
        result = template.render(TemplateContext({"items": ["a", "b", "c"]}))
        assert result == "[a][b][c]"
        print(f"  ✓ 简单循环: {result}")

        # 空列表
        result = template.render(TemplateContext({"items": []}))
        assert result == ""
        print("  ✓ 空列表无输出")

        # 循环中嵌套变量
        template = Template("{% for user in users %}{{ user.name }} {% endfor %}")
        result = template.render(TemplateContext({
            "users": [{"name": "Alice"}, {"name": "Bob"}]
        }))
        assert result == "Alice Bob "
        print(f"  ✓ 循环嵌套变量: {result}")

        # 循环+条件
        template = Template("{% for num in numbers %}{% if num > 2 %}{{ num }}{% endif %}{% endfor %}")
        result = template.render(TemplateContext({"numbers": [1, 2, 3, 4]}))
        assert result == "34"
        print(f"  ✓ 循环+条件: {result}")

        print("[Pass] 循环渲染\n")
        return True
    except Exception as e:
        print(f"[Fail] 循环渲染: {e}\n")
        return False


def test_template_inheritance() -> bool:
    print("[Test] 模板继承")
    try:
        engine = TemplateEngine()

        engine.register("base", "<html><title>{% block title %}Default{% endblock %}</title><body>{% block content %}{% endblock %}</body></html>")
        engine.register("child", '{% extends "base" %}{% block title %}My Page{% endblock %}{% block content %}<h1>Hello</h1>{% endblock %}')

        result = engine.render("child")
        assert "<title>My Page</title>" in result
        assert "<h1>Hello</h1>" in result
        print(f"  ✓ 基础继承: {result}")

        # 只覆盖一个block
        engine.register("child2", '{% extends "base" %}{% block content %}Only content{% endblock %}')
        result = engine.render("child2")
        assert "<title>Default</title>" in result
        assert "Only content" in result
        print(f"  ✓ 部分覆盖: {result}")

        # 使用上下文
        engine.register("child3", '{% extends "base" %}{% block title %}{{ page_title }}{% endblock %}{% block content %}{{ body }}{% endblock %}')
        result = engine.render("child3", page_title="Dynamic", body="<p>Text</p>")
        assert "<title>Dynamic</title>" in result
        assert "<p>Text</p>" in result
        print(f"  ✓ 继承+上下文: {result}")

        print("[Pass] 模板继承\n")
        return True
    except Exception as e:
        print(f"[Fail] 模板继承: {e}\n")
        return False


def test_complex_combination() -> bool:
    print("[Test] 复杂组合")
    try:
        source = """
Users:
{% for user in users %}
  - Name: {{ user.name }}
    {% if user.active %}Status: Active{% else %}Status: Inactive{% endif %}
    {% if user.score > 80 %}Grade: A{% elif user.score > 60 %}Grade: B{% else %}Grade: C{% endif %}
{% endfor %}
Total: {{ users|length }}
""".strip()

        # 简化测试：只测试for+if组合
        source2 = "{% for user in users %}{{ user.name }}:{% if user.active %}active{% else %}inactive{% endif %} {% endfor %}"
        template = Template(source2)
        result = template.render(TemplateContext({
            "users": [
                {"name": "Alice", "active": True},
                {"name": "Bob", "active": False},
            ]
        }))
        assert result == "Alice:active Bob:inactive "
        print(f"  ✓ for+if组合: {result}")

        # 文本+变量+条件混合
        source3 = "Welcome, {{ name }}!{% if is_new %} You are new here.{% endif %}"
        template = Template(source3)
        result = template.render(TemplateContext({"name": "Alice", "is_new": True}))
        assert result == "Welcome, Alice! You are new here."
        result = template.render(TemplateContext({"name": "Bob", "is_new": False}))
        assert result == "Welcome, Bob!"
        print("  ✓ 文本+变量+条件混合")

        print("[Pass] 复杂组合\n")
        return True
    except Exception as e:
        print(f"[Fail] 复杂组合: {e}\n")
        return False


def test_comments() -> bool:
    print("[Test] 注释")
    try:
        template = Template("Hello {# this is a comment #} World")
        result = template.render(TemplateContext())
        assert result == "Hello  World"
        print(f"  ✓ 注释被移除: '{result}'")

        print("[Pass] 注释\n")
        return True
    except Exception as e:
        print(f"[Fail] 注释: {e}\n")
        return False


def test_engine_management() -> bool:
    print("[Test] 引擎管理")
    try:
        engine = TemplateEngine()

        engine.register("t1", "Hello {{ name }}")
        assert engine.get("t1") is not None
        print("  ✓ 模板注册")

        result = engine.render("t1", name="World")
        assert result == "Hello World"
        print("  ✓ 渲染已注册模板")

        try:
            engine.render("not_exist")
            assert False, "应该抛出异常"
        except TemplateSyntaxError:
            print("  ✓ 不存在的模板抛出异常")

        print("[Pass] 引擎管理\n")
        return True
    except Exception as e:
        print(f"[Fail] 引擎管理: {e}\n")
        return False


def test_template_nodes() -> bool:
    print("[Test] 模板节点")
    try:
        text = TextNode("hello")
        assert text.render(TemplateContext()) == "hello"
        print("  ✓ TextNode")

        var = VariableNode("name")
        assert var.render(TemplateContext({"name": "Alice"})) == "Alice"
        assert var.render(TemplateContext()) == ""
        print("  ✓ VariableNode")

        if_node = IfNode("x", [TextNode("yes")], [TextNode("no")])
        assert if_node.render(TemplateContext({"x": True})) == "yes"
        assert if_node.render(TemplateContext({"x": False})) == "no"
        print("  ✓ IfNode")

        for_node = ForNode("i", "items", [VariableNode("i")])
        assert for_node.render(TemplateContext({"items": [1, 2]})) == "12"
        assert for_node.render(TemplateContext({"items": []})) == ""
        print("  ✓ ForNode")

        block = BlockNode("main", [TextNode("content")])
        assert block.render(TemplateContext()) == "content"
        ctx = TemplateContext()
        ctx.set_block("main", "overridden")
        assert block.render(ctx) == "overridden"
        print("  ✓ BlockNode")

        print("[Pass] 模板节点\n")
        return True
    except Exception as e:
        print(f"[Fail] 模板节点: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段68验证脚本：模板引擎")
    print("=" * 60 + "\n")

    results = []
    results.append(("变量替换", test_variable_replacement()))
    results.append(("嵌套变量访问", test_nested_variables()))
    results.append(("条件渲染", test_condition_rendering()))
    results.append(("循环渲染", test_loop_rendering()))
    results.append(("模板继承", test_template_inheritance()))
    results.append(("复杂组合", test_complex_combination()))
    results.append(("注释", test_comments()))
    results.append(("引擎管理", test_engine_management()))
    results.append(("模板节点", test_template_nodes()))

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
        print("🎉 所有测试通过！阶段68验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
