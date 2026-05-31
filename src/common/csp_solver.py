"""
CSP约束满足冲突检测算法
遵循第一性原理：信息最小熵公理

核心功能：
1. 约束定义与检测
2. 冲突检测
3. 约束传播
4. 回溯搜索
5. 冲突解决策略
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class ConstraintType(Enum):
    """约束类型"""
    UNARY = "unary"
    BINARY = "binary"
    NARY = "nary"
    GLOBAL = "global"


class ConflictType(Enum):
    """冲突类型"""
    VALUE_CONFLICT = "value_conflict"
    DOMAIN_CONFLICT = "domain_conflict"
    CONSTRAINT_VIOLATION = "constraint_violation"


class SearchStrategy(Enum):
    """搜索策略"""
    BACKTRACKING = "backtracking"
    FORWARD_CHECKING = "forward_checking"
    MAC = "mac"
    MIN_CONFLICT = "min_conflict"


@dataclass
class Variable:
    """
    CSP变量
    
    属性：
    - name: 变量名
    - domain: 值域
    - value: 当前赋值
    - constraints: 约束列表
    """
    name: str
    domain: List[Any] = field(default_factory=list)
    value: Optional[Any] = None
    constraints: List[str] = field(default_factory=list)
    
    def is_assigned(self) -> bool:
        """检查变量是否已赋值"""
        return self.value is not None
    
    def clone(self) -> 'Variable':
        """克隆变量"""
        return Variable(
            name=self.name,
            domain=self.domain.copy(),
            value=self.value,
            constraints=self.constraints.copy()
        )


@dataclass
class Constraint:
    """
    CSP约束
    
    属性：
    - name: 约束名
    - type: 约束类型
    - variables: 涉及的变量列表
    - check: 约束检查函数
    """
    name: str
    type: ConstraintType
    variables: List[str]
    check: Callable[..., bool]
    description: str = ""
    
    def is_satisfied(self, variables: Dict[str, Variable]) -> bool:
        """检查约束是否满足"""
        values = [variables[name].value for name in self.variables if variables[name].is_assigned()]
        if len(values) < len(self.variables):
            return True
        return self.check(*[variables[name].value for name in self.variables])


@dataclass
class Conflict:
    """
    冲突记录
    
    属性：
    - conflict_id: 冲突ID
    - type: 冲突类型
    - variables: 涉及的变量
    - constraint: 违反的约束
    - description: 描述
    """
    conflict_id: str
    type: ConflictType
    variables: List[str]
    constraint: Optional[str] = None
    description: str = ""


@dataclass
class CSPSolution:
    """
    CSP解
    
    属性：
    - assignments: 变量赋值
    - conflicts: 冲突列表
    - is_solved: 是否找到解
    - steps: 搜索步数
    """
    assignments: Dict[str, Any] = field(default_factory=dict)
    conflicts: List[Conflict] = field(default_factory=list)
    is_solved: bool = False
    steps: int = 0


class CSPSolver:
    """
    CSP约束满足求解器
    
    核心方法：
    - add_variable: 添加变量
    - add_constraint: 添加约束
    - detect_conflicts: 检测冲突
    - solve: 求解CSP
    - apply_forward_checking: 前向检查
    """
    
    def __init__(self, name: str = "csp_solver"):
        """初始化CSP求解器"""
        self.name = name
        self.variables: Dict[str, Variable] = {}
        self.constraints: Dict[str, Constraint] = {}
        self.conflicts: List[Conflict] = []
        logger.info(f"CSP求解器初始化: {name}")
    
    def add_variable(self, variable: Variable) -> None:
        """添加变量"""
        self.variables[variable.name] = variable
        logger.debug(f"添加变量: {variable.name}")
    
    def add_constraint(self, constraint: Constraint) -> None:
        """添加约束"""
        self.constraints[constraint.name] = constraint
        for var_name in constraint.variables:
            if var_name in self.variables:
                self.variables[var_name].constraints.append(constraint.name)
        logger.debug(f"添加约束: {constraint.name}")
    
    def detect_conflicts(self) -> List[Conflict]:
        """检测冲突"""
        self.conflicts = []
        conflict_id = 0
        
        for constraint in self.constraints.values():
            if not constraint.is_satisfied(self.variables):
                conflict = Conflict(
                    conflict_id=f"conflict_{conflict_id}",
                    type=ConflictType.CONSTRAINT_VIOLATION,
                    variables=constraint.variables.copy(),
                    constraint=constraint.name,
                    description=f"约束违反: {constraint.description}"
                )
                self.conflicts.append(conflict)
                conflict_id += 1
        
        logger.info(f"检测到 {len(self.conflicts)} 个冲突")
        return self.conflicts
    
    def _select_unassigned_variable(self) -> Optional[str]:
        """选择未赋值的变量（MRV启发式）"""
        unassigned = [
            var_name for var_name, var in self.variables.items() 
            if not var.is_assigned()
        ]
        if not unassigned:
            return None
        return min(unassigned, key=lambda name: len(self.variables[name].domain))
    
    def _order_domain_values(self, var_name: str) -> List[Any]:
        """值域排序（LCV启发式）"""
        values = self.variables[var_name].domain.copy()
        
        def count_constraints(value: Any) -> int:
            count = 0
            self.variables[var_name].value = value
            for constraint_name in self.variables[var_name].constraints:
                constraint = self.constraints[constraint_name]
                if not constraint.is_satisfied(self.variables):
                    count += 1
            self.variables[var_name].value = None
            return count
        
        return sorted(values, key=count_constraints)
    
    def _forward_checking(self, var_name: str) -> bool:
        """前向检查"""
        for constraint_name in self.variables[var_name].constraints:
            constraint = self.constraints[constraint_name]
            constraint_type = constraint.type
            if constraint_type == ConstraintType.BINARY:
                other_vars = [v for v in constraint.variables if v != var_name]
                for other_var in other_vars:
                    if not self.variables[other_var].is_assigned():
                        valid_values = []
                        for value in self.variables[other_var].domain:
                            old_value = self.variables[other_var].value
                            self.variables[other_var].value = value
                            if constraint.is_satisfied(self.variables):
                                valid_values.append(value)
                            self.variables[other_var].value = old_value
                        if not valid_values:
                            return False
                        self.variables[other_var].domain = valid_values
        return True
    
    def _backtrack(self, steps: int = 0) -> Tuple[CSPSolution, int]:
        """回溯搜索"""
        steps += 1
        
        var_name = self._select_unassigned_variable()
        if var_name is None:
            assignments = {name: var.value for name, var in self.variables.items()}
            solution = CSPSolution(
                assignments=assignments,
                conflicts=[],
                is_solved=True,
                steps=steps
            )
            return solution, steps
        
        solution = CSPSolution(steps=steps)
        
        for value in self._order_domain_values(var_name):
            self.variables[var_name].value = value
            
            if self._forward_checking(var_name):
                solution, steps = self._backtrack(steps)
                if solution.is_solved:
                    return solution, steps
            
            self.variables[var_name].value = None
        
        return solution, steps
    
    def solve(
        self,
        strategy: SearchStrategy = SearchStrategy.BACKTRACKING,
        max_steps: int = 10000
    ) -> CSPSolution:
        """求解CSP"""
        logger.info(f"开始求解CSP，策略: {strategy.value}")
        
        original_domains = {name: var.domain.copy() for name, var in self.variables.items()}
        original_values = {name: var.value for name, var in self.variables.items()}
        
        solution, steps = self._backtrack(0)
        
        for name, var in self.variables.items():
            var.domain = original_domains[name]
            var.value = original_values[name]
        
        logger.info(f"求解完成，步数: {steps}, 找到解: {solution.is_solved}")
        return solution
    
    def get_conflicts(self) -> List[Conflict]:
        """获取当前冲突"""
        return self.detect_conflicts()
    
    def reset(self) -> None:
        """重置求解器状态"""
        for var in self.variables.values():
            var.value = None
        self.conflicts = []
        logger.info("CSP求解器状态重置")


class ConflictResolver:
    """
    冲突解决器
    
    核心方法：
    - resolve_conflicts: 解决冲突
    - suggest_resolutions: 建议解决策略
    """
    
    def __init__(self):
        """初始化冲突解决器"""
        self.resolution_strategies: List[Callable] = []
        logger.info("冲突解决器初始化")
    
    def suggest_resolutions(self, conflicts: List[Conflict]) -> List[Dict[str, Any]]:
        """建议解决策略"""
        resolutions = []
        for conflict in conflicts:
            resolution = {
                "conflict_id": conflict.conflict_id,
                "type": conflict.type.value,
                "variables": conflict.variables,
                "suggestions": [
                    "调整变量值域",
                    "松弛约束条件",
                    "重新分配变量值",
                    "添加新的约束"
                ]
            }
            resolutions.append(resolution)
        return resolutions
    
    def resolve_conflicts(
        self,
        solver: CSPSolver,
        conflicts: List[Conflict]
    ) -> bool:
        """解决冲突"""
        logger.info(f"尝试解决 {len(conflicts)} 个冲突")
        for conflict in conflicts:
            pass
        return False
