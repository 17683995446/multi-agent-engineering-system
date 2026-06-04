"""
中央控制Agent测试
遵循项目规范：四类测试用例
"""

import unittest
from src.core.central_control import CentralControlAgent
from src.core.development_agent import DevelopmentAgent


class TestCentralControlAgent(unittest.TestCase):
    """中央控制Agent测试类"""

    def setUp(self) -> None:
        """测试前置"""
        self.agent = CentralControlAgent("central")

    def tearDown(self) -> None:
        """测试后置"""
        self.agent.shutdown()

    def test_init_normal(self) -> None:
        """正常初始化测试"""
        self.assertEqual(self.agent.name, "central")

    def test_register_agent(self) -> None:
        """注册Agent测试"""
        dev = DevelopmentAgent("dev")
        result = self.agent.register_agent(dev)
        self.assertTrue(result)
        dev.shutdown()

    def test_register_duplicate(self) -> None:
        """重复注册测试"""
        dev1 = DevelopmentAgent("dev")
        dev2 = DevelopmentAgent("dev")
        self.agent.register_agent(dev1)
        result = self.agent.register_agent(dev2)
        self.assertFalse(result)
        dev1.shutdown()
        dev2.shutdown()

    def test_process_requirement_normal(self) -> None:
        """正常处理需求测试"""
        result = self.agent.execute({
            "action": "process_requirement",
            "requirement": "实现登录功能"
        })
        self.assertEqual(result["status"], "decomposed")
        self.assertEqual(result["task_count"], 5)

    def test_process_requirement_empty(self) -> None:
        """空需求处理测试"""
        result = self.agent.execute({
            "action": "process_requirement",
            "requirement": ""
        })
        self.assertEqual(result["status"], "decomposed")

    def test_process_requirement_long(self) -> None:
        """长需求处理测试"""
        result = self.agent.execute({
            "action": "process_requirement",
            "requirement": "A" * 500
        })
        self.assertEqual(result["status"], "decomposed")

    def test_execute_invalid_action(self) -> None:
        """非法操作测试"""
        result = self.agent.execute({})
        self.assertIn("error", result)

    def test_task_structure(self) -> None:
        """任务结构验证"""
        result = self.agent.execute({
            "action": "process_requirement",
            "requirement": "测试"
        })
        tasks = result["tasks"]
        names = [t["name"] for t in tasks]
        self.assertIn("需求分析", names)
        self.assertIn("编码实现", names)
        self.assertIn("单元测试", names)


if __name__ == "__main__":
    unittest.main()
