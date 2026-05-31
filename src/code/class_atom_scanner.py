"""
类原子化扫描器
遵循第一性原理：类原子内聚约束

核心功能：
1. 类三区分离检测（常量区/状态区/方法区）
2. 区域边界检测
3. 三区合规性自动化校验
4. 类内聚约束验证

三区分离规范：
1. 常量区（Class Constants）：类级常量，定义在类开头
2. 状态区（Class State）：实例变量和类变量
3. 方法区（Class Methods）：所有实例方法和类方法
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class ClassZone(Enum):
    """类区域类型"""
    CONSTANT = "constant"  # 常量区
    STATE = "state"        # 状态区
    METHOD = "method"      # 方法区
    UNKNOWN = "unknown"    # 未知


@dataclass
class ClassItemInfo:
    """类成员信息"""
    name: str
    zone: ClassZone
    line: int
    item_type: str  # 'assign', 'function', 'async_function'
    is_class_level: bool = True


@dataclass
class ClassStructure:
    """类结构"""
    name: str
    line: int
    constants: List[ClassItemInfo] = field(default_factory=list)
    states: List[ClassItemInfo] = field(default_factory=list)
    methods: List[ClassItemInfo] = field(default_factory=list)
    unknown: List[ClassItemInfo] = field(default_factory=list)
    has_issues: bool = False
    issues: List[str] = field(default_factory=list)
    zone_order_correct: bool = True


@dataclass
class ComplianceResult:
    """合规性检查结果"""
    class_name: str
    is_compliant: bool
    zone_order_correct: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ClassAtomScanner(ast.NodeVisitor):
    """类原子化扫描器"""
    
    def __init__(self):
        self.classes: List[ClassStructure] = []
        self.current_class = None
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """处理类定义"""
        self.current_class = node.name
        structure = self._analyze_class(node)
        self.classes.append(structure)
        self.generic_visit(node)
    
    def _analyze_class(self, node: ast.ClassDef) -> ClassStructure:
        """分析类结构"""
        structure = ClassStructure(
            name=node.name,
            line=node.lineno
        )
        
        items: List[ClassItemInfo] = []
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 方法定义
                items.append(ClassItemInfo(
                    name=item.name,
                    zone=ClassZone.METHOD,
                    line=item.lineno,
                    item_type='function' if isinstance(item, ast.FunctionDef) else 'async_function',
                    is_class_level=not item.name.startswith('_') or item.name.startswith('__')
                ))
            elif isinstance(item, ast.Assign):
                # 赋值语句
                zone = self._classify_assignment(item)
                items.append(ClassItemInfo(
                    name=item.targets[0].id if hasattr(item.targets[0], 'id') else str(item.targets[0]),
                    zone=zone,
                    line=item.lineno,
                    item_type='assign'
                ))
            elif isinstance(item, ast.AnnAssign):
                # 带类型注解的赋值
                zone = self._classify_annotated_assignment(item)
                items.append(ClassItemInfo(
                    name=item.target.id if hasattr(item.target, 'id') else str(item.target),
                    zone=zone,
                    line=item.lineno,
                    item_type='ann_assign'
                ))
        
        # 按行号排序并分配区域
        items.sort(key=lambda x: x.line)
        
        # 检测区域顺序
        structure.zone_order_correct = self._check_zone_order(items)
        
        # 分配到各个区域
        for item in items:
            if item.zone == ClassZone.CONSTANT:
                structure.constants.append(item)
            elif item.zone == ClassZone.STATE:
                structure.states.append(item)
            elif item.zone == ClassZone.METHOD:
                structure.methods.append(item)
            else:
                structure.unknown.append(item)
        
        # 检测问题
        structure.has_issues = self._check_issues(structure)
        
        return structure
    
    def _classify_assignment(self, node: ast.Assign) -> ClassZone:
        """分类赋值语句"""
        if not node.targets:
            return ClassZone.UNKNOWN
        
        target = node.targets[0]
        
        if hasattr(target, 'id'):
            name = target.id
            
            # 常量：全大写
            if name.isupper():
                return ClassZone.CONSTANT
            
            # 常量：_开头的大写
            if name.startswith('_') and name.lstrip('_').isupper():
                return ClassZone.CONSTANT
            
            # 状态：_xxx（类级变量）
            if name.startswith('_') and not name.startswith('__'):
                return ClassZone.STATE
            
            # 默认状态
            return ClassZone.STATE
        
        return ClassZone.UNKNOWN
    
    def _classify_annotated_assignment(self, node: ast.AnnAssign) -> ClassZone:
        """分类带类型注解的赋值"""
        if hasattr(node.target, 'id'):
            name = node.target.id
            
            # 常量：全大写
            if name.isupper():
                return ClassZone.CONSTANT
            
            # 常量：_开头的大写
            if name.startswith('_') and name.lstrip('_').isupper():
                return ClassZone.CONSTANT
        
        return ClassZone.STATE
    
    def _check_zone_order(self, items: List[ClassItemInfo]) -> bool:
        """检查区域顺序是否正确"""
        # 期望顺序：CONSTANT -> STATE -> METHOD
        expected_order = [ClassZone.CONSTANT, ClassZone.STATE, ClassZone.METHOD]
        
        current_zone_index = -1
        
        for item in items:
            if item.zone == ClassZone.UNKNOWN:
                continue
            
            try:
                item_zone_index = expected_order.index(item.zone)
            except ValueError:
                continue
            
            if item_zone_index < current_zone_index:
                return False
            
            current_zone_index = item_zone_index
        
        return True
    
    def _check_issues(self, structure: ClassStructure) -> bool:
        """检查类结构问题"""
        issues = []
        
        # 检查区域顺序
        if not structure.zone_order_correct:
            issues.append("类成员区域顺序不正确，应为：常量区 → 状态区 → 方法区")
        
        # 检查常量区是否在类开头
        if structure.constants and structure.methods:
            first_constant_line = min(c.line for c in structure.constants)
            first_method_line = min(m.line for m in structure.methods)
            
            if first_constant_line > first_method_line:
                issues.append("常量区应该在方法区之前")
        
        # 检查是否有多个常量块（应该集中在一起）
        if len(structure.constants) > 1:
            constant_lines = [c.line for c in structure.constants]
            constant_lines.sort()
            for i in range(len(constant_lines) - 1):
                if constant_lines[i + 1] - constant_lines[i] > 10:
                    issues.append("常量应该集中放在类开头")
                    break
        
        structure.issues = issues
        return len(issues) > 0
    
    def scan_file(self, file_path: str) -> List[ClassStructure]:
        """扫描单个文件（类方法）"""
        self.classes = []
        self.current_class = None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            self.visit(tree)
        except Exception as e:
            logger.error(f"扫描文件 {file_path} 失败: {e}")
        return self.classes


class ClassComplianceChecker:
    """类三区合规性检查器"""
    
    def __init__(self):
        self.scanner = ClassAtomScanner()
    
    def check_file(self, file_path: str) -> List[ComplianceResult]:
        """检查文件中的所有类"""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        self.scanner.visit(tree)
        
        results = []
        for cls in self.scanner.classes:
            result = ComplianceResult(
                class_name=cls.name,
                is_compliant=not cls.has_issues,
                zone_order_correct=cls.zone_order_correct,
                issues=cls.issues
            )
            results.append(result)
        
        return results
    
    def check_directory(self, directory: str) -> Dict[str, List[ComplianceResult]]:
        """检查目录中的所有类"""
        all_results = {}
        for file in Path(directory).rglob('*.py'):
            results = self.check_file(str(file))
            if results:
                all_results[str(file)] = results
        return all_results


def demo_class_atom_scanner():
    """演示类原子化扫描器"""
    print("=" * 70)
    print("类原子化扫描器演示 - 三区分离检测")
    print("=" * 70)
    print()
    
    # 良好示例
    good_code = '''
class UserService:
    """用户服务类 - 三区分离良好"""
    
    # ========== 常量区 ==========
    MAX_RETRY = 3
    DEFAULT_TIMEOUT = 30
    USER_CACHE_KEY = "user_cache"
    
    # ========== 状态区 ==========
    _users = {}
    _cache = None
    _instance_count = 0
    
    # ========== 方法区 ==========
    def get_user(self, user_id):
        """获取用户"""
        if user_id in self._users:
            return self._users[user_id]
        return None
    
    def add_user(self, user_id, user_data):
        """添加用户"""
        self._users[user_id] = user_data
        self._update_cache()
    
    def _update_cache(self):
        """更新缓存"""
        self._cache = self._users.copy()
'''

    # 问题示例
    bad_code = '''
class BadClass:
    """问题类 - 区域混乱"""
    
    def method1(self):
        """方法在前"""
        pass
    
    MAX_VALUE = 100  # 常量在中间
    _count = 0  # 状态在后面
    
    def method2(self):
        """又有方法"""
        pass
'''
    
    print("📊 良好示例分析:")
    print("-" * 70)
    temp_file = Path('/tmp/test_class_good.py')
    temp_file.write_text(good_code.strip(), encoding='utf-8')
    
    checker = ClassComplianceChecker()
    results = checker.check_file(str(temp_file))
    
    for result in results:
        print(f"类: {result.class_name}")
        print(f"  合规性: {'✓ 通过' if result.is_compliant else '✗ 不通过'}")
        print(f"  区域顺序: {'✓ 正确' if result.zone_order_correct else '✗ 错误'}")
        if result.issues:
            print(f"  问题:")
            for issue in result.issues:
                print(f"    - {issue}")
        else:
            print(f"  ✓ 无问题")
    
    print()
    print("📊 问题示例分析:")
    print("-" * 70)
    temp_file2 = Path('/tmp/test_class_bad.py')
    temp_file2.write_text(bad_code.strip(), encoding='utf-8')
    
    results2 = checker.check_file(str(temp_file2))
    
    for result in results2:
        print(f"类: {result.class_name}")
        print(f"  合规性: {'✓ 通过' if result.is_compliant else '✗ 不通过'}")
        print(f"  区域顺序: {'✓ 正确' if result.zone_order_correct else '✗ 错误'}")
        if result.issues:
            print(f"  问题:")
            for issue in result.issues:
                print(f"    - {issue}")
    
    print()
    print("=" * 70)
    print("📋 类三区分离规范:")
    print()
    print("1️⃣  常量区（CONSTANT）:")
    print("   - 位置：类开头")
    print("   - 命名：全大写（MAX_SIZE）")
    print("   - 特点：类级常量，不变")
    print()
    print("2️⃣  状态区（STATE）:")
    print("   - 位置：常量区之后")
    print("   - 命名：_xxx（类级变量）")
    print("   - 特点：实例变量/类变量")
    print()
    print("3️⃣  方法区（METHOD）:")
    print("   - 位置：状态区之后")
    print("   - 命名：小写下划线（get_user）")
    print("   - 特点：所有实例方法")
    print()
    print("✅ 正确顺序：常量区 → 状态区 → 方法区")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_class_atom_scanner()
