"""
合同网协议模块 - 遵循第一性原理
核心功能：
1. 任务招标、投标、评标、授标
2. 根据Agent能力自动匹配和分发
3. 任务负载均衡，避免任务分配
4. 复用行业通用的合同网协议，无自研调度
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from uuid import uuid4
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class CNPMessageType(Enum):
    """合同网协议消息类型"""
    CFP = "cfp"  # Call for Proposal - 招标
    PROPOSE = "propose"  # 投标
    ACCEPT = "accept"  # 接受投标
    REJECT = "reject"  # 拒绝投标
    CANCEL = "cancel"  # 取消
    INFORM = "inform"  # 通知结果
    FAILURE = "failure"  # 执行失败


class BidStatus(Enum):
    """投标状态"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class TaskRequirement:
    """任务需求"""
    task_id: str
    description: str
    required_capabilities: Set[str]  # 所需能力
    estimated_effort: float  # 预估工作量
    deadline: Optional[str] = None
    priority: int = 1  # 优先级，数字越小越重要


@dataclass
class Bid:
    """投标信息"""
    bid_id: str
    bidder_name: str
    task_id: str
    proposed_cost: float  # 成本/成本预估
    proposed_effort: float  # 预计工作量
    proposed_start_time: Optional[str] = None
    confidence: float = 1.0  # 完成信心值
    status: BidStatus = BidStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentWorkload:
    """Agent负载信息"""
    agent_name: str
    current_tasks: List[str] = field(default_factory=list)
    total_effort: float = 0.0
    max_capacity: float = 10.0  # 最大容量


@dataclass
class TaskAssignment:
    """任务分配结果"""
    task_id: str
    assigned_agent: str
    bid: Optional[Bid]
    assigned_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ContractNetProtocol:
    """
    合同网协议实现
    遵循经典合同网协议，无自研调度
    """

    def __init__(self):
        self.pending_tasks: Dict[str, TaskRequirement] = {}
        self.active_bids: Dict[str, List[Bid]] = {}
        self.assignments: Dict[str, TaskAssignment] = {}
        self.agent_workloads: Dict[str, AgentWorkload] = {}
        self.agent_capabilities: Dict[str, Set[str]] = {}
        self.task_bids_map: Dict[str, List[Bid]] = {}

        logger.info("合同网协议初始化完成")

    def register_agent_capabilities(self, agent_name: str, capabilities: Set[str], max_capacity: float = 10.0):
        """
        注册Agent的能力信息
        """
        self.agent_capabilities[agent_name] = capabilities
        if agent_name not in self.agent_workloads:
            self.agent_workloads[agent_name] = AgentWorkload(agent_name=agent_name, max_capacity=max_capacity)
        
        logger.info(f"Agent {agent_name} 能力注册完成: {capabilities}, 容量: {max_capacity}")

    def announce_task(self, task_requirement: TaskRequirement) -> str:
        """
        发布任务公告（Call for Proposal）
        返回：公告所有有能力处理该任务的Agent
        """
        task_id = task_requirement.task_id
        self.pending_tasks[task_id] = task_requirement
        self.active_bids[task_id] = []
        logger.info(f"任务招标: {task_requirement.description}")

        eligible_agents = self._find_eligible_agents(task_requirement)
        logger.info(f"找到 {len(eligible_agents)} 个符合条件的Agent")

        return task_id

    def _find_eligible_agents(self, task_requirement: TaskRequirement) -> List[str]:
        """
        查找符合要求的Agent
        """
        eligible_agents = []
        required_caps = task_requirement.required_capabilities

        for agent_name, agent_caps in self.agent_capabilities.items():
            # 检查能力匹配
            if required_caps.issubset(agent_caps):
                eligible_agents.append(agent_name)

        return eligible_agents

    def submit_bid(self, task_id: str, bidder_name: str, proposed_cost: float, proposed_effort: float, 
                   proposed_start_time: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Optional[Bid]:
        """
        Agent提交投标
        """
        if task_id not in self.pending_tasks:
            logger.warning(f"任务 {task_id} 不存在或已结束招标")
            return None

        bid = Bid(
            bid_id=str(uuid4())[:8],
            bidder_name=bidder_name,
            task_id=task_id,
            proposed_cost=proposed_cost,
            proposed_effort=proposed_effort,
            proposed_start_time=proposed_start_time,
            metadata=metadata or {}
        )

        if task_id not in self.task_bids_map:
            self.task_bids_map[task_id] = []
        self.task_bids_map[task_id].append(bid)
        self.active_bids[task_id].append(bid)

        logger.info(f"Agent {bidder_name} 对任务 {task_id} 提交投标，成本: {proposed_cost}")
        return bid

    def evaluate_bids(self, task_id: str) -> Optional[Bid]:
        """
        评估所有投标并选择最优的
        使用行业通用的评标策略：
        1. 优先考虑Agent的成本
        2. 考虑负载均衡
        3. 综合评估
        """
        if task_id not in self.active_bids or not self.active_bids[task_id]:
            logger.warning(f"任务 {task_id} 没有投标")
            return None

        bids = self.active_bids[task_id]

        # 计算每个投标的综合得分
        scored_bids = []
        for bid in bids:
            score = self._calculate_bid_score(bid)
            scored_bids.append((bid, score))

        # 按得分排序
        scored_bids.sort(key=lambda x: x[1], reverse=True)
        best_bid = scored_bids[0][0]
        best_bid.status = BidStatus.ACCEPTED

        # 拒绝其他投标
        for bid in bids:
            if bid != best_bid:
                bid.status = BidStatus.REJECTED

        logger.info(f"任务 {task_id} 最佳投标选择: {best_bid.bidder_name}")
        return best_bid

    def _calculate_bid_score(self, bid: Bid) -> float:
        """
        计算投标分数
        综合考虑成本、Agent负载、预估工作量等因素
        """
        base_score = 100.0
        
        # 成本越低越好
        cost_factor = max(0, 50 - bid.proposed_cost)
        
        # 考虑Agent负载
        if bid.bidder_name in self.agent_workloads:
            workload = self.agent_workloads[bid.bidder_name]
            capacity_usage = workload.total_effort / workload.max_capacity
            # 负载越低越好
            load_factor = 30 * (1.0 - capacity_usage)
        
        # 考虑信心值
        confidence_factor = 20 * bid.confidence
        
        total_score = cost_factor + load_factor + confidence_factor
        return total_score

    def assign_task(self, task_id: str, bid: Bid) -> TaskAssignment:
        """
        任务分配
        """
        assignment = TaskAssignment(
            task_id=task_id,
            assigned_agent=bid.bidder_name,
            bid=bid
        )

        self.assignments[task_id] = assignment

        # 更新Agent负载
        if bid.bidder_name in self.agent_workloads:
            self.agent_workloads[bid.bidder_name].current_tasks.append(task_id)
            self.agent_workloads[bid.bidder_name].total_effort += bid.proposed_effort

        logger.info(f"任务 {task_id} 分配给 {bid.bidder_name}")
        return assignment

    def complete_task(self, task_id: str):
        """
        标记任务完成
        """
        if task_id in self.assignments:
            assignment = self.assignments[task_id]
            agent_name = assignment.assigned_agent

            # 从Agent负载中移除
            if agent_name in self.agent_workloads:
                if task_id in self.agent_workloads[agent_name].current_tasks:
                    self.agent_workloads[agent_name].current_tasks.remove(task_id)
                    self.agent_workloads[agent_name].total_effort -= assignment.bid.proposed_effort

            logger.info(f"任务 {task_id} 完成，从 {agent_name} 负载中移除")

    def get_bids_for_task(self, task_id: str) -> List[Bid]:
        """
        获取任务的所有投标
        """
        return self.task_bids_map.get(task_id, [])

    def get_agent_workload(self, agent_name: str) -> Optional[AgentWorkload]:
        """
        获取Agent的负载信息
        """
        return self.agent_workloads.get(agent_name)

    def check_load_balancing_info(self) -> Dict[str, Any]:
        """
        获取负载均衡信息
        """
        info = {
            "agents": {},
            "total_tasks": len(self.assignments),
            "pending_tasks": len(self.pending_tasks)
        }

        for agent_name, workload in self.agent_workloads.items():
            info["agents"][agent_name] = {
                "current_tasks": workload.current_tasks,  # 返回实际的任务ID列表
                "task_count": len(workload.current_tasks),  # 同时返回任务数量
                "total_effort": workload.total_effort,
                "capacity": workload.max_capacity,
                "utilization": workload.total_effort / workload.max_capacity
            }

        return info

    def auto_bid(self, task_requirement: TaskRequirement, agent_name: str) -> Optional[Bid]:
        """
        自动为Agent生成投标
        模拟行业通用的自动投标策略
        """
        if agent_name not in self.agent_capabilities:
            return None

        # 检查Agent能力
        if not task_requirement.required_capabilities.issubset(self.agent_capabilities[agent_name]):
            return None

        # 计算预估成本（基于当前负载）
        workload = self.agent_workloads.get(agent_name, AgentWorkload(agent_name=agent_name))
        current_load = workload.total_effort / workload.max_capacity
        
        # 成本随负载增加而增加
        base_cost = task_requirement.estimated_effort
        load_multiplier = 1.0 + (current_load * 0.5)
        proposed_cost = base_cost * load_multiplier

        # 自动投标
        return self.submit_bid(
            task_requirement.task_id,
            agent_name,
            proposed_cost,
            task_requirement.estimated_effort
        )

    def full_cnp_cycle(self, task_requirement: TaskRequirement) -> Optional[TaskAssignment]:
        """
        完整的合同网协议流程
        从招标→投标→评标→授标
        """
        # 1. 招标
        task_id = self.announce_task(task_requirement)

        # 2. 让符合要求的Agent自动投标
        eligible_agents = self._find_eligible_agents(task_requirement)
        for agent_name in eligible_agents:
            self.auto_bid(task_requirement, agent_name)

        # 3. 评标
        best_bid = self.evaluate_bids(task_id)

        # 4. 授标
        if best_bid:
            return self.assign_task(task_id, best_bid)

        return None
