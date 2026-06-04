"""
核心接口定义模块
所有模块依赖此接口，禁止直接依赖实现
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class AgentInterface(ABC):
    """Agent统一接口

    所有Agent必须实现此接口
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent名称

        Returns:
            Agent唯一标识名
        """
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """初始化Agent

        Returns:
            初始化是否成功
        """
        pass

    @abstractmethod
    def shutdown(self) -> bool:
        """关闭Agent

        Returns:
            关闭是否成功
        """
        pass

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务

        Args:
            task: 标准化任务字典，必须含action键

        Returns:
            标准化结果字典，必须含status键
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取状态

        Returns:
            状态字典，含name/status/running键
        """
        pass


class MessageBusInterface(ABC):
    """消息总线接口

    所有消息总线实现必须遵循此接口
    """

    @abstractmethod
    def register(self, agent_name: str) -> bool:
        """注册Agent

        Args:
            agent_name: Agent名称

        Returns:
            注册是否成功
        """
        pass

    @abstractmethod
    def unregister(self, agent_name: str) -> bool:
        """注销Agent

        Args:
            agent_name: Agent名称

        Returns:
            注销是否成功
        """
        pass

    @abstractmethod
    def send(self, sender: str, receiver: str, content: Dict[str, Any]) -> bool:
        """发送消息

        Args:
            sender: 发送者
            receiver: 接收者
            content: 消息内容

        Returns:
            发送是否成功
        """
        pass

    @abstractmethod
    def broadcast(self, sender: str, content: Dict[str, Any]) -> int:
        """广播消息

        Args:
            sender: 发送者
            content: 消息内容

        Returns:
            接收者数量
        """
        pass


class TaskDecomposerInterface(ABC):
    """任务分解器接口

    所有分解器实现必须遵循此接口
    """

    @abstractmethod
    def decompose(self, requirement: str) -> 'TaskNodeInterface':
        """分解需求

        Args:
            requirement: 需求描述字符串，非空

        Returns:
            任务树根节点
        """
        pass

    @abstractmethod
    def get_leaf_tasks(self, root: 'TaskNodeInterface') -> List['TaskNodeInterface']:
        """获取叶子任务

        Args:
            root: 根节点

        Returns:
            叶子任务列表
        """
        pass


class TaskNodeInterface(ABC):
    """任务节点接口

    任务树节点抽象
    """

    @property
    @abstractmethod
    def task_id(self) -> str:
        """任务ID"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """任务名称"""
        pass

    @abstractmethod
    def is_leaf(self) -> bool:
        """是否为叶子

        Returns:
            是否为叶子节点
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """转字典

        Returns:
            字典表示
        """
        pass


class CodeGeneratorInterface(ABC):
    """代码生成器接口

    所有代码生成器实现必须遵循此接口
    """

    @abstractmethod
    def generate_function(
        self,
        name: str,
        params: List[str],
        description: str,
        body: List[str]
    ) -> str:
        """生成函数

        Args:
            name: 函数名
            params: 参数列表
            description: 描述
            body: 函数体

        Returns:
            函数代码字符串
        """
        pass

    @abstractmethod
    def generate_class(self, name: str, description: str) -> str:
        """生成类

        Args:
            name: 类名
            description: 描述

        Returns:
            类代码字符串
        """
        pass


class TestGeneratorInterface(ABC):
    """测试生成器接口

    所有测试生成器实现必须遵循此接口
    """

    @abstractmethod
    def generate_tests(
        self,
        function_name: str,
        source_code: str
    ) -> List[Dict[str, Any]]:
        """生成测试用例

        Args:
            function_name: 函数名
            source_code: 源码

        Returns:
            测试用例列表，每项含name/input/expected/type键
        """
        pass
