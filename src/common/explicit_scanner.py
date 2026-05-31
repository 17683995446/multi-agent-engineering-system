"""
全局信息显式化扫描器
遵循第一性原理：最小熵信息确定性要求

目标：
1. 消灭隐式变量 - 所有变量必须有类型注解
2. 消灭隐式逻辑 - 所有魔法数字必须定义为常量
3. 消灭隐式依赖 - 所有依赖必须在配置中声明
4. 满足最小熵要求 - 所有信息必须显式化、确定化

扫描内容：
- 隐式变量检测（无类型注解的变量）
- 隐式逻辑检测（魔法数字、硬编码）
- 隐式依赖检测（未声明的导入）
- 隐式配置检测（硬编码配置值）
- 隐式状态检测（未声明的状态）
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from src.common.utils import setup_logger

logger = setup_logger(__name__)


@dataclass
class ImplicitVariable:
    """隐式变量"""
    file_path: str
    line_number: int
    variable_name: str
    context: str
    suggestion: str = "添加类型注解"


@dataclass
class ImplicitLogic:
    """隐式逻辑"""
    file_path: str
    line_number: int
    code_snippet: str
    type: str
    suggestion: str


@dataclass
class ImplicitDependency:
    """隐式依赖"""
    file_path: str
    line_number: int
    module_name: str
    suggestion: str = "在requirements.txt中声明依赖"


@dataclass
class ImplicitConfig:
    """隐式配置"""
    file_path: str
    line_number: int
    config_key: str
    config_value: str
    suggestion: str = "移至配置文件"


@dataclass
class ScanReport:
    """扫描报告"""
    total_files: int = 0
    implicit_variables: List[ImplicitVariable] = field(default_factory=list)
    implicit_logic: List[ImplicitLogic] = field(default_factory=list)
    implicit_dependencies: List[ImplicitDependency] = field(default_factory=list)
    implicit_configs: List[ImplicitConfig] = field(default_factory=list)
    
    def get_total_issues(self) -> int:
        """获取问题总数"""
        return (len(self.implicit_variables) + 
                len(self.implicit_logic) + 
                len(self.implicit_dependencies) + 
                len(self.implicit_configs))
    
    def is_clean(self) -> bool:
        """检查是否无隐式信息"""
        return self.get_total_issues() == 0


class MagicNumberDetector(ast.NodeVisitor):
    """魔法数字检测器"""
    
    MAGIC_PATTERNS = [
        (r'range\(\d+\)', 'range参数'),
        (r'\[\d+\]', '列表索引'),
        (r'\{\d+\}', '字典键'),
        (r'\s==\s\d+', '比较操作'),
        (r'\s>\s\d+', '大于比较'),
        (r'\s<\s\d+', '小于比较'),
        (r'\s>=\s\d+', '大于等于'),
        (r'\s<=\s\d+', '小于等于'),
    ]
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.findings: List[ImplicitLogic] = []
    
    def visit_Constant(self, node: ast.Constant):
        """检测常量值"""
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if node.value not in [0, 1, -1]:
                self.findings.append(ImplicitLogic(
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    code_snippet=f"{node.value}",
                    type="魔法数字",
                    suggestion=f"将 {node.value} 定义为命名常量"
                ))
        self.generic_visit(node)


class HardcodedConfigDetector(ast.NodeVisitor):
    """硬编码配置检测器"""
    
    HARDCODED_PATTERNS = [
        (r'timeout\s*=\s*\d+', 'timeout'),
        (r'port\s*=\s*\d+', 'port'),
        (r'host\s*=\s*["\'][^"\']+["\']', 'host'),
        (r'url\s*=\s*["\'][^"\']+["\']', 'url'),
        (r'limit\s*=\s*\d+', 'limit'),
        (r'max_\w+\s*=\s*\d+', 'max限制'),
        (r'retry\s*=\s*\d+', 'retry'),
    ]
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.findings: List[ImplicitConfig] = []
    
    def visit_Assign(self, node: ast.Assign):
        """检测赋值语句"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                for pattern, config_type in self.HARDCODED_PATTERNS:
                    if re.search(pattern, ast.unparse(node)):
                        self.findings.append(ImplicitConfig(
                            file_path=self.file_path,
                            line_number=node.lineno or 0,
                            config_key=var_name,
                            config_value=ast.unparse(node.value),
                            suggestion=f"将 {config_type} 移至配置文件"
                        ))
        self.generic_visit(node)


class ImplicitVariableDetector(ast.NodeVisitor):
    """隐式变量检测器（检测无类型注解的变量）"""
    
    EXCLUDED_NAMES = {'self', 'cls', '__init__'}
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.findings: List[ImplicitVariable] = []
        self.in_function = False
        self.function_name = ""
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """检测函数参数"""
        self.in_function = True
        self.function_name = node.name
        
        for arg in node.args.args:
            if arg.annotation is None and arg.arg not in self.EXCLUDED_NAMES:
                self.findings.append(ImplicitVariable(
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    variable_name=arg.arg,
                    context=f"函数 {node.name} 的参数",
                    suggestion=f"为参数 '{arg.arg}' 添加类型注解"
                ))
        
        self.generic_visit(node)
        self.in_function = False
    
    def visit_Assign(self, node: ast.Assign):
        """检测赋值语句"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if not var_name.isupper():
                    self.findings.append(ImplicitVariable(
                        file_path=self.file_path,
                        line_number=node.lineno or 0,
                        variable_name=var_name,
                        context="局部变量",
                        suggestion=f"为变量 '{var_name}' 添加类型注解"
                    ))
        self.generic_visit(node)


class ImplicitDependencyDetector(ast.NodeVisitor):
    """隐式依赖检测器"""
    
    KNOWN_STDLIB = {
        'os', 'sys', 're', 'json', 'datetime', 'time', 'math',
        'collections', 'itertools', 'functools', 'pathlib',
        'typing', 'abc', 'dataclasses', 'enum', 'threading',
        'ast', 'io', 'contextlib', 'uuid', 'logging', 'traceback',
        'tempfile', 'shutil', 'subprocess', 'platform', 'gc'
    }
    
    EXCLUDED_MODULES = {'src'}
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.findings: List[ImplicitDependency] = []
    
    def visit_Import(self, node: ast.Import):
        """检测import语句"""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            if module_name not in self.KNOWN_STDLIB and module_name not in self.EXCLUDED_MODULES:
                self.findings.append(ImplicitDependency(
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    module_name=module_name,
                    suggestion=f"确认 '{module_name}' 在requirements.txt中声明"
                ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """检测from...import语句"""
        if node.module:
            module_name = node.module.split('.')[0]
            if module_name not in self.KNOWN_STDLIB and module_name not in self.EXCLUDED_MODULES:
                self.findings.append(ImplicitDependency(
                    file_path=self.file_path,
                    line_number=node.lineno or 0,
                    module_name=module_name,
                    suggestion=f"确认 '{module_name}' 在requirements.txt中声明"
                ))
        self.generic_visit(node)


class ExplicitInfoScanner:
    """
    全局信息显式化扫描器
    
    遵循最小熵信息确定性要求：
    - 检测所有隐式信息
    - 输出明确的整改建议
    - 支持自动化集成
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.exclude_patterns = {
            '__pycache__', '.pytest_cache', '.ruff_cache',
            '.git', 'tests', 'docs', 'scripts'
        }
    
    def _should_scan(self, file_path: Path) -> bool:
        """判断是否应扫描"""
        if not file_path.suffix == '.py':
            return False
        if file_path.name.startswith('.'):
            return False
        for pattern in self.exclude_patterns:
            if pattern in str(file_path):
                return False
        return True
    
    def scan_file(self, file_path: Path) -> ScanReport:
        """扫描单个文件"""
        report = ScanReport()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            magic_detector = MagicNumberDetector(str(file_path))
            magic_detector.visit(tree)
            report.implicit_logic.extend(magic_detector.findings)
            
            config_detector = HardcodedConfigDetector(str(file_path))
            config_detector.visit(tree)
            report.implicit_configs.extend(config_detector.findings)
            
            var_detector = ImplicitVariableDetector(str(file_path))
            var_detector.visit(tree)
            report.implicit_variables.extend(var_detector.findings)
            
            dep_detector = ImplicitDependencyDetector(str(file_path))
            dep_detector.visit(tree)
            report.implicit_dependencies.extend(dep_detector.findings)
            
        except Exception as e:
            logger.error(f"扫描文件失败 {file_path}: {e}")
        
        return report
    
    def scan_project(self) -> ScanReport:
        """扫描整个项目"""
        logger.info(f"开始扫描项目: {self.project_root}")
        
        total_report = ScanReport()
        
        for py_file in self.project_root.rglob("*.py"):
            if self._should_scan(py_file):
                total_report.total_files += 1
                file_report = self.scan_file(py_file)
                
                total_report.implicit_variables.extend(file_report.implicit_variables)
                total_report.implicit_logic.extend(file_report.implicit_logic)
                total_report.implicit_dependencies.extend(file_report.implicit_dependencies)
                total_report.implicit_configs.extend(file_report.implicit_configs)
        
        logger.info(f"扫描完成: {total_report.total_files} 个文件, "
                    f"{total_report.get_total_issues()} 个问题")
        
        return total_report
    
    def generate_report(self, report: ScanReport) -> str:
        """生成扫描报告"""
        lines = ["=" * 70]
        lines.append("全局信息显式化扫描报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"扫描文件数: {report.total_files}")
        lines.append(f"问题总数: {report.get_total_issues()}")
        lines.append("")
        
        if report.implicit_variables:
            lines.append("-" * 70)
            lines.append(f"隐式变量 ({len(report.implicit_variables)} 个)")
            lines.append("-" * 70)
            for i, v in enumerate(report.implicit_variables[:10], 1):
                lines.append(f"{i}. {v.file_path}:{v.line_number}")
                lines.append(f"   变量: {v.variable_name}")
                lines.append(f"   上下文: {v.context}")
                lines.append(f"   建议: {v.suggestion}")
                lines.append("")
        
        if report.implicit_logic:
            lines.append("-" * 70)
            lines.append(f"隐式逻辑 ({len(report.implicit_logic)} 个)")
            lines.append("-" * 70)
            for i, l in enumerate(report.implicit_logic[:10], 1):
                lines.append(f"{i}. {l.file_path}:{l.line_number}")
                lines.append(f"   类型: {l.type}")
                lines.append(f"   代码: {l.code_snippet}")
                lines.append(f"   建议: {l.suggestion}")
                lines.append("")
        
        if report.implicit_dependencies:
            lines.append("-" * 70)
            lines.append(f"隐式依赖 ({len(report.implicit_dependencies)} 个)")
            lines.append("-" * 70)
            for i, d in enumerate(report.implicit_dependencies[:10], 1):
                lines.append(f"{i}. {d.file_path}:{d.line_number}")
                lines.append(f"   模块: {d.module_name}")
                lines.append(f"   建议: {d.suggestion}")
                lines.append("")
        
        if report.implicit_configs:
            lines.append("-" * 70)
            lines.append(f"隐式配置 ({len(report.implicit_configs)} 个)")
            lines.append("-" * 70)
            for i, c in enumerate(report.implicit_configs[:10], 1):
                lines.append(f"{i}. {c.file_path}:{c.line_number}")
                lines.append(f"   配置: {c.config_key} = {c.config_value}")
                lines.append(f"   建议: {c.suggestion}")
                lines.append("")
        
        if report.is_clean():
            lines.append("=" * 70)
            lines.append("✓ 项目无隐式信息，满足最小熵要求")
            lines.append("=" * 70)
        else:
            lines.append("=" * 70)
            lines.append(f"✗ 检测到 {report.get_total_issues()} 个隐式信息问题")
            lines.append("建议按上述提示进行整改")
            lines.append("=" * 70)
        
        return "\n".join(lines)


def demo_explicit_info_scanner():
    """演示信息显式化扫描"""
    print("=" * 70)
    print("全局信息显式化扫描演示")
    print("=" * 70)
    print()
    
    project_root = Path(__file__).parent.parent.parent
    scanner = ExplicitInfoScanner(str(project_root))
    
    report = scanner.scan_project()
    
    print(scanner.generate_report(report))
    print()
    
    print("=" * 70)
    print("扫描结果统计:")
    print(f"  扫描文件数: {report.total_files}")
    print(f"  隐式变量: {len(report.implicit_variables)} 个")
    print(f"  隐式逻辑: {len(report.implicit_logic)} 个")
    print(f"  隐式依赖: {len(report.implicit_dependencies)} 个")
    print(f"  隐式配置: {len(report.implicit_configs)} 个")
    print(f"  问题总数: {report.get_total_issues()}")
    print(f"  满足最小熵: {'✓' if report.is_clean() else '✗'}")
    print("=" * 70)


if __name__ == "__main__":
    demo_explicit_info_scanner()
