"""
方法原子化扫描器
遵循第一性原理：单一职责原则

核心功能：
1. 检测多职责混杂方法
2. 检测超大方法
3. 方法单一职责验证
4. 方法行数和结构规范检查
"""

import ast
import re
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class MethodIssueType(Enum):
    """方法问题类型"""
    TOO_LONG = "too_long"
    TOO_MANY_PARAMS = "too_many_params"
    TOO_MANY_RESPONSIBILITIES = "too_many_responsibilities"
    MISSING_DOCSTRING = "missing_docstring"
    POOR_NAMING = "poor_naming"
    MULTIPLE_RETURN_VALUES = "multiple_return_values"


@dataclass
class MethodInfo:
    """方法信息"""
    name: str
    line: int
    column: int
    lines_count: int
    params_count: int
    has_docstring: bool
    issues: List[Tuple[MethodIssueType, str]] = field(default_factory=list)
    suggestion: Optional[str] = None


@dataclass
class MethodScanResult:
    """方法扫描结果"""
    methods: List[MethodInfo] = field(default_factory=list)
    total_methods: int = 0
    issue_methods: int = 0


class MethodAtomScanner(ast.NodeVisitor):
    """方法原子化扫描器"""
    
    # 原子方法规范
    MAX_METHOD_LINES = 30
    MAX_PARAMS = 5
    
    # 常见的多职责关键词
    RESPONSIBILITY_KEYWORDS = [
        "and", "or", "if", "else", "elif", "for", "while", 
        "try", "except", "finally", "with"
    ]
    
    def __init__(self):
        self.methods: List[MethodInfo] = []
        self.source_lines: List[str] = []
    
    def scan(self, file_path: str) -> MethodScanResult:
        """扫描文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            self.source_lines = f.read().split('\n')
            source = '\n'.join(self.source_lines)
        
        tree = ast.parse(source)
        self.visit(tree)
        
        return MethodScanResult(
            methods=self.methods,
            total_methods=len(self.methods),
            issue_methods=sum(1 for m in self.methods if m.issues)
        )
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """处理函数定义"""
        method_info = self._analyze_method(node)
        self.methods.append(method_info)
        self.generic_visit(node)
    
    def _analyze_method(self, node: ast.FunctionDef) -> MethodInfo:
        """分析方法"""
        # 计算方法行数
        start_line = node.lineno
        end_line = self._find_function_end(node)
        lines_count = end_line - start_line + 1 if end_line else 1
        
        # 统计参数数量
        params_count = len(node.args.args) + len(node.args.kwonlyargs)
        
        # 检查是否有文档字符串
        has_docstring = ast.get_docstring(node) is not None
        
        issues = []
        
        # 检查方法长度
        if lines_count > self.MAX_METHOD_LINES:
            issues.append((
                MethodIssueType.TOO_LONG,
                f"方法行数过长({lines_count}行)，建议少于{self.MAX_METHOD_LINES}行"
            ))
        
        # 检查参数数量
        if params_count > self.MAX_PARAMS:
            issues.append((
                MethodIssueType.TOO_MANY_PARAMS,
                f"方法参数过多({params_count}个)，建议少于{self.MAX_PARAMS}个"
            ))
        
        # 检查文档字符串
        if not has_docstring:
            issues.append((
                MethodIssueType.MISSING_DOCSTRING,
                "缺少方法文档字符串"
            ))
        
        # 分析方法复杂度和多职责
        complexity_score = self._calculate_complexity(node)
        if complexity_score > 10:
            issues.append((
                MethodIssueType.TOO_MANY_RESPONSIBILITIES,
                f"方法复杂度过高(复杂度{complexity_score})，可能承担了多个职责"
            ))
        
        # 检查方法命名
        if not self._is_good_method_name(node.name):
            issues.append((
                MethodIssueType.POOR_NAMING,
                f"方法命名不规范: {node.name}"
            ))
        
        return MethodInfo(
            name=node.name,
            line=node.lineno,
            column=node.col_offset,
            lines_count=lines_count,
            params_count=params_count,
            has_docstring=has_docstring,
            issues=issues,
            suggestion=self._generate_suggestion(issues)
        )
    
    def _find_function_end(self, node: ast.FunctionDef) -> Optional[int]:
        """找到函数结束位置"""
        end_line = node.lineno
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                if child.lineno > end_line:
                    end_line = child.lineno
        return end_line
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算方法复杂度（简化版）"""
        complexity = 1
        
        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.complexity = 1
            
            def visit_If(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_For(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_While(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_With(self, node):
                self.complexity += 1
                self.generic_visit(node)
            
            def visit_Try(self, node):
                self.complexity += 1
                self.generic_visit(node)
        
        visitor = ComplexityVisitor()
        visitor.visit(node)
        return visitor.complexity
    
    def _is_good_method_name(self, name: str) -> bool:
        """检查方法命名"""
        # 方法名应该是动词开头
        verbs = [
            "get", "set", "update", "delete", "create", "save", "load", 
            "process", "handle", "validate", "check", "find", "search",
            "calculate", "compute", "format", "parse", "convert", "transform"
        ]
        
        for verb in verbs:
            if name.lower().startswith(verb):
                return True
        
        # 如果不是动词开头，至少要符合小写下划线命名
        return bool(re.match(r'^[a-z][a-z0-9_]*$', name))
    
    def _generate_suggestion(self, issues: List[Tuple[MethodIssueType, str]]) -> Optional[str]:
        """生成改进建议"""
        if not issues:
            return None
        
        suggestions = []
        for issue_type, _ in issues:
            if issue_type == MethodIssueType.TOO_LONG:
                suggestions.append("考虑将方法拆分为更小的单一职责方法")
            elif issue_type == MethodIssueType.TOO_MANY_PARAMS:
                suggestions.append("考虑使用数据类或字典减少参数数量")
            elif issue_type == MethodIssueType.TOO_MANY_RESPONSIBILITIES:
                suggestions.append("按照单一职责原则拆分方法")
        
        return ' '.join(suggestions) if suggestions else None


class MethodSplitter:
    """方法拆分器"""
    
    def __init__(self):
        self.suggestions: List[Dict[str, Any]] = []
    
    def suggest_splits(self, method_info: MethodInfo, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """建议方法拆分点"""
        suggestions = []
        
        # 根据代码段进行分析
        if hasattr(node, 'body'):
            body_length = len(node.body)
            
            # 如果代码过长，找出可能的拆分点
            if body_length > 10:
                # 识别逻辑块边界
                for i in range(len(node.body) - 1):
                    stmt = node.body[i]
                    next_stmt = node.body[i + 1]
                    
                    # 遇到注释或空行可能是一个逻辑边界
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                        continue
                    
                    # 遇到新的 if/for/while 块
                    if isinstance(next_stmt, (ast.If, ast.For, ast.While)):
                        suggestions.append({
                            'type': 'split',
                            'line': stmt.lineno + 1 if hasattr(stmt, 'lineno') else 0,
                            'suggestion': '考虑在此处拆分方法'
                        })
        
        return suggestions


# 扫描和分析函数
def scan_methods(file_path: str) -> MethodScanResult:
    """扫描文件中的方法"""
    scanner = MethodAtomScanner()
    return scanner.scan(file_path)


def scan_directory_for_methods(directory: str) -> Dict[str, MethodScanResult]:
    """扫描整个目录的方法"""
    results: Dict[str, MethodScanResult] = {}
    for file in Path(directory).rglob('*.py'):
        results[str(file)] = scan_methods(str(file))
    return results


def demo_method_scanner():
    """演示方法扫描器"""
    print("=" * 70)
    print("方法原子化扫描器演示")
    print("=" * 70)
    print()
    
    # 创建测试文件
    test_code = '''
def process_user_data(name, age, email, address, phone, status):
    """处理用户数据 - 一个多职责方法的例子"""
    # 这个方法太长，职责太多
    if not name:
        raise ValueError("Name is required")
    if not age or age <= 0:
        raise ValueError("Age is invalid")
    if not email:
        raise ValueError("Email is required")
    
    user_data = {
        'name': name,
        'age': age,
        'email': email,
        'address': address,
        'phone': phone,
        'status': status
    }
    
    if status == 'active':
        send_welcome_email(email)
        log_activity(user_data)
    elif status == 'pending':
        send_verification_email(email)
        log_activity(user_data)
    
    if age > 18:
        apply_discount(user_data)
    
    if address:
        validate_address(address)
    
    save_to_database(user_data)
    cache_user_data(user_data)
    
    return user_data


def send_welcome_email(email):
    """发送欢迎邮件"""
    print(f"Sending welcome email to {email}")


def log_activity(data):
    """记录活动"""
    print(f"Logging activity for {data}")


def send_verification_email(email):
    """发送验证邮件"""
    print(f"Sending verification email to {email}")


def apply_discount(data):
    """应用折扣"""
    print(f"Applying discount to {data}")


def validate_address(address):
    """验证地址"""
    print(f"Validating address: {address}")


def save_to_database(data):
    """保存到数据库"""
    print(f"Saving to database: {data}")


def cache_user_data(data):
    """缓存用户数据"""
    print(f"Caching user data: {data}")
'''
    
    temp_file = Path('/tmp/test_method_atomic.py')
    temp_file.write_text(test_code, encoding='utf-8')
    
    # 扫描文件
    result = scan_methods(str(temp_file))
    
    print(f"扫描结果:")
    print(f"总方法数: {result.total_methods}")
    print(f"有问题的方法数: {result.issue_methods}")
    print()
    
    for method in result.methods:
        print(f"{method.name} (行 {method.line}):")
        print(f"  行数: {method.lines_count}")
        print(f"  参数数: {method.params_count}")
        print(f"  有文档字符串: {'是' if method.has_docstring else '否'}")
        if method.issues:
            print(f"  问题:")
            for issue_type, msg in method.issues:
                print(f"    - {issue_type.value}: {msg}")
            if method.suggestion:
                print(f"  建议: {method.suggestion}")
        print()
    
    print("=" * 70)
    print()
    print("📋 方法原子规范:")
    print(f"  - 方法行数 ≤ {MethodAtomScanner.MAX_METHOD_LINES}")
    print(f"  - 参数数 ≤ {MethodAtomScanner.MAX_PARAMS}")
    print(f"  - 有文档字符串")
    print(f"  - 单一职责")
    print(f"  - 规范的命名（动词开头）")
    print("=" * 70)





class MethodSplitter:
    """方法拆分建议器"""
    
    def analyze_and_suggest(self, file_path: str):
        """分析并提供方法拆分建议"""
        scanner = MethodAtomScanner()
        result = scanner.scan(file_path)
        
        split_suggestions = []
        
        for method_info in result.methods:
            if method_info.issues:
                suggestions = self._generate_split_suggestions(method_info)
                if suggestions:
                    split_suggestions.extend(suggestions)
        
        return split_suggestions
    
    def _generate_split_suggestions(self, method_info: MethodInfo):
        """生成拆分建议"""
        suggestions = []
        
        for issue_type, msg in method_info.issues:
            if issue_type == MethodIssueType.TOO_LONG:
                suggestions.append({
                    'method': method_info.name,
                    'type': 'split_by_functionality',
                    'description': f"方法 '{method_info.name}' 过长，建议按功能拆分为多个小方法",
                    'example': self._example_split_methods(method_info.name)
                })
            
            if issue_type == MethodIssueType.TOO_MANY_PARAMS:
                suggestions.append({
                    'method': method_info.name,
                    'type': 'extract_data_class',
                    'description': f"方法 '{method_info.name}' 参数过多，建议将相关参数封装为数据类",
                    'example': self._example_data_class()
                })
            
            if issue_type == MethodIssueType.TOO_MANY_RESPONSIBILITIES:
                suggestions.append({
                    'method': method_info.name,
                    'type': 'extract_single_responsibility',
                    'description': f"方法 '{method_info.name}' 可能承担多个职责，建议拆分为单一职责的小方法"
                })
        
        return suggestions
    
    def _example_split_methods(self, original_name):
        """生成拆分方法的示例"""
        return f'''
例如，将 '{original_name}' 拆分为:
- validate_input(): 负责参数验证
- prepare_data(): 负责数据准备
- process_active_user(): 处理活跃用户
- process_pending_user(): 处理待处理用户
- save_and_cache_data(): 保存和缓存数据
'''
    
    def _example_data_class(self):
        """生成数据类的示例"""
        return '''
例如，使用 dataclass 封装参数:
@dataclass
class UserData:
    name: str
    age: int
    email: str
    address: Optional[str]
    phone: Optional[str]
    status: str
'''


def demo_full_functionality():
    """演示完整功能"""
    print("=" * 70)
    print("方法原子化 - 完整功能演示")
    print("=" * 70)
    print()
    
    # 测试文件
    test_code = '''
def process_user_data(name, age, email, address, phone, status):
    """处理用户数据 - 一个多职责方法的例子"""
    # 这个方法太长，职责太多
    if not name:
        raise ValueError("Name is required")
    if not age or age <= 0:
        raise ValueError("Age is invalid")
    if not email:
        raise ValueError("Email is required")
    
    user_data = {
        'name': name,
        'age': age,
        'email': email,
        'address': address,
        'phone': phone,
        'status': status
    }
    
    if status == 'active':
        send_welcome_email(email)
        log_activity(user_data)
    elif status == 'pending':
        send_verification_email(email)
        log_activity(user_data)
    
    if age > 18:
        apply_discount(user_data)
    
    if address:
        validate_address(address)
    
    save_to_database(user_data)
    cache_user_data(user_data)
    
    return user_data
'''
    
    temp_file = Path('/tmp/test_method_atomic_full.py')
    temp_file.write_text(test_code, encoding='utf-8')
    
    # 扫描
    result = scan_methods(str(temp_file))
    
    print("📊 扫描结果:")
    print(f"总方法数: {result.total_methods}")
    print(f"有问题的方法数: {result.issue_methods}")
    print()
    
    # 展示问题方法
    for method in result.methods:
        if method.issues:
            print(f"🔴 {method.name}:")
            for issue_type, msg in method.issues:
                print(f"   - {issue_type.value}: {msg}")
            if method.suggestion:
                print(f"   💡 {method.suggestion}")
    
    print()
    print("=" * 70)
    print("📝 拆分建议:")
    splitter = MethodSplitter()
    suggestions = splitter.analyze_and_suggest(str(temp_file))
    
    for s in suggestions:
        print(f"🔧 {s['description']}")
        if 'example' in s:
            print(f"   示例: {s['example']}")
    
    print()
    print("=" * 70)
    print("✅ 方法原子规范总结:")
    print()
    print("📏 方法行数: ≤ 30 行")
    print("📦 参数数量: ≤ 5 个")
    print("📄 文档字符串: 必须包含")
    print("🎯 单一职责: 每个方法只做一件事")
    print("📛 命名规范: 动词开头，小写下划线")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'full':
        demo_full_functionality()
    else:
        demo_method_scanner()

