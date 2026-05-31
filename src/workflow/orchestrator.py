"""
LangGraph工作流编排器 - 调度中枢层核心组件
遵循第一性原理：复用LangGraph原生状态机，不自定义调度内核

功能演示：
1. 状态图创建与管理
2. 节点定义与添加
3. 边关系（单向边、条件边）
4. 流程流转与状态传递
5. 分支回退机制
"""

from langgraph.graph import StateGraph, END
from src.state import SystemState, TaskStatus
from typing import Literal
from src.common.utils import setup_logger

logger = setup_logger(__name__)


def validate_input(state: SystemState) -> SystemState:
    """节点1: 输入验证"""
    logger.info("Step 1: Validating input...")
    new_state = state.copy()
    if new_state.get("current_task"):
        new_state["current_task"]["status"] = TaskStatus.IN_PROGRESS
    return new_state


def analyze_requirements(state: SystemState) -> SystemState:
    """节点2: 需求分析"""
    logger.info("Step 2: Analyzing requirements...")
    return state


def execute_task(state: SystemState) -> SystemState:
    """节点3: 任务执行"""
    logger.info("Step 3: Executing task...")
    new_state = state.copy()
    if new_state.get("current_task"):
        new_state["current_task"]["status"] = TaskStatus.COMPLETED
        new_state["current_task"]["result"] = "Task executed successfully"
    return new_state


def review_results(state: SystemState) -> SystemState:
    """节点4: 结果评审"""
    logger.info("Step 4: Reviewing results...")
    return state


def should_retry_or_complete(state: SystemState) -> Literal["retry", "complete"]:
    """条件路由：根据评审结果决定是否重试"""
    task = state.get("current_task")
    if task and task.get("status") == TaskStatus.COMPLETED:
        logger.info("Decision: Task completed successfully")
        return "complete"
    logger.info("Decision: Need to retry")
    return "retry"


def create_langgraph_workflow() -> StateGraph:
    """
    创建LangGraph工作流
    流程: validate_input → analyze_requirements → execute_task → review_results
    分支: review_results根据结果决定是否回退重试
    """
    workflow = StateGraph(SystemState)

    workflow.add_node("validate_input", validate_input)
    workflow.add_node("analyze_requirements", analyze_requirements)
    workflow.add_node("execute_task", execute_task)
    workflow.add_node("review_results", review_results)

    workflow.set_entry_point("validate_input")

    workflow.add_edge("validate_input", "analyze_requirements")
    workflow.add_edge("analyze_requirements", "execute_task")
    workflow.add_edge("execute_task", "review_results")

    workflow.add_conditional_edges(
        "review_results",
        should_retry_or_complete,
        {
            "retry": "execute_task",
            "complete": END
        }
    )

    return workflow.compile()


def run_demo():
    """演示LangGraph工作流"""
    print("=" * 60)
    print("LangGraph工作流演示")
    print("=" * 60)
    print()

    app = create_langgraph_workflow()

    initial_state = {
        "current_task": {
            "id": "demo-task-1",
            "description": "Demo task to test LangGraph workflow",
            "type": "DEVELOPMENT",
            "status": TaskStatus.PENDING,
            "subtasks": [],
            "assigned_agent": None,
            "result": ""
        },
        "messages": [],
        "history": []
    }

    print("Initial state:")
    print(f"  Task ID: {initial_state['current_task']['id']}")
    print(f"  Task status: {initial_state['current_task']['status']}")
    print()

    print("Running workflow...")
    print("-" * 60)

    result = app.invoke(initial_state)

    print("-" * 60)
    print()
    print("Workflow completed!")
    print()
    print("Final state:")
    print(f"  Task ID: {result['current_task']['id']}")
    print(f"  Task status: {result['current_task']['status']}")
    print(f"  Task result: {result['current_task'].get('result', 'N/A')}")

    print()
    print("=" * 60)
    print("LangGraph integration successful!")
    print("=" * 60)

    return result


if __name__ == "__main__":
    run_demo()
