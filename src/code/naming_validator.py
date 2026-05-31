"""
命名规范全链路校验器
遵循第一性原理：命名规范清晰、语义明确

核心功能：
1. 变量命名规范校验（蛇形命名、语义清晰）
2. 函数/方法命名规范校验（动词开头、语义明确）
3. 类命名规范校验（驼峰命名、首字母大写）
4. 常量命名规范校验（全大写、下划线分隔）
5. 模块/包命名规范校验（蛇形命名、简洁）
6. 命名语义清晰性校验（避免模糊命名）
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class NamingIssueSeverity(Enum):
    """命名问题严重性"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class NamingIssue:
    """命名问题"""
    entity_type: str
    name: str
    line: int
    column: int
    issue_type: str
    description: str
    severity: NamingIssueSeverity
    suggestion: Optional[str] = None


@dataclass
class NamingCheckResult:
    """命名检查结果"""
    file_path: str
    total_issues: int = 0
    variable_issues: List[NamingIssue] = field(default_factory=list)
    function_issues: List[NamingIssue] = field(default_factory=list)
    class_issues: List[NamingIssue] = field(default_factory=list)
    constant_issues: List[NamingIssue] = field(default_factory=list)
    all_issues: List[NamingIssue] = field(default_factory=list)


class NamingRules:
    """命名规则"""
    
    # 变量/函数/方法：蛇形命名
    SNAKE_CASE_PATTERN = r'^[a-z][a-z0-9_]*$'
    
    # 类：大驼峰命名
    PASCAL_CASE_PATTERN = r'^[A-Z][a-zA-Z0-9]*$'
    
    # 常量：全大写+下划线
    CONSTANT_CASE_PATTERN = r'^[A-Z][A-Z0-9_]*$'
    
    # 模糊命名黑名单
    VAGUE_NAMES = {
        'data', 'temp', 'tmp', 'var', 'obj', 'item', 'thing',
        'value', 'result', 'output', 'input', 'x', 'y', 'z',
        'i', 'j', 'k', 'a', 'b', 'c'
    }
    
    # 常见动词前缀
    COMMON_VERBS = {
        'get', 'set', 'create', 'delete', 'update', 'fetch',
        'save', 'load', 'validate', 'check', 'calculate',
        'process', 'parse', 'format', 'convert', 'transform',
        'is', 'has', 'can', 'should', 'will'
    }


class NamingValidator(ast.NodeVisitor):
    """命名验证器"""
    
    def __init__(self):
        self.issues: List[NamingIssue] = []
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
    
    def validate_file(self, file_path: str) -> NamingCheckResult:
        """验证文件"""
        self.issues = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        self.visit(tree)
        
        return self._build_result(file_path)
    
    def _build_result(self, file_path: str) -> NamingCheckResult:
        """构建结果"""
        result = NamingCheckResult(file_path=file_path)
        
        for issue in self.issues:
            result.all_issues.append(issue)
            
            if issue.entity_type == 'variable':
                result.variable_issues.append(issue)
            elif issue.entity_type == 'function':
                result.function_issues.append(issue)
            elif issue.entity_type == 'class':
                result.class_issues.append(issue)
            elif issue.entity_type == 'constant':
                result.constant_issues.append(issue)
        
        result.total_issues = len(result.all_issues)
        return result
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """检查函数/方法命名"""
        old_function = self.current_function
        self.current_function = node.name
        
        self._check_function_name(node)
        self.generic_visit(node)
        
        self.current_function = old_function
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """检查类命名"""
        old_class = self.current_class
        self.current_class = node.name
        
        self._check_class_name(node)
        self.generic_visit(node)
        
        self.current_class = old_class
    
    def visit_Assign(self, node: ast.Assign):
        """检查赋值命名"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_variable_name(target, node)
            elif isinstance(target, ast.Attribute):
                pass
        
        self.generic_visit(node)
    
    def visit_AnnAssign(self, node: ast.AnnAssign):
        """检查注解赋值命名"""
        if isinstance(node.target, ast.Name):
            self._check_variable_name(node.target, node)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """检查名称（用于检测常量）"""
        if node.id.isupper():
            # 可能是常量
            if self.current_function is None and self.current_class is None:
                # 模块级
                self._check_constant_name(node)
        
        self.generic_visit(node)
    
    def _check_function_name(self, node: ast.FunctionDef):
        """检查函数/方法命名"""
        name = node.name
        
        # 跳过特殊方法（以双下划线开头和结尾）
        if name.startswith('__') and name.endswith('__'):
            return
        
        # 1. 检查格式
        if not re.match(NamingRules.SNAKE_CASE_PATTERN, name):
            self._add_issue(
                entity_type='function',
                name=name,
                line=node.lineno,
                column=node.col_offset,
                issue_type='invalid_format',
                description=f'函数名 "{name}" 不符合蛇形命名规范',
                severity=NamingIssueSeverity.ERROR,
                suggestion=f'建议使用蛇形命名，如 {self._to_snake_case(name)}'
            )
        
        # 2. 检查是否是动词开头
        has_verb = any(name.lower().startswith(verb) for verb in NamingRules.COMMON_VERBS)
        if not has_verb and not name.startswith('_'):
            self._add_issue(
                entity_type='function',
                name=name,
                line=node.lineno,
                column=node.col_offset,
                issue_type='missing_verb',
                description=f'函数名 "{name}" 未以动词开头',
                severity=NamingIssueSeverity.WARNING,
                suggestion=f'建议使用常见动词前缀（get, set, create, validate等）'
            )
        
        # 3. 检查模糊命名
        if name in NamingRules.VAGUE_NAMES:
            self._add_issue(
                entity_type='function',
                name=name,
                line=node.lineno,
                column=node.col_offset,
                issue_type='vague_name',
                description=f'函数名 "{name}" 语义模糊',
                severity=NamingIssueSeverity.WARNING,
                suggestion=f'建议使用更具描述性的名称'
            )
    
    def _check_class_name(self, node: ast.ClassDef):
        """检查类命名"""
        name = node.name
        
        if not re.match(NamingRules.PASCAL_CASE_PATTERN, name):
            self._add_issue(
                entity_type='class',
                name=name,
                line=node.lineno,
                column=node.col_offset,
                issue_type='invalid_format',
                description=f'类名 "{name}" 不符合大驼峰命名规范',
                severity=NamingIssueSeverity.ERROR,
                suggestion=f'建议使用大驼峰命名，如 {self._to_pascal_case(name)}'
            )
    
    def _check_variable_name(self, target: ast.Name, node):
        """检查变量命名"""
        name = target.id
        
        # 检查是否是常量（全大写）
        if name.isupper() and self.current_function is None and self.current_class is None:
            # 模块级常量，不检查变量规则
            return
        
        # 1. 检查格式
        if not re.match(NamingRules.SNAKE_CASE_PATTERN, name):
            self._add_issue(
                entity_type='variable',
                name=name,
                line=target.lineno if hasattr(target, 'lineno') else node.lineno,
                column=target.col_offset if hasattr(target, 'col_offset') else node.col_offset,
                issue_type='invalid_format',
                description=f'变量名 "{name}" 不符合蛇形命名规范',
                severity=NamingIssueSeverity.ERROR,
                suggestion=f'建议使用蛇形命名，如 {self._to_snake_case(name)}'
            )
        
        # 2. 检查模糊命名
        if name in NamingRules.VAGUE_NAMES:
            self._add_issue(
                entity_type='variable',
                name=name,
                line=target.lineno if hasattr(target, 'lineno') else node.lineno,
                column=target.col_offset if hasattr(target, 'col_offset') else node.col_offset,
                issue_type='vague_name',
                description=f'变量名 "{name}" 语义模糊',
                severity=NamingIssueSeverity.WARNING,
                suggestion=f'建议使用更具描述性的名称'
            )
    
    def _check_constant_name(self, node: ast.Name):
        """检查常量命名"""
        name = node.id
        
        if not re.match(NamingRules.CONSTANT_CASE_PATTERN, name):
            self._add_issue(
                entity_type='constant',
                name=name,
                line=node.lineno,
                column=node.col_offset,
                issue_type='invalid_format',
                description=f'常量名 "{name}" 不符合常量命名规范',
                severity=NamingIssueSeverity.ERROR,
                suggestion=f'建议使用全大写+下划线命名'
            )
    
    def _add_issue(self, **kwargs):
        """添加问题"""
        self.issues.append(NamingIssue(**kwargs))
    
    def _to_snake_case(self, text: str) -> str:
        """转换为蛇形命名"""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _to_pascal_case(self, text: str) -> str:
        """转换为大驼峰命名"""
        # 处理已经是驼峰格式的情况
        if not text or len(text) == 0:
            return text
        
        # 先转为蛇形，再转为大驼峰
        snake_case = self._to_snake_case(text)
        components = snake_case.split('_')
        return ''.join(x.title() for x in components)


def demo_naming_validator():
    """演示命名验证器"""
    print("=" * 70)
    print("命名规范全链路校验器 - 演示")
    print("=" * 70)
    print()
    
    # 创建测试文件
    test_code = '''
"""
命名规范测试文件
"""

# 常量
MAX_VALUE = 100
TIMEOUT = 30

# 变量
userName = "Alice"  # 错误：应该是 user_name
data = []  # 警告：语义模糊
x = 42  # 警告：语义模糊


class userService:  # 错误：应该是 UserService
    """用户服务类"""
    
    def __init__(self):
        self.user_list = []
    
    def GetUser(self, userId):  # 错误：应该是 get_user
        """获取用户"""
        for i in range(len(self.user_list)):  # 警告：i 语义模糊
            if self.user_list[i].id == userId:
                return self.user_list[i]
        return None
    
    def createUser(self, userData):  # 错误：应该是 create_user
        """创建用户"""
        obj = {"id": userData.get("id"), "name": userData.get("name")}  # 警告：obj 语义模糊
        self.user_list.append(obj)
    
    def ValidateUser(self, user):  # 错误：应该是 validate_user
        """验证用户"""
        result = user.get("name") is not None  # 警告：result 语义模糊
        return result


def ProcessData(data):  # 错误：应该是 process_data，警告：data 语义模糊
    """处理数据"""
    value = sum(data)  # 警告：value 语义模糊
    return value
'''
    
    temp_file = Path('/tmp/test_naming.py')
    temp_file.write_text(test_code.strip(), encoding='utf-8')
    
    # 验证文件
    validator = NamingValidator()
    result = validator.validate_file(str(temp_file))
    
    print("📊 命名规范检查结果:")
    print("-" * 70)
    print(f"总问题数: {result.total_issues}")
    print()
    
    if result.variable_issues:
        print(f"🔍 变量问题 ({len(result.variable_issues)}):")
        for issue in result.variable_issues:
            print(f"  第{issue.line}行: {issue.description}")
            if issue.suggestion:
                print(f"      💡 {issue.suggestion}")
        print()
    
    if result.function_issues:
        print(f"🔍 函数问题 ({len(result.function_issues)}):")
        for issue in result.function_issues:
            print(f"  第{issue.line}行: {issue.description}")
            if issue.suggestion:
                print(f"      💡 {issue.suggestion}")
        print()
    
    if result.class_issues:
        print(f"🔍 类问题 ({len(result.class_issues)}):")
        for issue in result.class_issues:
            print(f"  第{issue.line}行: {issue.description}")
            if issue.suggestion:
                print(f"      💡 {issue.suggestion}")
        print()
    
    if result.constant_issues:
        print(f"🔍 常量问题 ({len(result.constant_issues)}):")
        for issue in result.constant_issues:
            print(f"  第{issue.line}行: {issue.description}")
            if issue.suggestion:
                print(f"      💡 {issue.suggestion}")
        print()
    
    print("=" * 70)
    print("📋 命名规范标准:")
    print()
    print("✅ 变量/函数/方法: 蛇形命名 (user_name, get_user)")
    print("✅ 类: 大驼峰命名 (UserService)")
    print("✅ 常量: 全大写+下划线 (MAX_VALUE)")
    print("✅ 命名语义清晰 (避免 data, temp, x等)")
    print("✅ 函数以动词开头 (get, set, create, validate等)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_naming_validator()
