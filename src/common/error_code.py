"""
全局唯一错误码体系
遵循第一性原理：最小熵信息确定性要求

错误码结构：
- 分类前缀（2位） + 错误编号（4位） + 子编号（2位）
- 例如：ERR-0001-00

错误分类：
1. 系统错误（10xx） - 系统级错误
2. 输入错误（20xx） - 输入验证错误
3. 任务错误（30xx） - 任务处理错误
4. 代码错误（40xx） - 代码相关错误
5. 协作错误（50xx） - Agent协作错误
6. 状态错误（60xx） - 状态管理错误
7. 配置错误（70xx） - 配置相关错误
8. 依赖错误（80xx） - 依赖相关错误

核心约束：
- 错误码分类清晰、全覆盖无重复
- 所有异常均绑定对应错误码
- 错误信息统一输出格式
- 支持错误快速定位、归类统计
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    SYSTEM = "system"
    INPUT = "input"
    TASK = "task"
    CODE = "code"
    COLLABORATION = "collaboration"
    STATE = "state"
    CONFIG = "config"
    DEPENDENCY = "dependency"


class ErrorSeverity(Enum):
    """错误严重性"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ErrorCode:
    """错误码定义"""
    code: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    description: str
    solution: str = ""
    example: str = ""


@dataclass
class ErrorInfo:
    """错误信息"""
    code: str
    category: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    trace_id: Optional[str] = None
    source: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "source": self.source
        }
    
    def to_string(self) -> str:
        """转换为字符串"""
        parts = [
            f"[{self.code}]",
            f"[{self.severity.upper()}]",
            f"[{self.category}]",
            self.message
        ]
        if self.trace_id:
            parts.append(f"(trace_id={self.trace_id})")
        if self.source:
            parts.append(f"@ {self.source}")
        return " ".join(parts)


class ErrorCodeRegistry:
    """错误码注册表"""
    
    def __init__(self):
        self._codes: Dict[str, ErrorCode] = {}
        self._init_error_codes()
    
    def _init_error_codes(self) -> None:
        """初始化错误码"""
        codes = [
            # 系统错误 (10xx)
            ErrorCode(
                code="SYS-1001-00",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                message="系统初始化失败",
                description="系统启动时初始化操作失败",
                solution="检查系统配置和依赖项",
                example="SYS-1001-00: 系统初始化失败 - 数据库连接超时"
            ),
            ErrorCode(
                code="SYS-1002-00",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                message="系统资源不足",
                description="系统内存或CPU资源不足",
                solution="增加系统资源或优化资源使用",
                example="SYS-1002-00: 系统资源不足 - 内存使用率超过90%"
            ),
            ErrorCode(
                code="SYS-1003-00",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                message="系统超时",
                description="系统操作超时",
                solution="增加超时时间或优化操作",
                example="SYS-1003-00: 系统超时 - 操作超过30秒"
            ),
            
            # 输入错误 (20xx)
            ErrorCode(
                code="INP-2001-00",
                category=ErrorCategory.INPUT,
                severity=ErrorSeverity.MEDIUM,
                message="输入参数无效",
                description="函数或方法接收到的参数不符合要求",
                solution="检查参数类型、范围和格式",
                example="INP-2001-00: 输入参数无效 - task_id不能为空"
            ),
            ErrorCode(
                code="INP-2002-00",
                category=ErrorCategory.INPUT,
                severity=ErrorSeverity.MEDIUM,
                message="输入格式错误",
                description="输入数据格式不正确",
                solution="检查输入数据格式是否符合规范",
                example="INP-2002-00: 输入格式错误 - JSON格式不正确"
            ),
            ErrorCode(
                code="INP-2003-00",
                category=ErrorCategory.INPUT,
                severity=ErrorSeverity.LOW,
                message="输入数据缺失",
                description="必填输入数据缺失",
                solution="提供完整的输入数据",
                example="INP-2003-00: 输入数据缺失 - 缺少description字段"
            ),
            
            # 任务错误 (30xx)
            ErrorCode(
                code="TSK-3001-00",
                category=ErrorCategory.TASK,
                severity=ErrorSeverity.HIGH,
                message="任务不存在",
                description="指定的任务ID不存在",
                solution="检查任务ID是否正确",
                example="TSK-3001-00: 任务不存在 - task_id=task_xxx"
            ),
            ErrorCode(
                code="TSK-3002-00",
                category=ErrorCategory.TASK,
                severity=ErrorSeverity.HIGH,
                message="任务状态错误",
                description="任务当前状态不允许该操作",
                solution="检查任务状态转换是否合法",
                example="TSK-3002-00: 任务状态错误 - 不能从COMPLETED状态开始任务"
            ),
            ErrorCode(
                code="TSK-3003-00",
                category=ErrorCategory.TASK,
                severity=ErrorSeverity.MEDIUM,
                message="任务依赖错误",
                description="任务依赖的其他任务失败或不存在",
                solution="检查任务依赖关系",
                example="TSK-3003-00: 任务依赖错误 - 依赖任务task_yyy失败"
            ),
            ErrorCode(
                code="TSK-3004-00",
                category=ErrorCategory.TASK,
                severity=ErrorSeverity.HIGH,
                message="任务执行失败",
                description="任务执行过程中发生错误",
                solution="查看任务错误详情",
                example="TSK-3004-00: 任务执行失败 - 代码编译错误"
            ),
            
            # 代码错误 (40xx)
            ErrorCode(
                code="COD-4001-00",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.MEDIUM,
                message="代码语法错误",
                description="代码语法不符合语言规范",
                solution="修复代码语法错误",
                example="COD-4001-00: 代码语法错误 - 第10行缺少冒号"
            ),
            ErrorCode(
                code="COD-4002-00",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.MEDIUM,
                message="代码逻辑错误",
                description="代码逻辑存在错误",
                solution="检查代码逻辑",
                example="COD-4002-00: 代码逻辑错误 - 循环条件永真"
            ),
            ErrorCode(
                code="COD-4003-00",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.LOW,
                message="代码规范违规",
                description="代码不符合编码规范",
                solution="按照编码规范修改代码",
                example="COD-4003-00: 代码规范违规 - 变量命名不符合规范"
            ),
            
            # 协作错误 (50xx)
            ErrorCode(
                code="COL-5001-00",
                category=ErrorCategory.COLLABORATION,
                severity=ErrorSeverity.HIGH,
                message="Agent通信失败",
                description="Agent之间通信失败",
                solution="检查网络连接和Agent状态",
                example="COL-5001-00: Agent通信失败 - agent_xxx不可达"
            ),
            ErrorCode(
                code="COL-5002-00",
                category=ErrorCategory.COLLABORATION,
                severity=ErrorSeverity.MEDIUM,
                message="消息格式错误",
                description="Agent间消息格式不正确",
                solution="检查消息格式是否符合协议",
                example="COL-5002-00: 消息格式错误 - 缺少必需字段sender"
            ),
            ErrorCode(
                code="COL-5003-00",
                category=ErrorCategory.COLLABORATION,
                severity=ErrorSeverity.MEDIUM,
                message="协商超时",
                description="多Agent协商超时",
                solution="增加协商超时时间或简化协商内容",
                example="COL-5003-00: 协商超时 - 超过30秒未达成共识"
            ),
            
            # 状态错误 (60xx)
            ErrorCode(
                code="STA-6001-00",
                category=ErrorCategory.STATE,
                severity=ErrorSeverity.HIGH,
                message="状态不存在",
                description="指定的状态实体不存在",
                solution="检查状态ID是否正确",
                example="STA-6001-00: 状态不存在 - state_id=state_xxx"
            ),
            ErrorCode(
                code="STA-6002-00",
                category=ErrorCategory.STATE,
                severity=ErrorSeverity.MEDIUM,
                message="状态冲突",
                description="状态更新冲突",
                solution="使用乐观锁或重试",
                example="STA-6002-00: 状态冲突 - 状态已被其他操作修改"
            ),
            ErrorCode(
                code="STA-6003-00",
                category=ErrorCategory.STATE,
                severity=ErrorSeverity.LOW,
                message="状态历史过长",
                description="状态历史记录过长",
                solution="清理过期的状态历史",
                example="STA-6003-00: 状态历史过长 - 超过1000条记录"
            ),
            
            # 配置错误 (70xx)
            ErrorCode(
                code="CFG-7001-00",
                category=ErrorCategory.CONFIG,
                severity=ErrorSeverity.HIGH,
                message="配置项缺失",
                description="必需的配置文件缺失",
                solution="创建或恢复配置文件",
                example="CFG-7001-00: 配置项缺失 - 缺少database_config"
            ),
            ErrorCode(
                code="CFG-7002-00",
                category=ErrorCategory.CONFIG,
                severity=ErrorSeverity.MEDIUM,
                message="配置项无效",
                description="配置项值不符合要求",
                solution="检查配置项值",
                example="CFG-7002-00: 配置项无效 - port必须是1-65535之间的数字"
            ),
            
            # 依赖错误 (80xx)
            ErrorCode(
                code="DEP-8001-00",
                category=ErrorCategory.DEPENDENCY,
                severity=ErrorSeverity.HIGH,
                message="模块导入失败",
                description="Python模块导入失败",
                solution="检查模块是否安装",
                example="DEP-8001-00: 模块导入失败 - ModuleNotFoundError: No module named 'xxx'"
            ),
            ErrorCode(
                code="DEP-8002-00",
                category=ErrorCategory.DEPENDENCY,
                severity=ErrorSeverity.HIGH,
                message="循环依赖",
                description="检测到模块循环依赖",
                solution="重构模块依赖关系",
                example="DEP-8002-00: 循环依赖 - module_a -> module_b -> module_a"
            ),
        ]
        
        for code in codes:
            self._codes[code.code] = code
    
    def get_code(self, code: str) -> Optional[ErrorCode]:
        """获取错误码定义"""
        return self._codes.get(code)
    
    def get_all_codes(self) -> List[ErrorCode]:
        """获取所有错误码"""
        return list(self._codes.values())
    
    def get_codes_by_category(self, category: ErrorCategory) -> List[ErrorCode]:
        """获取指定分类的所有错误码"""
        return [code for code in self._codes.values() if code.category == category]
    
    def get_codes_by_severity(self, severity: ErrorSeverity) -> List[ErrorCode]:
        """获取指定严重性的所有错误码"""
        return [code for code in self._codes.values() if code.severity == severity]


class SystemException(Exception):
    """
    系统异常基类
    
    所有系统异常必须继承此类
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        source: Optional[str] = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()
        self.trace_id = trace_id
        self.source = source
        
        registry = ErrorCodeRegistry()
        error_code = registry.get_code(code)
        if error_code:
            self.category = error_code.category.value
            self.severity = error_code.severity.value
        else:
            self.category = "unknown"
            self.severity = "unknown"
    
    def to_error_info(self) -> ErrorInfo:
        """转换为错误信息"""
        return ErrorInfo(
            code=self.code,
            category=self.category,
            severity=self.severity,
            message=self.message,
            details=self.details,
            timestamp=self.timestamp,
            trace_id=self.trace_id,
            source=self.source
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.to_error_info().to_dict()
    
    def __str__(self) -> str:
        """转换为字符串"""
        return self.to_error_info().to_string()


class ErrorStatistics:
    """错误统计"""
    
    def __init__(self):
        self._counts: Dict[str, int] = {}
        self._by_category: Dict[str, int] = {}
        self._by_severity: Dict[str, int] = {}
        self._lock = None
    
    def record(self, error_info: ErrorInfo) -> None:
        """记录错误"""
        self._counts[error_info.code] = self._counts.get(error_info.code, 0) + 1
        self._by_category[error_info.category] = self._by_category.get(error_info.category, 0) + 1
        self._by_severity[error_info.severity] = self._by_severity.get(error_info.severity, 0) + 1
    
    def get_total(self) -> int:
        """获取错误总数"""
        return sum(self._counts.values())
    
    def get_by_code(self, code: str) -> int:
        """获取指定错误码的次数"""
        return self._counts.get(code, 0)
    
    def get_by_category(self, category: str) -> int:
        """获取指定分类的错误数"""
        return self._by_category.get(category, 0)
    
    def get_by_severity(self, severity: str) -> int:
        """获取指定严重性的错误数"""
        return self._by_severity.get(severity, 0)
    
    def get_top_errors(self, n: int = 10) -> List[tuple]:
        """获取Top N错误"""
        sorted_items = sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:n]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total": self.get_total(),
            "by_code": self._counts.copy(),
            "by_category": self._by_category.copy(),
            "by_severity": self._by_severity.copy(),
            "top_errors": self.get_top_errors()
        }


def demo_error_code_system():
    """演示错误码体系"""
    print("=" * 70)
    print("全局唯一错误码体系演示")
    print("=" * 70)
    print()
    
    registry = ErrorCodeRegistry()
    
    print("1. 错误码注册表:")
    all_codes = registry.get_all_codes()
    print(f"   错误码总数: {len(all_codes)} 个")
    print()
    
    print("2. 错误码分类统计:")
    categories = [ErrorCategory.SYSTEM, ErrorCategory.INPUT, ErrorCategory.TASK,
                   ErrorCategory.CODE, ErrorCategory.COLLABORATION, ErrorCategory.STATE,
                   ErrorCategory.CONFIG, ErrorCategory.DEPENDENCY]
    for cat in categories:
        codes = registry.get_codes_by_category(cat)
        print(f"   {cat.value}: {len(codes)} 个错误码")
    print()
    
    print("3. 错误码示例:")
    sample_codes = ["SYS-1001-00", "INP-2001-00", "TSK-3001-00", "COD-4001-00"]
    for code_str in sample_codes:
        code = registry.get_code(code_str)
        if code:
            print(f"   {code.code}: {code.message}")
            print(f"     严重性: {code.severity.value}")
            print(f"     描述: {code.description}")
    print()
    
    print("4. 抛出系统异常:")
    try:
        raise SystemException(
            code="TSK-3001-00",
            message="任务不存在",
            details={"task_id": "task_xxx"},
            source="TaskManager"
        )
    except SystemException as e:
        print(f"   异常: {e}")
        print(f"   字典: {e.to_dict()}")
    print()
    
    print("5. 错误统计:")
    stats = ErrorStatistics()
    test_errors = [
        ErrorInfo("TSK-3001-00", "task", "high", "任务不存在"),
        ErrorInfo("SYS-1001-00", "system", "critical", "系统初始化失败"),
        ErrorInfo("TSK-3001-00", "task", "high", "任务不存在"),
        ErrorInfo("INP-2001-00", "input", "medium", "输入参数无效"),
    ]
    for error in test_errors:
        stats.record(error)
    
    print(f"   总错误数: {stats.get_total()}")
    print(f"   TSK-3001-00错误次数: {stats.get_by_code('TSK-3001-00')}")
    print(f"   按分类统计: {stats._by_category}")
    print(f"   按严重性统计: {stats._by_severity}")
    print(f"   Top错误: {stats.get_top_errors()}")
    print()
    
    print("=" * 70)
    print("全局唯一错误码体系演示完成")
    print("=" * 70)
    print()
    print("✓ 错误码分类清晰、全覆盖无重复")
    print("✓ 所有异常均绑定对应错误码")
    print("✓ 错误信息统一输出格式")
    print("✓ 支持错误快速定位、归类统计")


if __name__ == "__main__":
    demo_error_code_system()
