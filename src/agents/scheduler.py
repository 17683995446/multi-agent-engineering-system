
from src.agents.base import BaseAgent
from src.state import Task


class SchedulerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Scheduler")

    def execute(self, task: Task) -> Task:
        print(f"{self.name} executing task: {task['id']}")
        return task
