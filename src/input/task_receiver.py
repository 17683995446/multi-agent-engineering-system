"""
输入收敛层 - 第1层架构
职责：统一接收任务、类型判定、基础预处理
依赖规则：可引用 common, workflow
"""

from typing import Dict, Any, Optional


class TaskReceiver:
    """任务接收器 - 输入收敛层核心组件"""

    def __init__(self):
        self.task_buffer = []

    def receive(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """接收任务并进行基础预处理"""
        if not task:
            raise ValueError("任务不能为空")

        normalized_task = {
            "id": task.get("id", self._generate_id()),
            "description": task.get("description", ""),
            "type": task.get("type", "unknown"),
            "priority": task.get("priority", 5),
            "metadata": task.get("metadata", {})
        }

        self.task_buffer.append(normalized_task)
        return normalized_task

    def _generate_id(self) -> str:
        """生成唯一任务ID"""
        import uuid
        return f"task-{uuid.uuid4().hex[:8]}"


def create_task_receiver() -> TaskReceiver:
    """工厂方法：创建任务接收器"""
    return TaskReceiver()
