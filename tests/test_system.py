
import pytest
from src.state import TaskType, TaskStatus
from src.workflow.orchestrator import create_workflow


def test_basic_workflow():
    app = create_workflow()
    initial_state = {
        "current_task": {
            "id": "test-1",
            "description": "Test workflow",
            "type": TaskType.DEVELOPMENT,
            "status": TaskStatus.PENDING,
            "subtasks": [],
            "assigned_agent": None,
            "result": ""
        },
        "messages": [],
        "history": []
    }
    result = app.invoke(initial_state)
    assert result["current_task"]["result"] == "Task completed successfully"
    assert result["current_task"]["status"] == TaskStatus.COMPLETED
