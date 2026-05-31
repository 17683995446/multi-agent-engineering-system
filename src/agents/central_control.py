"""
总控Agent - 遵循第一性原理：仅统筹不执行，实现全局收口
核心功能：
1. 全局任务收口
2. 优先级管控
3. 权限管控
4. 统筹所有Agent工作
5. 任务闭环验收
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import hashlib
from pathlib import Path
from src.agents.base import BaseAgent
from src.common.utils import setup_logger
from src.common.atomic_entities import TaskStatus

logger = setup_logger(__name__)


class PriorityLevel(Enum):
    """优先级级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PermissionLevel(Enum):
    """权限级别"""
    ADMIN = "admin"
    FULL = "full"
    WRITE = "write"
    READ = "read"


@dataclass
class ManagedAgent:
    """被管理的Agent信息"""
    name: str
    instance: BaseAgent
    permission: PermissionLevel
    capabilities: List[str] = field(default_factory=list)
    is_active: bool = True


@dataclass
class AgentTask:
    """被管理的任务"""
    task_id: str
    description: str
    priority: PriorityLevel
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    outputs: Dict[str, Any] = field(default_factory=dict)


class CentralControlAgent(BaseAgent):
    """总控Agent - 全局收口、统筹调度"""

    def __init__(self):
        super().__init__("CentralControlAgent")
        self.agents: Dict[str, ManagedAgent] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.is_running = False

    def register_agent(self, agent: BaseAgent, permission: PermissionLevel, 
                       capabilities: Optional[List[str]] = None):
        """注册被管理的Agent"""
        managed = ManagedAgent(
            name=agent.name,
            instance=agent,
            permission=permission,
            capabilities=capabilities or []
        )
        self.agents[agent.name] = managed
        logger.info(f"Agent {agent.name} 注册成功，权限: {permission}")

    def submit_task(self, description: str, priority: PriorityLevel,
                    assignee: Optional[str] = None) -> str:
        """提交任务 - 全局收口入口"""
        task_id = hashlib.md5(f"{description}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        task = AgentTask(
            task_id=task_id,
            description=description,
            priority=priority,
            assignee=assignee,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        self.tasks[task_id] = task
        logger.info(f"任务 {task_id} 已接收: {description}")
        return task_id

    def get_tasks_by_priority(self) -> List[AgentTask]:
        """按优先级获取任务"""
        priority_order = [
            PriorityLevel.CRITICAL,
            PriorityLevel.HIGH,
            PriorityLevel.MEDIUM,
            PriorityLevel.LOW
        ]
        sorted_tasks = []
        for p in priority_order:
            sorted_tasks.extend([t for t in self.tasks.values() if t.priority == p and t.status == TaskStatus.PENDING])
        return sorted_tasks

    def check_permission(self, agent_name: str, required: PermissionLevel) -> bool:
        """权限检查"""
        if agent_name not in self.agents:
            return False
        agent_perm = self.agents[agent_name].permission
        perm_order = [
            PermissionLevel.READ,
            PermissionLevel.WRITE,
            PermissionLevel.FULL,
            PermissionLevel.ADMIN
        ]
        return perm_order.index(agent_perm) >= perm_order.index(required)

    def assign_task(self, task_id: str, agent_name: str) -> bool:
        """分配任务"""
        if task_id not in self.tasks or agent_name not in self.agents:
            return False

        task = self.tasks[task_id]
        task.assignee = agent_name
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now().isoformat()
        logger.info(f"任务 {task_id} 分配给 {agent_name}")
        return True

    def complete_task(self, task_id: str, outputs: Dict[str, Any]) -> bool:
        """完成任务 - 闭环验收"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.outputs = outputs
        task.updated_at = datetime.now().isoformat()
        logger.info(f"任务 {task_id} 验收完成")
        return True

    def start(self):
        """启动总控"""
        self.is_running = True
        logger.info(f"总控Agent {self.name} 已启动，当前管理 {len(self.agents)} 个Agent")

    def execute(self, task: Any) -> Any:
        """总控执行 - 仅统筹不执行具体业务"""
        if not self.is_running:
            self.start()

        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "register":
                return self._handle_register(task)
            elif action == "submit":
                return self._handle_submit(task)
            elif action == "assign":
                return self._handle_assign(task)
            elif action == "complete":
                return self._handle_complete(task)
            elif action == "list_tasks":
                return self._handle_list()
        return {"status": "error", "message": "未知操作"}

    def _handle_register(self, data: Dict) -> Dict:
        """处理注册（模拟）"""
        return {"status": "ok", "message": "注册处理（需实际Agent实例）"}

    def _handle_submit(self, data: Dict) -> Dict:
        """处理提交"""
        desc = data.get("description", "未命名任务")
        priority = PriorityLevel(data.get("priority", "medium"))
        assignee = data.get("assignee")
        task_id = self.submit_task(desc, priority, assignee)
        return {"status": "ok", "task_id": task_id}

    def _handle_assign(self, data: Dict) -> Dict:
        """处理分配"""
        task_id = data.get("task_id")
        agent_name = data.get("agent_name")
        if self.assign_task(task_id, agent_name):
            return {"status": "ok", "message": "分配成功"}
        return {"status": "error", "message": "分配失败"}

    def _handle_complete(self, data: Dict) -> Dict:
        """处理完成"""
        task_id = data.get("task_id")
        outputs = data.get("outputs", {})
        if self.complete_task(task_id, outputs):
            return {"status": "ok", "message": "验收完成"}
        return {"status": "error", "message": "完成失败"}

    def _handle_list(self) -> Dict:
        """处理任务列表"""
        pending = self.get_tasks_by_priority()
        return {
            "status": "ok",
            "total": len(self.tasks),
            "pending": len(pending),
            "tasks": [
                {
                    "id": t.task_id,
                    "desc": t.description,
                    "priority": t.priority.value,
                    "assignee": t.assignee,
                    "status": t.status.value
                }
                for t in self.tasks.values()
            ]
        }


def demo_central_control():
    """演示总控Agent"""
    print("========================================")
    print("总控Agent演示")
    print("========================================")
    print()

    # 创建总控
    cc = CentralControlAgent()
    cc.start()

    # 注册简单模拟Agent
    class SimpleAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name)
        def execute(self, task):
            return f"{self.name} 处理了 {task}"

    dev_agent = SimpleAgent("DeveloperAgent")
    test_agent = SimpleAgent("TestAgent")

    cc.register_agent(dev_agent, PermissionLevel.WRITE, ["coding", "debug"])
    cc.register_agent(test_agent, PermissionLevel.READ, ["testing"])

    # 提交任务
    print("提交任务...")
    task1_id = cc.submit_task("重构用户模块", PriorityLevel.HIGH)
    task2_id = cc.submit_task("修复登录Bug", PriorityLevel.CRITICAL)
    task3_id = cc.submit_task("更新文档", PriorityLevel.LOW)

    # 分配任务
    print("\n分配任务...")
    cc.assign_task(task2_id, "DeveloperAgent")
    cc.assign_task(task1_id, "DeveloperAgent")

    # 列出任务
    print("\n当前任务:")
    tasks_data = cc._handle_list()
    for t in tasks_data["tasks"]:
        print(f"  [{t['priority']}] {t['id']} - {t['desc']} ({t['assignee']})")

    # 完成任务
    print("\n完成任务...")
    cc.complete_task(task2_id, {"fixed": True, "tests_passed": 12})

    # 再次列出
    print("\n最终状态:")
    final_data = cc._handle_list()
    for t in final_data["tasks"]:
        print(f"  [{t['priority']}] {t['id']} - {t['status']}")

    print("\n✅ 演示完成！")


if __name__ == "__main__":
    demo_central_control()
