"""
开发Agent模块
遵循项目规范
"""

from typing import Dict, Any, Optional
from src.core.agent_base import AgentBase, AgentStatus


class DevelopmentAgent(AgentBase):
    """开发Agent

    负责代码生成与修改
    """

    def __init__(
        self,
        name: str,
        message_bus=None
    ) -> None:
        """初始化开发Agent

        Args:
            name: Agent名称
            message_bus: 消息总线
        """
        super().__init__(name, message_bus)
        self._history: list = []

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务

        Args:
            task: 任务字典

        Returns:
            执行结果
        """
        action = task.get("action")
        if action == "generate":
            return self._generate_code(task)
        if action == "modify":
            return self._modify_code(task)
        return {"error": "未知操作"}

    def _generate_code(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """生成代码

        Args:
            task: 任务

        Returns:
            生成结果
        """
        code_type = task.get("type", "function")
        name = task.get("name", "unnamed")
        code = self._build_code(code_type, name, task)
        self._history.append({"type": "generate", "name": name})
        return {"code": code, "type": code_type}

    def _build_code(
        self,
        code_type: str,
        name: str,
        task: Dict[str, Any]
    ) -> str:
        """构建代码字符串

        Args:
            code_type: 代码类型
            name: 名称
            task: 任务

        Returns:
            代码字符串
        """
        if code_type == "function":
            return self._build_function(name, task)
        if code_type == "class":
            return self._build_class(name, task)
        return ""

    def _build_function(
        self,
        name: str,
        task: Dict[str, Any]
    ) -> str:
        """构建函数代码

        Args:
            name: 函数名
            task: 任务

        Returns:
            函数代码
        """
        desc = task.get("description", "")
        params = task.get("params", [])
        body = task.get("body", ["pass"])
        lines = [f"def {name}({', '.join(params)}):"]
        if desc:
            lines.append(f'    """{desc}"""')
        for line in body:
            lines.append(f"    {line}")
        return "\n".join(lines)

    def _build_class(
        self,
        name: str,
        task: Dict[str, Any]
    ) -> str:
        """构建类代码

        Args:
            name: 类名
            task: 任务

        Returns:
            类代码
        """
        desc = task.get("description", "")
        lines = [f"class {name}:"]
        if desc:
            lines.append(f'    """{desc}"""')
        lines.append("    def __init__(self):")
        lines.append("        pass")
        return "\n".join(lines)

    def _modify_code(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """修改代码

        Args:
            task: 任务

        Returns:
            修改结果
        """
        return {"status": "modified"}
