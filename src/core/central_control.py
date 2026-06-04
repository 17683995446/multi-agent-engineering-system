"""
中央控制Agent模块
遵循项目规范
"""

from typing import Dict, Any, Optional
from src.core.agent_base import AgentBase
from src.core.task_decomposer import TaskDecomposer


class CentralControlAgent(AgentBase):
    """中央控制Agent

    负责任务收口与分发
    """

    def __init__(
        self,
        name: str,
        message_bus=None
    ) -> None:
        """初始化中央控制Agent

        Args:
            name: Agent名称
            message_bus: 消息总线
        """
        super().__init__(name, message_bus)
        self._decomposer = TaskDecomposer("decomposer")
        self._agents: Dict[str, AgentBase] = {}

    def register_agent(self, agent: AgentBase) -> bool:
        """注册子Agent

        Args:
            agent: 要注册的Agent

        Returns:
            注册是否成功
        """
        if agent.name in self._agents:
            return False
        self._agents[agent.name] = agent
        return True

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务

        Args:
            task: 任务字典

        Returns:
            执行结果
        """
        action = task.get("action")
        if action == "process_requirement":
            return self._process_requirement(task)
        return {"error": "未知操作"}

    def _process_requirement(
        self,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理需求

        Args:
            task: 任务

        Returns:
            处理结果
        """
        requirement = task.get("requirement", "")
        root = self._decomposer.decompose(requirement)
        leaves = self._decomposer.get_leaf_tasks(root)
        return {
            "status": "decomposed",
            "task_count": len(leaves),
            "tasks": [t.to_dict() for t in leaves]
        }
