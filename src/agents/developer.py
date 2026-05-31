
from src.agents.base import BaseAgent
from src.state import Task


class DeveloperAgent(BaseAgent):
    def __init__(self):
        super().__init__("Developer")

    def execute(self, task: Task) -> Task:
        print(f"{self.name} executing task: {task['id']}")
        task["result"] = "Code changes applied successfully"
        return task
