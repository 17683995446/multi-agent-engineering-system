"""
模块原子化扫描器
遵循第一性原理：模块原子边界清晰原则

核心功能：
1. 模块粒度检测（行数、类数、函数数）
2. 模块接口检测（__all__、公共API）
3. 模块内部实现隐蔽性检测
4. 模块间依赖关系检测
5. 循环依赖和过度耦合检测
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


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    path: str
    lines_count: int
    class_count: int
    function_count: int
    public_api: List[str] = field(default_factory=list)
    private_api: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    from_imports: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ModuleAnalysis:
    """模块分析结果"""
    module: ModuleInfo
    is_giant_module: bool = False
    has_clean_interface: bool = False
    has_hidden_implementation: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class DependencyInfo:
    """依赖信息"""
    from_module: str
    to_module: str
    is_circular: bool = False
    is_over_coupled: bool = False


class ModuleAtomScanner:
    """模块原子化扫描器"""
    
    # 模块粒度阈值
    MAX_LINES = 500
    MAX_CLASSES = 10
    MAX_FUNCTIONS = 30
    MAX_PUBLIC_API = 20
    
    def __init__(self):
        self.modules: Dict[str, ModuleInfo] = {}
        self.dependencies: List[DependencyInfo] = {}
    
    def scan_file(self, file_path: str) -> ModuleAnalysis:
        """扫描单个文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        module_info = self._parse_module(file_path, source)
        analysis = self._analyze_module(module_info)
        return analysis
    
    def scan_directory(self, directory: str) -> Dict[str, ModuleAnalysis]:
        """扫描目录中的所有模块"""
        results = {}
        for file in Path(directory).rglob('*.py'):
            if file.name.startswith('__'):
                continue
            
            analysis = self.scan_file(str(file))
            results[str(file)] = analysis
        
        return results
    
    def _parse_module(self, file_path: str, source: str) -> ModuleInfo:
        """解析模块"""
        module_name = Path(file_path).stem
        
        try:
            tree = ast.parse(source)
        except:
            return ModuleInfo(
                name=module_name,
                path=file_path,
                lines_count=len(source.split('\n')),
                class_count=0,
                function_count=0
            )
        
        # 统计类和函数
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        functions = [node.name for node in ast.walk(tree) 
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_')]
        
        # 获取公共API
        public_api = self._get_public_api(tree)
        
        # 获取私有API
        private_api = self._get_private_api(tree)
        
        # 获取导入
        imports, from_imports = self._get_imports(tree)
        
        return ModuleInfo(
            name=module_name,
            path=file_path,
            lines_count=len(source.split('\n')),
            class_count=len(classes),
            function_count=len(functions),
            public_api=public_api,
            private_api=private_api,
            imports=imports,
            from_imports=from_imports
        )
    
    def _get_public_api(self, tree: ast.AST) -> List[str]:
        """获取公共API"""
        public_api = []
        
        # 检查 __all__
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    public_api.append(str(elt.value))
                                elif isinstance(elt, ast.Name):
                                    public_api.append(elt.id)
                        break
        
        # 如果没有 __all__，则所有非下划线开头的都是公共API
        if not public_api:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith('_'):
                        public_api.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith('_'):
                        public_api.append(node.name)
        
        return public_api
    
    def _get_private_api(self, tree: ast.AST) -> List[str]:
        """获取私有API"""
        private_api = []
        
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_'):
                    private_api.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith('_'):
                    private_api.append(node.name)
        
        return private_api
    
    def _get_imports(self, tree: ast.AST) -> Tuple[List[str], Dict[str, List[str]]]:
        """获取导入信息"""
        imports = []
        from_imports = defaultdict(list)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    from_imports[node.module] = [alias.name for alias in node.names]
        
        return imports, dict(from_imports)
    
    def _analyze_module(self, module_info: ModuleInfo) -> ModuleAnalysis:
        """分析模块"""
        analysis = ModuleAnalysis(module=module_info)
        
        # 1. 检查粒度
        if module_info.lines_count > self.MAX_LINES:
            analysis.is_giant_module = True
            analysis.issues.append(
                f"模块行数过多 ({module_info.lines_count})，建议少于 {self.MAX_LINES}"
            )
        
        if module_info.class_count > self.MAX_CLASSES:
            analysis.is_giant_module = True
            analysis.issues.append(
                f"模块类数过多 ({module_info.class_count})，建议少于 {self.MAX_CLASSES}"
            )
        
        if module_info.function_count > self.MAX_FUNCTIONS:
            analysis.is_giant_module = True
            analysis.issues.append(
                f"模块函数数过多 ({module_info.function_count})，建议少于 {self.MAX_FUNCTIONS}"
            )
        
        # 2. 检查接口
        if module_info.public_api:
            analysis.has_clean_interface = True
            if len(module_info.public_api) > self.MAX_PUBLIC_API:
                analysis.issues.append(
                    f"公共API过多 ({len(module_info.public_api)})，建议少于 {self.MAX_PUBLIC_API}"
                )
        else:
            analysis.issues.append("模块缺少公共API")
        
        # 3. 检查实现隐蔽性
        if module_info.private_api:
            analysis.has_hidden_implementation = True
        else:
            analysis.issues.append("模块缺少私有实现（所有内容都是公共的）")
        
        # 4. 生成建议
        if analysis.is_giant_module:
            analysis.suggestions.append(
                "建议将大模块拆分为多个小模块，每个模块职责单一"
            )
        
        if not analysis.has_clean_interface:
            analysis.suggestions.append(
                "建议使用 __all__ 明确定义公共API"
            )
        
        return analysis


class ModuleDependencyAnalyzer:
    """模块依赖分析器"""
    
    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.circular_deps: List[List[str]] = []
        self.over_coupled: List[str] = []
    
    def analyze_dependencies(self, modules: Dict[str, ModuleInfo]) -> Dict[str, any]:
        """分析模块间依赖"""
        # 提取依赖关系
        for module_path, module_info in modules.items():
            module_name = module_info.name
            
            for imp in module_info.imports:
                self.dependencies[module_name].add(imp)
            
            for from_module, imports in module_info.from_imports.items():
                self.dependencies[module_name].add(from_module)
        
        # 检测循环依赖
        self._detect_circular_dependencies()
        
        # 检测过度耦合
        self._detect_over_coupling()
        
        return {
            'dependencies': dict(self.dependencies),
            'circular_deps': self.circular_deps,
            'over_coupled': self.over_coupled
        }
    
    def _detect_circular_dependencies(self):
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.dependencies.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor, path + [node]):
                        return True
                elif neighbor in rec_stack:
                    # 找到循环依赖
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    self.circular_deps.append(path[cycle_start:] + [neighbor])
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.dependencies:
            if node not in visited:
                dfs(node, [node])
    
    def _detect_over_coupling(self):
        """检测过度耦合"""
        for module, deps in self.dependencies.items():
            # 如果一个模块依赖超过10个其他模块，认为是过度耦合
            if len(deps) > 10:
                self.over_coupled.append(module)


def demo_module_atom_scanner():
    """演示模块原子化扫描器"""
    print("=" * 70)
    print("模块原子化扫描器 - 模块粒度与接口检测")
    print("=" * 70)
    print()
    
    # 创建测试模块
    giant_module_code = '''
"""
超大模块示例 - 包含太多内容
"""

MAX_VALUE = 100
TIMEOUT = 30

__all__ = ['process_data', 'validate_input', 'UserService', 'OrderService']


class UserService:
    """用户服务"""
    def get_user(self, user_id):
        pass
    
    def create_user(self, user_data):
        pass
    
    def update_user(self, user_id, data):
        pass
    
    def delete_user(self, user_id):
        pass


class OrderService:
    """订单服务"""
    def create_order(self, order_data):
        pass
    
    def get_order(self, order_id):
        pass
    
    def update_order(self, order_id, data):
        pass
    
    def cancel_order(self, order_id):
        pass


class ProductService:
    """产品服务"""
    def get_product(self, product_id):
        pass
    
    def create_product(self, product_data):
        pass


def process_data(data):
    """处理数据"""
    validate_input(data)
    return data


def validate_input(data):
    """验证输入"""
    return len(data) > 0


def _internal_helper():
    """内部辅助函数"""
    pass


def _calculate_metrics():
    """计算指标"""
    pass
'''

    good_module_code = '''
"""
良好的模块示例 - 职责单一、接口清晰
"""

__all__ = ['UserService', 'get_user', 'create_user']

from typing import Dict, Optional


class UserService:
    """用户服务 - 单一职责"""
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """获取用户"""
        pass
    
    def create_user(self, user_data: Dict) -> str:
        """创建用户"""
        pass


def get_user(user_id: str) -> Optional[Dict]:
    """获取用户（便捷函数）"""
    service = UserService()
    return service.get_user(user_id)


def create_user(user_data: Dict) -> str:
    """创建用户（便捷函数）"""
    service = UserService()
    return service.create_user(user_data)


def _validate_user_data(data: Dict) -> bool:
    """内部：验证用户数据"""
    return 'name' in data and 'email' in data
'''

    print("📊 超大模块分析:")
    print("-" * 70)
    
    temp_file = Path('/tmp/test_giant_module.py')
    temp_file.write_text(giant_module_code.strip(), encoding='utf-8')
    
    scanner = ModuleAtomScanner()
    analysis = scanner.scan_file(str(temp_file))
    
    print(f"模块: {analysis.module.name}")
    print(f"  文件路径: {analysis.module.path}")
    print(f"  行数: {analysis.module.lines_count}")
    print(f"  类数: {analysis.module.class_count}")
    print(f"  函数数: {analysis.module.function_count}")
    print(f"  公共API: {len(analysis.module.public_api)}")
    print(f"  私有实现: {len(analysis.module.private_api)}")
    print(f"  是超大模块: {'✓' if analysis.is_giant_module else '✗'}")
    print(f"  接口清晰: {'✓' if analysis.has_clean_interface else '✗'}")
    print(f"  实现隐蔽: {'✓' if analysis.has_hidden_implementation else '✗'}")
    
    if analysis.issues:
        print(f"  问题:")
        for issue in analysis.issues:
            print(f"    - {issue}")
    
    if analysis.suggestions:
        print(f"  建议:")
        for suggestion in analysis.suggestions:
            print(f"    - {suggestion}")
    
    print()
    print("📊 良好模块分析:")
    print("-" * 70)
    
    temp_file2 = Path('/tmp/test_good_module.py')
    temp_file2.write_text(good_module_code.strip(), encoding='utf-8')
    
    analysis2 = scanner.scan_file(str(temp_file2))
    
    print(f"模块: {analysis2.module.name}")
    print(f"  行数: {analysis2.module.lines_count}")
    print(f"  类数: {analysis2.module.class_count}")
    print(f"  函数数: {analysis2.module.function_count}")
    print(f"  公共API: {len(analysis2.module.public_api)}")
    print(f"  私有实现: {len(analysis2.module.private_api)}")
    print(f"  是超大模块: {'✓' if analysis2.is_giant_module else '✗'}")
    print(f"  接口清晰: {'✓' if analysis2.has_clean_interface else '✗'}")
    print(f"  实现隐蔽: {'✓' if analysis2.has_hidden_implementation else '✗'}")
    
    if analysis2.issues:
        print(f"  问题:")
        for issue in analysis2.issues:
            print(f"    - {issue}")
    
    print()
    print("=" * 70)
    print("📋 模块原子化标准:")
    print()
    print(f"✅ 行数 ≤ {ModuleAtomScanner.MAX_LINES}")
    print(f"✅ 类数 ≤ {ModuleAtomScanner.MAX_CLASSES}")
    print(f"✅ 函数数 ≤ {ModuleAtomScanner.MAX_FUNCTIONS}")
    print(f"✅ 公共API ≤ {ModuleAtomScanner.MAX_PUBLIC_API}")
    print()
    print("✅ 接口清晰：使用 __all__ 定义公共API")
    print("✅ 实现隐蔽：私有函数/类以下划线开头")
    print("✅ 无循环依赖")
    print("✅ 无过度耦合")
    print()
    print("=" * 70)


if __name__ == "__main__":
    demo_module_atom_scanner()
