"""
类单一能力校验器和解耦重构器
遵循第一性原理：单一职责原则

核心功能：
1. 检测万能大类、多能力混杂类
2. 大类自动解耦拆分建议
3. 重构后单一业务能力验证
4. 类间耦合度检测
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class ClassAbilityType(Enum):
    """类能力类型"""
    DATA = "data"                  # 数据处理
    STORAGE = "storage"            # 存储
    NETWORK = "network"            # 网络
    VALIDATION = "validation"      # 验证
    UI = "ui"                      # UI
    BUSINESS = "business"          # 业务逻辑
    UTILITY = "utility"            # 工具
    UNKNOWN = "unknown"            # 未知


@dataclass
class ClassAbility:
    """类能力信息"""
    name: str
    ability_type: ClassAbilityType
    methods: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass
class ClassAnalysis:
    """类分析结果"""
    name: str
    line: int
    method_count: int
    attribute_count: int
    estimated_lines: int
    abilities: List[ClassAbility] = field(default_factory=list)
    is_super_class: bool = False
    is_multi_ability: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class CouplingInfo:
    """耦合信息"""
    class_name: str
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    coupling_score: float = 0.0
    is_over_coupled: bool = False


@dataclass
class RefactorSuggestion:
    """重构建议"""
    original_class: str
    proposed_classes: List[str]
    reason: str
    confidence: float


class ClassSingleAbilityAnalyzer(ast.NodeVisitor):
    """类单一能力分析器"""
    
    # 能力关键词
    ABILITY_KEYWORDS = {
        ClassAbilityType.DATA: [
            "data", "parse", "serialize", "deserialize", "convert", "transform",
            "json", "xml", "csv", "format", "encode", "decode"
        ],
        ClassAbilityType.STORAGE: [
            "save", "load", "store", "retrieve", "read", "write", "db", "database",
            "cache", "redis", "sql", "persist", "query", "search"
        ],
        ClassAbilityType.NETWORK: [
            "http", "request", "response", "api", "client", "server", "socket",
            "download", "upload", "connect", "disconnect", "url", "web"
        ],
        ClassAbilityType.VALIDATION: [
            "validate", "check", "verify", "is_valid", "sanitize", "clean",
            "validate", "schema", "validate_schema"
        ],
        ClassAbilityType.BUSINESS: [
            "process", "handle", "manage", "control", "service", "manager",
            "execute", "run", "business", "workflow", "task", "job"
        ],
        ClassAbilityType.UTILITY: [
            "util", "utility", "helper", "tool", "common", "math", "string",
            "date", "time", "random", "uuid", "hash"
        ]
    }
    
    # 阈值
    MAX_METHODS = 15
    MAX_ATTRIBUTES = 10
    MAX_LINES = 300
    MAX_ABILITY_TYPES = 2
    
    def __init__(self):
        self.classes: List[ClassAnalysis] = []
        self.current_class = None
        self.imports: Set[str] = set()
        self.all_class_names: Set[str] = set()
    
    def visit_Import(self, node: ast.Import) -> None:
        """记录导入"""
        for name in node.names:
            self.imports.add(name.name)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """记录导入"""
        for name in node.names:
            if node.module:
                self.imports.add(f"{node.module}.{name.name}")
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """分析类"""
        self.current_class = node.name
        self.all_class_names.add(node.name)
        
        analysis = self._analyze_single_class(node)
        self.classes.append(analysis)
        
        self.generic_visit(node)
        self.current_class = None
    
    def _analyze_single_class(self, node: ast.ClassDef) -> ClassAnalysis:
        """分析单个类"""
        analysis = ClassAnalysis(
            name=node.name,
            line=node.lineno,
            method_count=0,
            attribute_count=0,
            estimated_lines=0
        )
        
        attributes = set()
        methods = []
        
        # 统计方法和属性
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
                analysis.method_count += 1
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                if hasattr(item, 'targets') and item.targets:
                    if hasattr(item.targets[0], 'id'):
                        attributes.add(item.targets[0].id)
                        analysis.attribute_count += 1
                elif hasattr(item, 'target'):
                    if hasattr(item.target, 'id'):
                        attributes.add(item.target.id)
                        analysis.attribute_count += 1
        
        # 估计行数
        if node.body:
            analysis.estimated_lines = node.body[-1].lineno - node.lineno + 1
        else:
            analysis.estimated_lines = 10
        
        # 检测能力类型
        analysis.abilities = self._detect_abilities(methods, attributes, node)
        
        # 检查是否是万能大类
        if analysis.method_count > self.MAX_METHODS:
            analysis.is_super_class = True
            analysis.issues.append(
                f"类方法数过多 ({analysis.method_count})，建议少于 {self.MAX_METHODS}"
            )
        
        if analysis.attribute_count > self.MAX_ATTRIBUTES:
            analysis.is_super_class = True
            analysis.issues.append(
                f"类属性数过多 ({analysis.attribute_count})，建议少于 {self.MAX_ATTRIBUTES}"
            )
        
        if analysis.estimated_lines > self.MAX_LINES:
            analysis.is_super_class = True
            analysis.issues.append(
                f"类行数过多 ({analysis.estimated_lines})，建议少于 {self.MAX_LINES}"
            )
        
        if len(analysis.abilities) > self.MAX_ABILITY_TYPES:
            analysis.is_multi_ability = True
            analysis.issues.append(
                f"类承载了 {len(analysis.abilities)} 种能力类型，建议少于 {self.MAX_ABILITY_TYPES}"
            )
        
        # 生成重构建议
        analysis.suggestions = self._generate_suggestions(analysis)
        
        return analysis
    
    def _detect_abilities(self, methods: List[str], attributes: Set[str], node: ast.ClassDef) -> List[ClassAbility]:
        """检测类能力类型"""
        abilities = []
        ability_counts = defaultdict(int)
        
        # 分析方法名
        for method_name in methods:
            method_lower = method_name.lower()
            for ability_type, keywords in self.ABILITY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in method_lower:
                        ability_counts[ability_type] += 1
                        break
        
        # 分析类名
        class_name_lower = node.name.lower()
        for ability_type, keywords in self.ABILITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in class_name_lower:
                    ability_counts[ability_type] += 2
        
        # 生成能力列表
        for ability_type, count in sorted(ability_counts.items(), key=lambda x: x[1], reverse=True):
            ability = ClassAbility(
                name=f"{node.name}_{ability_type.value}",
                ability_type=ability_type,
                methods=[m for m in methods if any(k in m.lower() for k in self.ABILITY_KEYWORDS[ability_type])],
                line_start=node.lineno,
                line_end=node.lineno
            )
            abilities.append(ability)
        
        if not abilities:
            abilities.append(ClassAbility(
                name=f"{node.name}_unknown",
                ability_type=ClassAbilityType.UNKNOWN,
                methods=methods,
                attributes=list(attributes),
                line_start=node.lineno,
                line_end=node.lineno
            ))
        
        return abilities
    
    def _generate_suggestions(self, analysis: ClassAnalysis) -> List[str]:
        """生成重构建议"""
        suggestions = []
        
        if len(analysis.abilities) > 1:
            suggested_classes = [a.name for a in analysis.abilities]
            suggestions.append(
                f"建议将类拆分为：{', '.join(suggested_classes)}"
            )
        
        if analysis.method_count > self.MAX_METHODS:
            suggestions.append(
                f"建议减少方法数量，考虑拆分为 {analysis.method_count // self.MAX_METHODS + 1} 个类"
            )
        
        return suggestions


class ClassCouplingAnalyzer(ast.NodeVisitor):
    """类间耦合度分析器"""
    
    def __init__(self, all_class_names: Set[str]):
        self.all_class_names = all_class_names
        self.couplings: Dict[str, CouplingInfo] = {}
        self.current_class = None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """分析类耦合"""
        self.current_class = node.name
        info = CouplingInfo(class_name=node.name)
        self.couplings[node.name] = info
        self.generic_visit(node)
        self.current_class = None
    
    def visit_Name(self, node: ast.Name) -> None:
        """记录名称引用"""
        if node.id in self.all_class_names and self.current_class:
            if self.current_class != node.id:
                self.couplings[self.current_class].dependencies.add(node.id)
    
    def calculate_coupling_scores(self):
        """计算耦合得分"""
        # 填充被依赖关系
        for class_name, info in self.couplings.items():
            for dep in info.dependencies:
                if dep in self.couplings:
                    self.couplings[dep].dependents.add(class_name)
        
        # 计算得分
        for info in self.couplings.values():
            info.coupling_score = len(info.dependencies) + len(info.dependents)
            info.is_over_coupled = info.coupling_score > 5


def demo_single_ability_checker():
    """演示单一能力校验器"""
    print("=" * 70)
    print("类单一能力校验器 - 万能大类检测")
    print("=" * 70)
    print()
    
    # 万能大类示例
    super_class_code = '''
class GiantService:
    """万能服务类 - 承载太多能力"""
    
    MAX_RETRY = 3
    TIMEOUT = 30
    
    def __init__(self):
        self._db = None
        self._cache = {}
        self._http_client = None
    
    # 存储能力
    def save_data(self, data):
        """保存数据"""
        self._db.save(data)
    
    def load_data(self, id):
        """加载数据"""
        return self._db.get(id)
    
    # 网络能力
    def fetch_from_api(self, url):
        """从API获取"""
        return self._http_client.get(url)
    
    def send_request(self, endpoint, data):
        """发送请求"""
        return self._http_client.post(endpoint, data)
    
    # 验证能力
    def validate_user(self, user):
        """验证用户"""
        return user.id and user.name
    
    def validate_data(self, data):
        """验证数据"""
        return len(data) > 0
    
    # 业务能力
    def process_order(self, order):
        """处理订单"""
        self.validate_user(order.user)
        saved = self.save_data(order)
        self.send_request("/notify", {"order": order.id})
        return saved
    
    def handle_payment(self, payment):
        """处理支付"""
        self.validate_data(payment)
        result = self.save_data(payment)
        self.fetch_from_api("/payment/status")
        return result
    
    # 工具能力
    def format_date(self, date):
        """格式化日期"""
        return date.strftime("%Y-%m-%d")
    
    def generate_uuid(self):
        """生成UUID"""
        return str(uuid.uuid4())
'''
    
    temp_file = Path('/tmp/test_giant_class.py')
    temp_file.write_text(super_class_code.strip(), encoding='utf-8')
    
    analyzer = ClassSingleAbilityAnalyzer()
    tree = ast.parse(super_class_code)
    analyzer.visit(tree)
    
    print("📊 万能大类分析:")
    print("-" * 70)
    
    for analysis in analyzer.classes:
        print(f"类: {analysis.name}")
        print(f"  方法数: {analysis.method_count}")
        print(f"  属性数: {analysis.attribute_count}")
        print(f"  估计行数: {analysis.estimated_lines}")
        print(f"  是万能大类: {'✓' if analysis.is_super_class else '✗'}")
        print(f"  多能力混杂: {'✓' if analysis.is_multi_ability else '✗'}")
        
        if analysis.abilities:
            print(f"  能力类型: {', '.join(a.ability_type.value for a in analysis.abilities)}")
        
        if analysis.issues:
            print(f"  问题:")
            for issue in analysis.issues:
                print(f"    - {issue}")
        
        if analysis.suggestions:
            print(f"  建议:")
            for suggestion in analysis.suggestions:
                print(f"    - {suggestion}")
    
    print()
    print("=" * 70)
    print("📋 单一能力类标准:")
    print()
    print(f"✅ 方法数 ≤ {ClassSingleAbilityAnalyzer.MAX_METHODS}")
    print(f"✅ 属性数 ≤ {ClassSingleAbilityAnalyzer.MAX_ATTRIBUTES}")
    print(f"✅ 行数 ≤ {ClassSingleAbilityAnalyzer.MAX_LINES}")
    print(f"✅ 能力类型 ≤ {ClassSingleAbilityAnalyzer.MAX_ABILITY_TYPES}")
    print()
    print("✅ 每个类只承载单一业务能力")
    print("✅ 类之间低耦合")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_single_ability_checker()
