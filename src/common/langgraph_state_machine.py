"""
LangGraph状态机调度内核 - 遵循第一性原理
核心功能：
1. 完全复用LangGraph原生状态机
2. 支持流程流转、分支、回退、循环
3. 状态切换精准、无流程卡死、无状态错乱
复用LangGraph 1.2.1版本，无自研核心调度逻辑
"""

from typing import TypedDict, Annotated, Sequence
from enum import Enum
import operator
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from src.common.utils import setup_logger

logger = setup_logger(__name__)

# 可选导入LangGraph
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    StateGraph = None
    END = None
    logger.warning("LangGraph未安装，状态机功能受限")


class WorkflowStateType(str, Enum):
    """工作流状态类型"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskNodeType(str, Enum):
    """任务节点类型"""
    START = "start"
    END = "end"
    ACTION = "action"
    DECISION = "decision"
    JOIN = "join"
    FORK = "fork"


@dataclass
class NodeDefinition:
    """节点定义"""
    node_id: str
    node_type: TaskNodeType
    name: str
    description: str
    action_name: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class EdgeDefinition:
    """边定义"""
    from_node: str
    to_node: str
    condition: str = "always"  # always, condition_name, or callback name


@dataclass
class WorkflowExecution:
    """工作流执行记录"""
    execution_id: str
    workflow_id: str
    status: WorkflowStateType
    current_node: str
    history: list = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = None


class LangGraphStateMachine:
    """
    基于LangGraph的状态机
    完全复用LangGraph原生状态机，无自研核心逻辑
    """

    def __init__(self, workflow_id: str):
        if not HAS_LANGGRAPH:
            raise ImportError("LangGraph未安装，请运行: pip install langgraph")

        self.workflow_id = workflow_id
        self.graph = StateGraph(State)  # 初始化StateGraph
        self.compiled_graph = None
        self.nodes: dict[str, NodeDefinition] = {}
        self.edges: list[EdgeDefinition] = []
        self.state_history: list[dict] = []
        self.current_state: dict = {}

        logger.info(f"LangGraph状态机初始化: {workflow_id}")

    def add_node(self, node_def: NodeDefinition, action_func=None):
        """
        添加节点
        """
        self.nodes[node_def.node_id] = node_def

        if action_func:
            self.graph.add_node(node_def.node_id, action_func)
        else:
            self.graph.add_node(node_def.node_id, self._default_action)

        logger.debug(f"节点添加: {node_def.node_id} ({node_def.node_type.value})")

    def add_edge(self, from_node: str, to_node: str, condition: str = "always"):
        """
        添加边
        """
        edge = EdgeDefinition(from_node, to_node, condition)
        self.edges.append(edge)

        if condition == "always":
            self.graph.add_edge(from_node, to_node)
        else:
            logger.warning(f"条件边需要使用add_conditional_edges: {from_node} -> {to_node}")

        logger.debug(f"边添加: {from_node} -> {to_node} [{condition}]")

    def add_conditional_edges(
        self,
        from_node: str,
        path_map: dict[str, str],
        condition_func=None
    ):
        """
        添加条件边
        path_map: 从条件名到目标节点的映射
        """
        self.graph.add_conditional_edges(
            from_node,
            condition_func,
            path_map
        )

        logger.debug(f"条件边添加: {from_node} -> {list(path_map.values())}")

    def set_entry_point(self, node_id: str):
        """
        设置入口点
        """
        self.graph.set_entry_point(node_id)
        logger.debug(f"入口点设置: {node_id}")

    def set_finish_point(self, node_id: str):
        """
        设置结束点
        """
        self.graph.add_edge(node_id, END)
        logger.debug(f"结束点设置: {node_id}")

    def compile(self):
        """
        编译图
        """
        self.compiled_graph = self.graph.compile()
        logger.info(f"状态机编译完成: {self.workflow_id}")

    def execute(self, initial_state: dict) -> dict:
        """
        执行工作流
        """
        if not self.compiled_graph:
            raise RuntimeError("状态机未编译，请先调用compile()")

        logger.info(f"开始执行工作流: {self.workflow_id}")

        try:
            result = self.compiled_graph.invoke(initial_state)
            self.state_history.append(result)
            logger.info(f"工作流执行完成: {self.workflow_id}")
            return result
        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}")
            raise

    def _default_action(self, state: dict) -> dict:
        """
        默认动作
        """
        current = state.get("current_node", "unknown")
        logger.debug(f"执行节点: {current}")
        return state

    def get_current_state(self) -> dict:
        """
        获取当前状态
        """
        return self.current_state

    def get_execution_history(self) -> list[dict]:
        """
        获取执行历史
        """
        return self.state_history

    def visualize_structure(self) -> dict:
        """
        可视化结构信息
        """
        return {
            "workflow_id": self.workflow_id,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "name": n.name,
                    "type": n.node_type.value
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from": e.from_node,
                    "to": e.to_node,
                    "condition": e.condition
                }
                for e in self.edges
            ]
        }


class State(TypedDict):
    """LangGraph状态定义"""
    workflow_id: str
    current_node: str
    status: str
    result: dict
    history: Annotated[list, operator.add]
    error: str | None


class WorkflowStateMachineFactory:
    """
    工作流状态机工厂
    用于创建常见的工作流模式
    """

    @staticmethod
    def create_sequential_workflow(
        workflow_id: str,
        nodes: list[dict]
    ) -> LangGraphStateMachine:
        """
        创建顺序工作流
        """
        sm = LangGraphStateMachine(workflow_id)

        for i, node_data in enumerate(nodes):
            node_def = NodeDefinition(
                node_id=node_data["id"],
                node_type=TaskNodeType.ACTION,
                name=node_data["name"],
                description=node_data.get("description", ""),
                action_name=node_data.get("action", "")
            )
            sm.add_node(node_def)

        if nodes:
            sm.set_entry_point(nodes[0]["id"])
            for i in range(len(nodes) - 1):
                sm.add_edge(nodes[i]["id"], nodes[i + 1]["id"])
            sm.set_finish_point(nodes[-1]["id"])

        sm.compile()
        return sm

    @staticmethod
    def create_branching_workflow(
        workflow_id: str,
        decision_node: dict,
        branches: list[dict],
        merge_node: dict = None
    ) -> LangGraphStateMachine:
        """
        创建分支工作流
        """
        sm = LangGraphStateMachine(workflow_id)

        decision_def = NodeDefinition(
            node_id=decision_node["id"],
            node_type=TaskNodeType.DECISION,
            name=decision_node["name"],
            description=decision_node.get("description", "")
        )
        sm.add_node(decision_def)

        branch_end_nodes = []
        for branch in branches:
            branch_def = NodeDefinition(
                node_id=branch["id"],
                node_type=TaskNodeType.ACTION,
                name=branch["name"],
                description=branch.get("description", "")
            )
            sm.add_node(branch_def)
            branch_end_nodes.append(branch["id"])

        sm.set_entry_point(decision_node["id"])

        def route_decision(state: State) -> str:
            decision = state.get("decision", "default")
            branch_map = {f"branch_{i}": b["id"] for i, b in enumerate(branches)}
            return branch_map.get(decision, branches[0]["id"])

        sm.add_conditional_edges(
            decision_node["id"],
            route_decision,
            [f"branch_{i}" for i in range(len(branches))],
            [b["id"] for b in branches]
        )

        if merge_node:
            merge_def = NodeDefinition(
                node_id=merge_node["id"],
                node_type=TaskNodeType.JOIN,
                name=merge_node["name"],
                description=merge_node.get("description", "")
            )
            sm.add_node(merge_def)
            for end_node in branch_end_nodes:
                sm.add_edge(end_node, merge_node["id"])
            sm.set_finish_point(merge_node["id"])
        else:
            for end_node in branch_end_nodes:
                sm.set_finish_point(end_node)

        sm.compile()
        return sm

    @staticmethod
    def create_loop_workflow(
        workflow_id: str,
        loop_start: dict,
        loop_body: list[dict],
        loop_end: dict,
        max_iterations: int = 10
    ) -> LangGraphStateMachine:
        """
        创建循环工作流
        """
        sm = LangGraphStateMachine(workflow_id)

        start_def = NodeDefinition(
            node_id=loop_start["id"],
            node_type=TaskNodeType.ACTION,
            name=loop_start["name"],
            description=loop_start.get("description", "")
        )
        sm.add_node(start_def)

        for node_data in loop_body:
            node_def = NodeDefinition(
                node_id=node_data["id"],
                node_type=TaskNodeType.ACTION,
                name=node_data["name"],
                description=node_data.get("description", "")
            )
            sm.add_node(node_def)

        end_def = NodeDefinition(
            node_id=loop_end["id"],
            node_type=TaskNodeType.DECISION,
            name=loop_end["name"],
            description=loop_end.get("description", "")
        )
        sm.add_node(end_def)

        sm.set_entry_point(loop_start["id"])

        sm.add_edge(loop_start["id"], loop_body[0]["id"])
        for i in range(len(loop_body) - 1):
            sm.add_edge(loop_body[i]["id"], loop_body[i + 1]["id"])
        sm.add_edge(loop_body[-1]["id"], loop_end["id"])

        def should_continue(state: State) -> str:
            iteration = state.get("iteration", 0)
            continue_loop = state.get("continue_loop", False)

            if iteration >= max_iterations:
                return END
            elif continue_loop:
                return loop_body[0]["id"]
            else:
                return END

        sm.add_conditional_edges(
            loop_end["id"],
            should_continue,
            {"continue": loop_body[0]["id"], "end": END}
        )

        sm.compile()
        return sm

    @staticmethod
    def create_retry_workflow(
        workflow_id: str,
        main_action: dict,
        max_retries: int = 3
    ) -> LangGraphStateMachine:
        """
        创建带重试的工作流
        """
        sm = LangGraphStateMachine(workflow_id)

        main_def = NodeDefinition(
            node_id=main_action["id"],
            node_type=TaskNodeType.ACTION,
            name=main_action["name"],
            description=main_action.get("description", "")
        )
        sm.add_node(main_def)

        sm.set_entry_point(main_action["id"])

        def check_retry(state: State) -> str:
            retry_count = state.get("retry_count", 0)
            last_success = state.get("last_success", False)

            if last_success or retry_count >= max_retries:
                return END
            else:
                return main_action["id"]

        sm.add_conditional_edges(
            main_action["id"],
            check_retry,
            {"retry": main_action["id"], "end": END}
        )

        sm.compile()
        return sm
