"""
开发Agent测试
遵循项目规范：四类测试用例
"""

import unittest
from src.core.development_agent import DevelopmentAgent


class TestDevelopmentAgent(unittest.TestCase):
    """开发Agent测试类"""

    def setUp(self) -> None:
        """测试前置"""
        self.agent = DevelopmentAgent("dev")

    def tearDown(self) -> None:
        """测试后置"""
        self.agent.shutdown()

    def test_init_normal(self) -> None:
        """正常初始化测试"""
        self.assertEqual(self.agent.name, "dev")

    def test_execute_generate_function(self) -> None:
        """生成函数测试"""
        result = self.agent.execute({
            "action": "generate",
            "type": "function",
            "name": "add",
            "params": ["a", "b"],
            "description": "加法函数",
            "body": ["return a + b"]
        })
        self.assertIn("code", result)
        self.assertIn("def add", result["code"])

    def test_execute_generate_class(self) -> None:
        """生成类测试"""
        result = self.agent.execute({
            "action": "generate",
            "type": "class",
            "name": "Calculator",
            "description": "计算器类"
        })
        self.assertIn("code", result)
        self.assertIn("class Calculator", result["code"])

    def test_execute_empty_action(self) -> None:
        """空操作测试"""
        result = self.agent.execute({})
        self.assertIn("error", result)

    def test_execute_modify(self) -> None:
        """修改操作测试"""
        result = self.agent.execute({
            "action": "modify"
        })
        self.assertEqual(result["status"], "modified")

    def test_generate_function_params(self) -> None:
        """函数参数测试"""
        result = self.agent.execute({
            "action": "generate",
            "type": "function",
            "name": "greet",
            "params": ["name"],
            "body": ["return f'Hello {name}'"]
        })
        code = result["code"]
        self.assertIn("def greet(name):", code)

    def test_generate_function_empty_params(self) -> None:
        """空参数函数测试"""
        result = self.agent.execute({
            "action": "generate",
            "type": "function",
            "name": "hello",
            "params": [],
            "body": ["return 'hello'"]
        })
        code = result["code"]
        self.assertIn("def hello():", code)

    def test_generate_class_empty(self) -> None:
        """空类生成测试"""
        result = self.agent.execute({
            "action": "generate",
            "type": "class",
            "name": "Empty"
        })
        code = result["code"]
        self.assertIn("class Empty:", code)
        self.assertIn("def __init__(self):", code)


if __name__ == "__main__":
    unittest.main()
