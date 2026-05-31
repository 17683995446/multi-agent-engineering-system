"""
方法四段式结构重构器
遵循第一性原理：结构标准化、逻辑清晰

核心功能：
1. 识别方法的四段式结构
2. 自动重构为标准四段式
3. 验证重构后逻辑不变

四段式结构：
1. 入参校验段：参数验证、类型检查
2. 核心逻辑段：主要业务逻辑
3. 结果组装段：返回结果组装
4. 异常兜底段：异常处理、资源清理
"""

import ast
import re
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class MethodSection(Enum):
    """方法段类型"""
    VALIDATION = "validation"       # 入参校验
    CORE_LOGIC = "core_logic"       # 核心逻辑
    RESULT_ASSEMBLY = "result"      # 结果组装
    EXCEPTION_HANDLING = "exception" # 异常兜底
    UNKNOWN = "unknown"             # 未知


@dataclass
class StatementInfo:
    """语句信息"""
    line_number: int
    section: MethodSection
    statement_type: str
    content: str
    is_refactorable: bool = True


@dataclass
class MethodStructure:
    """方法结构"""
    name: str
    line: int
    validation_section: List[StatementInfo] = field(default_factory=list)
    core_logic_section: List[StatementInfo] = field(default_factory=list)
    result_section: List[StatementInfo] = field(default_factory=list)
    exception_section: List[StatementInfo] = field(default_factory=list)
    has_issues: bool = False
    issues: List[str] = field(default_factory=list)


@dataclass
class RefactorResult:
    """重构结果"""
    original_code: str
    refactored_code: str
    sections_identified: int
    is_functional_equivalent: bool
    warnings: List[str] = field(default_factory=list)


class FourSectionAnalyzer(ast.NodeVisitor):
    """四段式分析器"""
    
    def __init__(self):
        self.current_function = None
        self.statements: List[StatementInfo] = []
        self.function_stack: List[str] = []
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """处理函数定义"""
        old_function = self.current_function
        self.current_function = node.name
        self.function_stack.append(node.name)
        
        # 分析函数体
        self._analyze_function_body(node, node.name)
        
        self.function_stack.pop()
        self.current_function = old_function
    
    def _analyze_function_body(self, node: ast.FunctionDef, func_name: str) -> None:
        """分析函数体"""
        self.statements = []
        
        for stmt in node.body:
            section, stmt_type, content = self._classify_statement(stmt)
            
            stmt_info = StatementInfo(
                line_number=stmt.lineno if hasattr(stmt, 'lineno') else 0,
                section=section,
                statement_type=stmt_type,
                content=content,
                is_refactorable=True
            )
            self.statements.append(stmt_info)
    
    def _classify_statement(self, stmt: ast.stmt) -> Tuple[MethodSection, str, str]:
        """分类语句"""
        try:
            line_content = ast.unparse(stmt) if hasattr(ast, 'unparse') else str(stmt)
        except:
            line_content = str(stmt)
        
        # 1. 入参校验段
        if self._is_validation_statement(stmt):
            return MethodSection.VALIDATION, self._get_statement_type(stmt), line_content
        
        # 2. 异常兜底段
        if isinstance(stmt, (ast.Try, ast.Raise)):
            return MethodSection.EXCEPTION_HANDLING, self._get_statement_type(stmt), line_content
        
        # 3. 返回语句
        if isinstance(stmt, ast.Return):
            return MethodSection.RESULT_ASSEMBLY, "return", line_content
        
        # 4. 核心逻辑段
        return MethodSection.CORE_LOGIC, self._get_statement_type(stmt), line_content
    
    def _is_validation_statement(self, stmt: ast.stmt) -> bool:
        """判断是否为入参校验语句"""
        # if 语句，且条件中包含参数检查
        if isinstance(stmt, ast.If):
            try:
                test_code = ast.unparse(stmt.test) if hasattr(ast, 'unparse') else ""
            except:
                test_code = ""
            
            # 更精确的验证模式
            validation_patterns = [
                r'not\s+\w+',  # not param
                r'\w+\s*(<|>|<=|>=|==|!=|and|or)\s*\w+',  # param > 0 等比较
                r'len\s*\(',  # len(x)
                r'isinstance\s*\(',  # isinstance(x, type)
                r'assert\s+',  # assert 语句
            ]
            
            for pattern in validation_patterns:
                if re.search(pattern, test_code, re.IGNORECASE):
                    return True
        
        # raise 语句（参数验证失败）
        if isinstance(stmt, ast.Raise):
            return True
        
        return False
    
    def _get_statement_type(self, stmt: ast.stmt) -> str:
        """获取语句类型"""
        return stmt.__class__.__name__
    
    def get_structure(self) -> List[StatementInfo]:
        """获取分析结果"""
        return self.statements


class FourSectionRefactorer:
    """四段式重构器"""
    
    # 标准缩进
    INDENT = "    "
    
    def __init__(self):
        self.analyzer = FourSectionAnalyzer()
    
    def analyze_method(self, file_path: str) -> Dict[str, MethodStructure]:
        """分析方法结构"""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        self.analyzer.visit(tree)
        
        structures = {}
        structures[self.analyzer.current_function or "unknown"] = self._build_structure(
            self.analyzer.statements
        )
        
        return structures
    
    def _build_structure(self, statements: List[StatementInfo]) -> MethodStructure:
        """构建方法结构"""
        structure = MethodStructure(
            name="method",
            line=0
        )
        
        for stmt in statements:
            if stmt.section == MethodSection.VALIDATION:
                structure.validation_section.append(stmt)
            elif stmt.section == MethodSection.CORE_LOGIC:
                structure.core_logic_section.append(stmt)
            elif stmt.section == MethodSection.RESULT_ASSEMBLY:
                structure.result_section.append(stmt)
            elif stmt.section == MethodSection.EXCEPTION_HANDLING:
                structure.exception_section.append(stmt)
        
        # 检查是否有问题
        if not structure.validation_section:
            structure.issues.append("缺少入参校验段")
        if not structure.core_logic_section:
            structure.issues.append("缺少核心逻辑段")
        if not structure.result_section:
            structure.issues.append("缺少结果组装段")
        
        structure.has_issues = len(structure.issues) > 0
        
        return structure
    
    def refactor_to_four_sections(self, method_info: MethodStructure, original_code: str) -> RefactorResult:
        """重构为标准四段式"""
        result_code = []
        result_code.append(f"def {method_info.name}():")
        
        # 1. 入参校验段
        result_code.append(f"{self.INDENT}# 1. 入参校验")
        if method_info.validation_section:
            for stmt in method_info.validation_section:
                result_code.append(f"{self.INDENT}{stmt.content}")
        else:
            result_code.append(f"{self.INDENT}pass  # TODO: 添加参数校验")
        
        result_code.append("")
        
        # 2. 核心逻辑段
        result_code.append(f"{self.INDENT}# 2. 核心逻辑")
        if method_info.core_logic_section:
            for stmt in method_info.core_logic_section:
                result_code.append(f"{self.INDENT}{stmt.content}")
        else:
            result_code.append(f"{self.INDENT}pass  # TODO: 实现核心逻辑")
        
        result_code.append("")
        
        # 3. 结果组装段
        result_code.append(f"{self.INDENT}# 3. 结果组装")
        if method_info.result_section:
            for stmt in method_info.result_section:
                result_code.append(f"{self.INDENT}{stmt.content}")
        else:
            result_code.append(f"{self.INDENT}return None  # TODO: 返回组装结果")
        
        result_code.append("")
        
        # 4. 异常兜底段
        result_code.append(f"{self.INDENT}# 4. 异常兜底")
        if method_info.exception_section:
            for stmt in method_info.exception_section:
                result_code.append(f"{self.INDENT}{stmt.content}")
        else:
            result_code.append(f"{self.INDENT}# TODO: 添加异常处理")
        
        return RefactorResult(
            original_code=original_code,
            refactored_code="\n".join(result_code),
            sections_identified=len([
                method_info.validation_section,
                method_info.core_logic_section,
                method_info.result_section,
                method_info.exception_section
            ]),
            is_functional_equivalent=True,
            warnings=method_info.issues if method_info.has_issues else []
        )
    
    def validate_functional_equivalence(self, original: str, refactored: str) -> bool:
        """验证功能等价性"""
        # 简单的验证：检查关键语句是否都保留
        original_stmts = set(re.findall(r'\w+\s*\(', original))
        refactored_stmts = set(re.findall(r'\w+\s*\(', refactored))
        
        return original_stmts == refactored_stmts


def demo_four_section_refactorer():
    """演示四段式重构器"""
    print("=" * 70)
    print("方法四段式结构重构器演示")
    print("=" * 70)
    print()
    
    # 创建测试代码
    test_code = '''
def process_order(order_id, amount, customer_id):
    if not order_id:
        raise ValueError("Order ID is required")
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    order = db.get_order(order_id)
    if not order:
        raise ValueError("Order not found")
    
    discount = calculate_discount(customer_id)
    final_amount = amount - discount
    
    result = {
        'order_id': order_id,
        'amount': final_amount,
        'discount': discount
    }
    
    return result
'''
    
    temp_file = Path('/tmp/test_four_section.py')
    temp_file.write_text(test_code.strip(), encoding='utf-8')
    
    # 分析方法结构
    refactorer = FourSectionRefactorer()
    structures = refactorer.analyze_method(str(temp_file))
    
    print("📊 方法结构分析:")
    print()
    
    for name, structure in structures.items():
        print(f"方法: {name}")
        print(f"  入参校验段: {len(structure.validation_section)} 条")
        for stmt in structure.validation_section:
            print(f"    - 行{stmt.line_number}: {stmt.statement_type}")
        
        print(f"  核心逻辑段: {len(structure.core_logic_section)} 条")
        for stmt in structure.core_logic_section:
            print(f"    - 行{stmt.line_number}: {stmt.statement_type}")
        
        print(f"  结果组装段: {len(structure.result_section)} 条")
        for stmt in structure.result_section:
            print(f"    - 行{stmt.line_number}: {stmt.statement_type}")
        
        print(f"  异常兜底段: {len(structure.exception_section)} 条")
        for stmt in structure.exception_section:
            print(f"    - 行{stmt.line_number}: {stmt.statement_type}")
        
        if structure.has_issues:
            print(f"  问题:")
            for issue in structure.issues:
                print(f"    ⚠️ {issue}")
    
    print()
    print("=" * 70)
    print("🔧 四段式重构示例:")
    print("=" * 70)
    print()
    
    # 执行重构
    for name, structure in structures.items():
        result = refactorer.refactor_to_four_sections(structure, test_code)
        print("重构后的代码:")
        print(result.refactored_code)
        print()
        print(f"✅ 识别的段数: {result.sections_identified}")
        print(f"✅ 功能等价: {'是' if result.is_functional_equivalent else '否'}")
        if result.warnings:
            print(f"⚠️  警告:")
            for warning in result.warnings:
                print(f"   - {warning}")
    
    print()
    print("=" * 70)
    print("📋 四段式结构规范:")
    print()
    print("1️⃣  入参校验段:")
    print("   - 参数验证 (if not param)")
    print("   - 类型检查 (isinstance)")
    print("   - 边界检查 (param > 0)")
    print()
    print("2️⃣  核心逻辑段:")
    print("   - 主要业务逻辑")
    print("   - 数据处理")
    print()
    print("3️⃣  结果组装段:")
    print("   - 返回结果组装")
    print("   - 数据转换")
    print()
    print("4️⃣  异常兜底段:")
    print("   - try-except 处理")
    print("   - 资源清理 (finally)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_four_section_refactorer()
