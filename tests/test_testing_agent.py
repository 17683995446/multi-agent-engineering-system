"""
测试Agent测试
遵循项目规范：四类测试用例
"""

import unittest
from src.core.testing_agent import TestingAgent


class TestTestingAgent(unittest.TestCase):
    """测试Agent测试类"""

    def setUp(self) -> None:
        """测试前置"""
        self.agent = TestingAgent("tester")

    def tearDown(self) -> None:
        """测试后置"""
        self.agent.shutdown()

    def test_init_normal(self) -> None:
        """正常初始化测试"""
        self.assertEqual(self.agent.name, "tester")

    def test_generate_tests_normal(self) -> None:
        """正常生成测试"""
        result = self.agent.execute({
            "action": "generate",
            "source": "def add(a, b): return a + b",
            "function_name": "add"
        })
        self.assertIn("test_cases", result)
        self.assertEqual(result["count"], 4)

    def test_generate_tests_empty(self) -> None:
        """空源码生成测试"""
        result = self.agent.execute({
            "action": "generate",
            "source": "",
            "function_name": ""
        })
        self.assertEqual(result["count"], 4)

    def test_generate_tests_invalid(self) -> None:
        """非法操作测试"""
        result = self.agent.execute({})
        self.assertIn("error", result)

    def test_test_case_types(self) -> None:
        """测试用例类型覆盖"""
        result = self.agent.execute({
            "action": "generate",
            "source": "def test(): pass",
            "function_name": "test"
        })
        cases = result["test_cases"]
        types = [c["type"] for c in cases]
        self.assertIn("normal", types)
        self.assertIn("empty", types)
        self.assertIn("boundary", types)
        self.assertIn("invalid", types)

    def test_normal_case_values(self) -> None:
        """正常值用例内容测试"""
        result = self.agent.execute({
            "action": "generate",
            "source": "def add(a, b): return a + b",
            "function_name": "add"
        })
        normal = [c for c in result["test_cases"] if c["type"] == "normal"][0]
        self.assertEqual(normal["input"]["a"], 1)
        self.assertEqual(normal["expected"], 3)

    def test_boundary_case_values(self) -> None:
        """边界值用例内容测试"""
        result = self.agent.execute({
            "action": "generate",
            "source": "def add(a, b): return a + b",
            "function_name": "add"
        })
        boundary = [c for c in result["test_cases"] if c["type"] == "boundary"][0]
        self.assertEqual(boundary["input"]["a"], 0)
        self.assertEqual(boundary["expected"], 0)

    def test_invalid_case_values(self) -> None:
        """非法值用例内容测试"""
        result = self.agent.execute({
            "action": "generate",
            "source": "def add(a, b): return a + b",
            "function_name": "add"
        })
        invalid = [c for c in result["test_cases"] if c["type"] == "invalid"][0]
        self.assertEqual(invalid["input"]["a"], "x")


if __name__ == "__main__":
    unittest.main()
