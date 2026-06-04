# 接口规范文档

## 目录

- [概述](#概述)
- [Agent接口](#agent接口)
- [消息总线接口](#消息总线接口)
- [任务分解接口](#任务分解接口)
- [代码生成接口](#代码生成接口)
- [测试生成接口](#测试生成接口)

## 概述

本文档定义系统所有模块的接口规范。所有实现必须严格遵循此文档，禁止私自扩展或修改接口签名。

## Agent接口

### AgentInterface

所有Agent必须实现的统一接口。

```python
class AgentInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent唯一标识名"""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """初始化Agent，返回是否成功"""
        pass

    @abstractmethod
    def shutdown(self) -> bool:
        """关闭Agent，返回是否成功"""
        pass

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务
        
        入参task必须含action键
        返回必须含status键
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取状态，返回含name/status/running键的字典"""
        pass
```

### 标准化任务格式

```python
{
    "action": str,        # 必填，操作类型
    "params": Dict,       # 可选，操作参数
    "context": Dict       # 可选，上下文信息
}
```

### 标准化结果格式

```python
{
    "status": str,        # 必填，success/error
    "data": Any,          # 可选，返回数据
    "error": str          # 可选，错误信息
}
```

## 消息总线接口

### MessageBusInterface

所有消息总线实现必须遵循的接口。

```python
class MessageBusInterface(ABC):
    @abstractmethod
    def register(self, agent_name: str) -> bool:
        """注册Agent"""
        pass

    @abstractmethod
    def unregister(self, agent_name: str) -> bool:
        """注销Agent"""
        pass

    @abstractmethod
    def send(self, sender: str, receiver: str, content: Dict) -> bool:
        """点对点发送消息"""
        pass

    @abstractmethod
    def broadcast(self, sender: str, content: Dict) -> int:
        """广播消息，返回接收者数量"""
        pass
```

## 任务分解接口

### TaskDecomposerInterface

```python
class TaskDecomposerInterface(ABC):
    @abstractmethod
    def decompose(self, requirement: str) -> TaskNodeInterface:
        """分解需求为任务树
        
        requirement: 非空字符串
        返回: 任务树根节点
        """
        pass

    @abstractmethod
    def get_leaf_tasks(self, root: TaskNodeInterface) -> List[TaskNodeInterface]:
        """获取所有叶子任务"""
        pass
```

### TaskNodeInterface

```python
class TaskNodeInterface(ABC):
    @property
    @abstractmethod
    def task_id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_leaf(self) -> bool:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass
```

## 代码生成接口

### CodeGeneratorInterface

```python
class CodeGeneratorInterface(ABC):
    @abstractmethod
    def generate_function(
        self,
        name: str,
        params: List[str],
        description: str,
        body: List[str]
    ) -> str:
        """生成函数代码字符串"""
        pass

    @abstractmethod
    def generate_class(self, name: str, description: str) -> str:
        """生成类代码字符串"""
        pass
```

## 测试生成接口

### TestGeneratorInterface

```python
class TestGeneratorInterface(ABC):
    @abstractmethod
    def generate_tests(
        self,
        function_name: str,
        source_code: str
    ) -> List[Dict[str, Any]]:
        """生成测试用例列表
        
        每项必须含:
        - name: 用例名称
        - input: 输入数据
        - expected: 期望输出
        - type: 用例类型(normal/empty/boundary/invalid)
        """
        pass
```

## 接口变更流程

1. 提出变更申请
2. 影响范围评估
3. 所有实现同步更新
4. 测试验证
5. 文档更新
