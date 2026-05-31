
from src.workflow.orchestrator import create_workflow
from src.state import TaskType, TaskStatus


def main():
    print("Multi-Agent Software Engineering System starting...")
    app = create_workflow()
    initial_state = {
        "current_task": {
            "id": "task-1",
            "description": "Test task",
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
    print(f"Result: {result['current_task']['result']}")


if __name__ == "__main__":
    main()
