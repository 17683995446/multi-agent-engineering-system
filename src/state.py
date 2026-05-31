
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from enum import Enum
from langgraph.graph import add_messages


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    REFACTORING = "refactoring"
    DEVELOPMENT = "development"
    BUGFIX = "bugfix"


class Task(TypedDict):
    id: str
    description: str
    type: TaskType
    status: TaskStatus
    subtasks: List["Task"]
    assigned_agent: Optional[str]
    result: Optional[str]


class SystemState(TypedDict):
    current_task: Optional[Task]
    messages: Annotated[List[Dict[str, Any]], add_messages]
    history: List[Task]
