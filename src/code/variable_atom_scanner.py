"""
变量原子化扫描器
遵循第一性原理：单一语义原子约束

核心功能：
1. 自动分类变量：常量/状态/临时
2. 检测模糊命名、多语义变量
3. 自动标准化修正变量
4. 验证单一语义原子约束
"""

import ast
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class VariableCategory(Enum):
    """变量类别"""
    CONSTANT = "constant"      # 常量：全大写下划线
    STATE = "state"            # 状态：描述状态变化
    TEMPORARY = "temporary"    # 临时：循环/计算临时值
    UNKNOWN = "unknown"        # 未知：无法分类


class VariableIssueType(Enum):
    """问题类型"""
    VAGUE_NAMING = "vague_naming"
    MULTI_SEMANTIC = "multi_semantic"
    NAMING_VIOLATION = "naming_violation"


@dataclass
class VariableInfo:
    """变量信息"""
    name: str
    category: VariableCategory
    line: int
    column: int
    is_assigned: bool
    is_modified: bool = False
    issues: List[Tuple[VariableIssueType, str]] = field(default_factory=list)
    suggestion: Optional[str] = None


@dataclass
class ScanResult:
    """扫描结果"""
    variables: List[VariableInfo] = field(default_factory=list)
    total_count: int = 0
    issue_count: int = 0


class VariableAtomScanner(ast.NodeVisitor):
    """变量原子化扫描器"""
    
    # 模糊命名模式
    VAGUE_PATTERNS = [
        re.compile(r'^temp$', re.IGNORECASE),
        re.compile(r'^tmp$', re.IGNORECASE),
        re.compile(r'^data$', re.IGNORECASE),
        re.compile(r'^info$', re.IGNORECASE),
        re.compile(r'^val$', re.IGNORECASE),
        re.compile(r'^value$', re.IGNORECASE),
        re.compile(r'^result$', re.IGNORECASE),
        re.compile(r'^res$', re.IGNORECASE),
        re.compile(r'^x$', re.IGNORECASE),
        re.compile(r'^y$', re.IGNORECASE),
        re.compile(r'^z$', re.IGNORECASE),
        re.compile(r'^i$', re.IGNORECASE),
        re.compile(r'^j$', re.IGNORECASE),
        re.compile(r'^k$', re.IGNORECASE),
        re.compile(r'^a$', re.IGNORECASE),
        re.compile(r'^b$', re.IGNORECASE),
        re.compile(r'^c$', re.IGNORECASE),
        re.compile(r'^obj$', re.IGNORECASE),
        re.compile(r'^object$', re.IGNORECASE),
        re.compile(r'^item$', re.IGNORECASE),
        re.compile(r'^things$', re.IGNORECASE),
        re.compile(r'^stuff$', re.IGNORECASE),
    ]
    
    # 常量命名模式：全大写下划线
    CONSTANT_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
    
    # 临时变量模式：下划线开头、或带有temp/tmp
    TEMPORARY_PATTERNS = [
        re.compile(r'^_', re.IGNORECASE),
        re.compile(r'temp', re.IGNORECASE),
        re.compile(r'tmp', re.IGNORECASE),
    ]
    
    # 状态变量模式：is_/has_/can_/should_
    STATE_PATTERNS = [
        re.compile(r'^is_', re.IGNORECASE),
        re.compile(r'^has_', re.IGNORECASE),
        re.compile(r'^can_', re.IGNORECASE),
        re.compile(r'^should_', re.IGNORECASE),
        re.compile(r'^needs_', re.IGNORECASE),
        re.compile(r'^will_', re.IGNORECASE),
        re.compile(r'^status', re.IGNORECASE),
        re.compile(r'_state$', re.IGNORECASE),
        re.compile(r'_status$', re.IGNORECASE),
        re.compile(r'_flag$', re.IGNORECASE),
    ]
    
    def __init__(self):
        self.variables: List[VariableInfo] = []
        self.assigned_names: Set[str] = set()
        self.modified_names: Set[str] = set()
        self.current_function_vars: Set[str] = set()
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """处理函数定义"""
        self.current_function_vars = set()
        for arg in node.args.args:
            self._add_variable(arg.arg, node.lineno, node.col_offset, is_assigned=True)
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """处理赋值语句"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add_variable(target.id, node.lineno, node.col_offset, is_assigned=True)
                if target.id in self.assigned_names:
                    self.modified_names.add(target.id)
        self.generic_visit(node)
    
    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """处理增量赋值语句（+=, -=等）"""
        if isinstance(node.target, ast.Name):
            self._add_variable(node.target.id, node.lineno, node.col_offset, is_assigned=True)
            self.modified_names.add(node.target.id)
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """处理名称引用"""
        if isinstance(node.ctx, ast.Store):
            self._add_variable(node.id, node.lineno, node.col_offset, is_assigned=True)
            if node.id in self.assigned_names:
                self.modified_names.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            if node.id not in self.assigned_names:
                self._add_variable(node.id, node.lineno, node.col_offset, is_assigned=False)
    
    def _add_variable(self, name: str, line: int, col: int, is_assigned: bool) -> None:
        """添加变量信息"""
        if name.startswith('__'):  # 跳过魔术方法和私有属性
            return
        
        category = self._classify_variable(name, is_assigned)
        issues = self._check_issues(name, category)
        
        var_info = VariableInfo(
            name=name,
            category=category,
            line=line,
            column=col,
            is_assigned=is_assigned,
            is_modified=name in self.modified_names,
            issues=issues,
            suggestion=self._generate_suggestion(name, category, issues)
        )
        self.variables.append(var_info)
        
        if is_assigned:
            self.assigned_names.add(name)
    
    def _classify_variable(self, name: str, is_assigned: bool) -> VariableCategory:
        """分类变量"""
        # 检查常量模式（全大写）
        if self.CONSTANT_PATTERN.match(name):
            return VariableCategory.CONSTANT
        
        # 检查状态模式
        for pattern in self.STATE_PATTERNS:
            if pattern.search(name):
                return VariableCategory.STATE
        
        # 检查临时变量模式
        for pattern in self.TEMPORARY_PATTERNS:
            if pattern.search(name):
                return VariableCategory.TEMPORARY
        
        return VariableCategory.UNKNOWN
    
    def _check_issues(self, name: str, category: VariableCategory) -> List[Tuple[VariableIssueType, str]]:
        """检查变量问题"""
        issues: List[Tuple[VariableIssueType, str]] = []
        
        # 检测模糊命名
        for pattern in self.VAGUE_PATTERNS:
            if pattern.match(name):
                issues.append((VariableIssueType.VAGUE_NAMING, f'命名过于模糊: {name}'))
                break
        
        # 检测命名违规
        if category == VariableCategory.CONSTANT and not self.CONSTANT_PATTERN.match(name):
            issues.append((VariableIssueType.NAMING_VIOLATION, f'常量应使用全大写下划线: {name}'))
        elif category == VariableCategory.UNKNOWN and not any(p.search(name) for p in self.STATE_PATTERNS):
            issues.append((VariableIssueType.NAMING_VIOLATION, f'变量命名不符合规范: {name}'))
        
        return issues
    
    def _generate_suggestion(self, name: str, category: VariableCategory, issues: List[Tuple[VariableIssueType, str]]) -> Optional[str]:
        """生成修正建议"""
        if not issues:
            return None
        
        if category == VariableCategory.CONSTANT:
            return name.upper().replace('-', '_')
        
        return None
    
    def get_result(self) -> ScanResult:
        """获取扫描结果"""
        total_count = len(self.variables)
        issue_count = sum(1 for var in self.variables if var.issues)
        return ScanResult(
            variables=self.variables,
            total_count=total_count,
            issue_count=issue_count
        )
    
    def scan_file(self, file_path: str) -> ScanResult:
        """扫描单个文件（类方法）"""
        self.variables = []
        self.assigned_names = set()
        self.modified_names = set()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
            self.visit(tree)
        except Exception as e:
            logger.error(f"扫描文件 {file_path} 失败: {e}")
        return self.get_result()


def scan_file(file_path: str) -> ScanResult:
    """扫描单个文件"""
    scanner = VariableAtomScanner()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        scanner.visit(tree)
    except Exception as e:
        logger.error(f"扫描文件 {file_path} 失败: {e}")
    return scanner.get_result()


def scan_directory(directory: str) -> Dict[str, ScanResult]:
    """扫描整个目录"""
    results: Dict[str, ScanResult] = {}
    for file in Path(directory).rglob('*.py'):
        results[str(file)] = scan_file(str(file))
    return results


def demo_scanner():
    """演示扫描器"""
    print("=" * 70)
    print("变量原子化扫描器演示")
    print("=" * 70)
    print()
    
    # 创建测试用Python代码
    test_code = '''
# 常量示例
MAX_SIZE = 100
DEBUG_MODE = True

# 状态变量示例
is_running = False
has_error = False
should_continue = True

# 临时变量示例
_temp = 0
tmp_value = []

# 模糊命名示例
data = {}
result = 0
x = 10
y = 20
obj = object()

# 普通变量示例
user_id = 123
user_name = "test"
'''
    
    # 保存到临时文件
    temp_file = Path('/tmp/test_atomic_var.py')
    temp_file.write_text(test_code, encoding='utf-8')
    
    print(f"测试文件内容:")
    print(test_code)
    print("-" * 70)
    
    # 扫描文件
    result = scan_file(str(temp_file))
    
    print(f"扫描结果:")
    print(f"总变量数: {result.total_count}")
    print(f"有问题的变量数: {result.issue_count}")
    print()
    
    for var in result.variables:
        print(f"{var.name} (行 {var.line}, 列 {var.column}):")
        print(f"  类别: {var.category.value}")
        print(f"  是否被赋值: {'是' if var.is_assigned else '否'}")
        print(f"  是否被修改: {'是' if var.is_modified else '否'}")
        if var.issues:
            print(f"  问题:")
            for issue_type, msg in var.issues:
                print(f"    - {issue_type.value}: {msg}")
            if var.suggestion:
                print(f"  建议: {var.suggestion}")
        print()
    
    print("=" * 70)


# 标准化修正功能
class VariableStandardizer:
    """变量标准化修正器"""
    
    def __init__(self):
        self.fixes: List[Dict[str, Any]] = []
    
    def standardize_name(self, name: str, category: VariableCategory) -> str:
        """标准化变量名"""
        if category == VariableCategory.CONSTANT:
            # 常量标准化为全大写下划线
            name = re.sub(r'[A-Z]', lambda m: '_' + m.group(0).lower(), name)
            name = name.upper().replace('__', '_').strip('_')
            if not name:
                name = 'CONSTANT'
            return name
        elif category in [VariableCategory.STATE, VariableCategory.TEMPORARY, VariableCategory.UNKNOWN]:
            # 变量标准化为小写下划线
            name = re.sub(r'[A-Z]', lambda m: '_' + m.group(0).lower(), name)
            name = name.lower().replace('__', '_').strip('_')
            if not name:
                name = 'var'
            return name
        return name
    
    def fix_variable(self, var_info: VariableInfo, file_source: str) -> Tuple[str, bool]:
        """修正变量"""
        if not var_info.issues:
            return file_source, False
        
        old_name = var_info.name
        new_name = self.standardize_name(old_name, var_info.category)
        
        if new_name != old_name:
            # 简单替换（实际项目中需要更精确的语法树操作）
            # 使用边界匹配来只替换整个变量名
            source = file_source
            # 替换
            import re
            source = re.sub(r'\b' + re.escape(old_name) + r'\b', new_name, source)
            self.fixes.append({
                'old': old_name,
                'new': new_name,
                'line': var_info.line,
                'category': var_info.category.value
            })
            return source, True
        return file_source, False


# 单一语义原子约束验证
class SingleSemanticValidator:
    """单一语义验证器"""
    
    def __init__(self):
        self.violations: List[Tuple[str, int, str]] = []
    
    def validate(self, variables: List[VariableInfo]) -> List[Tuple[str, int, str]]:
        """验证单一语义约束"""
        # 统计变量修改次数，识别被用于多种用途的变量
        usage_count = {}
        for var in variables:
            if var.name not in usage_count:
                usage_count[var.name] = {'assign': 0, 'load': 0}
            if var.is_assigned:
                usage_count[var.name]['assign'] += 1
            else:
                usage_count[var.name]['load'] += 1
        
        violations = []
        for name, counts in usage_count.items():
            # 被频繁重新赋值可能意味着多语义使用
            if counts['assign'] > 3:
                violations.append((name, 0, f"变量被频繁重新赋值({counts['assign']}次)，可能存在多语义问题"))
        
        self.violations.extend(violations)
        return violations


# 完整的自动化修复
def auto_fix_file(file_path: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """自动修复文件"""
    result = scan_file(file_path)
    standardizer = VariableStandardizer()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    modified = False
    for var in result.variables:
        if var.issues:
            source, fixed = standardizer.fix_variable(var, source)
            if fixed:
                modified = True
    
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(source)
    
    return modified, standardizer.fixes


def demo_full_functionality():
    """演示完整功能"""
    print("=" * 70)
    print("完整功能演示")
    print("=" * 70)
    print()
    
    # 测试文件
    test_code = '''
# 命名不规范的代码
maxSize = 100
debug_mode = True
IsRunning = False
hasError = False

# 模糊命名
data = []
result = None

# 多赋值问题
temp = 0
temp = 1
temp = 2
temp = 3
temp = 4
'''
    
    temp_file = Path('/tmp/test_full_atomic.py')
    temp_file.write_text(test_code, encoding='utf-8')
    
    # 扫描
    result = scan_file(str(temp_file))
    print("扫描结果：")
    print(f"总变量数: {result.total_count}")
    print(f"有问题的变量数: {result.issue_count}")
    print()
    
    for var in result.variables:
        print(f"{var.name}: {var.category.value}")
        if var.issues:
            for issue_type, msg in var.issues:
                print(f"  - {issue_type.value}: {msg}")
            if var.suggestion:
                print(f"  -> 建议: {var.suggestion}")
    print()
    
    # 单一语义验证
    validator = SingleSemanticValidator()
    violations = validator.validate(result.variables)
    if violations:
        print("单一语义约束违反：")
        for name, line, msg in violations:
            print(f"  - {name}: {msg}")
        print()
    
    # 标准化演示
    print("标准化修正示例：")
    standardizer = VariableStandardizer()
    for var in result.variables:
        if var.issues:
            new_name = standardizer.standardize_name(var.name, var.category)
            if new_name != var.name:
                print(f"  {var.name} -> {new_name}")
    print()
    
    print("=" * 70)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'full':
        demo_full_functionality()
    else:
        demo_scanner()

