"""
任务分解器测试
遵循项目规范：四类测试用例
"""

import unittest
from src.core.task_decomposer import (
    TaskDecomposer, TaskNode, TaskStatus, TaskPriority
)


class TestTaskDecomposer(unittest.TestCase):
    """任务分解器测试类"""

    def setUp(self) -> None:
        """测试前置"""
        self.decomposer = TaskDecomposer("test")

    def test_decompose_normal(self) -> None:
        """正常分解测试"""
        requirement = "实现用户登录功能"
        root = self.decomposer.decompose(requirement)
        self.assertIsNotNone(root)
        self.assertEqual(len(root.children), 5)

    def test_decompose_empty(self) -> None:
        """空需求分解测试"""
        root = self.decomposer.decompose("")
        self.assertIsNotNone(root)
        self.assertEqual(len(root.children), 5)

    def test_decompose_long(self) -> None:
        """长需求分解测试"""
        requirement = "A" * 1000
        root = self.decomposer.decompose(requirement)
        self.assertIsNotNone(root)

    def test_get_leaf_tasks(self) -> None:
        """叶子任务获取测试"""
        root = self.decomposer.decompose("测试")
        leaves = self.decomposer.get_leaf_tasks(root)
        self.assertEqual(len(leaves), 5)

    def test_get_leaf_tasks_empty(self) -> None:
        """空树叶子获取测试"""
        root = TaskNode(
            task_id="t1",
            name="root",
            description="test"
        )
        leaves = self.decomposer.get_leaf_tasks(root)
        self.assertEqual(len(leaves), 1)

    def test_task_node_is_leaf(self) -> None:
        """叶子判断测试"""
        node = TaskNode(
            task_id="t1",
            name="leaf",
            description="test"
        )
        self.assertTrue(node.is_leaf())

    def test_task_node_not_leaf(self) -> None:
        """非叶子判断测试"""
        parent = TaskNode(
            task_id="t1",
            name="parent",
            description="test"
        )
        child = TaskNode(
            task_id="t2",
            name="child",
            description="test",
            parent="t1"
        )
        parent.children.append(child)
        self.assertFalse(parent.is_leaf())

    def test_task_to_dict(self) -> None:
        """字典转换测试"""
        task = TaskNode(
            task_id="t1",
            name="test",
            description="desc",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.HIGH
        )
        data = task.to_dict()
        self.assertEqual(data["task_id"], "t1")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["priority"], "high")

    def test_task_dependencies(self) -> None:
        """依赖关系测试"""
        root = self.decomposer.decompose("测试")
        coding_task = root.children[2]
        self.assertEqual(coding_task.name, "编码实现")
        self.assertEqual(len(coding_task.dependencies), 1)


if __name__ == "__main__":
    unittest.main()
