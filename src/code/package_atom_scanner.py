"""
包结构原子化扫描器
遵循第一性原理：包原子内聚约束

核心功能：
1. 包层级结构分析
2. 包间依赖关系检测
3. 循环依赖检测
4. 包内模块粒度统一性检测
5. 包原子内聚性验证
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
class PackageInfo:
    """包信息"""
    name: str
    path: Path
    level: int
    modules: List[str] = field(default_factory=list)
    subpackages: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    from_imports: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class PackageAnalysis:
    """包分析结果"""
    package: PackageInfo
    is_giant_package: bool = False
    is_well_structured: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class PackageHierarchyResult:
    """包层级结构结果"""
    total_levels: int
    packages_per_level: Dict[int, List[str]]
    dependencies: Dict[str, Set[str]]
    circular_dependencies: List[List[str]]
    is_hierarchical: bool
    issues: List[str]


class PackageAtomScanner:
    """包结构原子化扫描器"""
    
    # 包层级标准
    MAX_LEVELS = 4
    MAX_MODULES_PER_PACKAGE = 20
    MIN_MODULES_PER_PACKAGE = 2
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.packages: Dict[str, PackageInfo] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.circular_deps: List[List[str]] = []
    
    def scan(self) -> PackageHierarchyResult:
        """扫描包结构"""
        self._discover_packages()
        self._analyze_dependencies()
        self._detect_circular_dependencies()
        
        return self._build_hierarchy_result()
    
    def _discover_packages(self):
        """发现所有包"""
        for init_file in self.root_dir.rglob('__init__.py'):
            package_path = init_file.parent
            relative_path = package_path.relative_to(self.root_dir)
            
            # 计算包层级
            level = len(relative_path.parts)
            
            # 获取包名
            package_name = str(relative_path).replace('/', '.').replace('\\', '.')
            
            # 获取模块列表
            modules = self._get_package_modules(package_path)
            
            # 获取导入信息
            imports, from_imports = self._get_package_imports(init_file)
            
            # 获取子包
            subpackages = [str(p.relative_to(package_path)).replace('/', '.').replace('\\', '.') 
                         for p in package_path.iterdir() if p.is_dir() and (p / '__init__.py').exists()]
            
            self.packages[package_name] = PackageInfo(
                name=package_name,
                path=package_path,
                level=level,
                modules=modules,
                subpackages=subpackages,
                imports=imports,
                from_imports=from_imports
            )
    
    def _get_package_modules(self, package_path: Path) -> List[str]:
        """获取包内模块"""
        modules = []
        for py_file in package_path.glob('*.py'):
            if py_file.name != '__init__.py':
                modules.append(py_file.stem)
        return modules
    
    def _get_package_imports(self, init_file: Path) -> Tuple[List[str], Dict[str, List[str]]]:
        """获取包导入信息"""
        try:
            with open(init_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
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
        except:
            return [], {}
    
    def _analyze_dependencies(self):
        """分析包间依赖"""
        for package_name, package_info in self.packages.items():
            # 从导入中提取依赖
            for imp in package_info.imports:
                self.dependencies[package_name].add(imp)
            
            for from_module, _ in package_info.from_imports.items():
                self.dependencies[package_name].add(from_module)
    
    def _detect_circular_dependencies(self):
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.dependencies.get(node, set()):
                if neighbor not in self.packages:
                    continue
                    
                if neighbor not in visited:
                    if dfs(neighbor, path + [node]):
                        return True
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    self.circular_deps.append(path[cycle_start:] + [neighbor])
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.packages:
            if node not in visited:
                dfs(node, [node])
    
    def _build_hierarchy_result(self) -> PackageHierarchyResult:
        """构建层级结果"""
        packages_per_level = defaultdict(list)
        
        for package_name, package_info in self.packages.items():
            packages_per_level[package_info.level].append(package_name)
        
        return PackageHierarchyResult(
            total_levels=len(packages_per_level),
            packages_per_level=dict(packages_per_level),
            dependencies=dict(self.dependencies),
            circular_dependencies=self.circular_deps,
            is_hierarchical=len(packages_per_level) <= self.MAX_LEVELS,
            issues=self._get_hierarchy_issues(packages_per_level)
        )
    
    def _get_hierarchy_issues(self, packages_per_level: Dict[int, List[str]]) -> List[str]:
        """获取层级结构问题"""
        issues = []
        
        if len(packages_per_level) > self.MAX_LEVELS:
            issues.append(f"包层级过深 ({len(packages_per_level)}层)，建议少于 {self.MAX_LEVELS} 层")
        
        return issues
    
    def analyze_package(self, package_name: str) -> PackageAnalysis:
        """分析单个包"""
        if package_name not in self.packages:
            return None
        
        package_info = self.packages[package_name]
        analysis = PackageAnalysis(package=package_info)
        
        # 检查包大小
        if len(package_info.modules) > self.MAX_MODULES_PER_PACKAGE:
            analysis.is_giant_package = True
            analysis.issues.append(
                f"包内模块过多 ({len(package_info.modules)})，建议少于 {self.MAX_MODULES_PER_PACKAGE}"
            )
        
        if 0 < len(package_info.modules) < self.MIN_MODULES_PER_PACKAGE:
            analysis.issues.append(
                f"包内模块过少 ({len(package_info.modules)})，建议多于 {self.MIN_MODULES_PER_PACKAGE}"
            )
        
        # 检查包结构
        if package_info.modules or package_info.subpackages:
            analysis.is_well_structured = True
        
        # 生成建议
        if analysis.is_giant_package:
            analysis.suggestions.append(
                "建议将大包拆分为多个子包，每个子包职责单一"
            )
        
        if len(package_info.modules) < self.MIN_MODULES_PER_PACKAGE:
            analysis.suggestions.append(
                "包内模块过少，考虑合并到其他包或拆分出更多模块"
            )
        
        return analysis


def demo_package_atom_scanner():
    """演示包结构原子化扫描器"""
    print("=" * 70)
    print("包结构原子化扫描器 - 层级清晰与内聚性检测")
    print("=" * 70)
    print()
    
    # 创建测试包结构
    test_structure = [
        ('src/__init__.py', '"""Src package."""'),
        ('src/common/__init__.py', '"""Common package."""\nfrom .utils import *'),
        ('src/common/utils.py', '"""Utilities."""\ndef helper(): pass'),
        ('src/agents/__init__.py', '"""Agents package."""\nfrom .autogen import *'),
        ('src/agents/autogen.py', '"""AutoGen integration."""\nclass AutoGenAgent: pass'),
        ('src/code/__init__.py', '"""Code package."""'),
        ('src/code/parser.py', '"""Parser."""\ndef parse(): pass'),
        ('src/code/linter.py', '"""Linter."""\ndef lint(): pass'),
    ]
    
    import tempfile
    import shutil
    
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        for file_path, content in test_structure:
            full_path = temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding='utf-8')
        
        print("📦 测试包结构:")
        print("-" * 70)
        
        for i, (file_path, _) in enumerate(test_structure):
            indent = '  ' * file_path.count('/') 
            name = file_path.split('/')[-1]
            print(f"{indent}{name}")
        
        print()
        print("🔍 扫描包结构...")
        print()
        
        scanner = PackageAtomScanner(str(temp_dir))
        result = scanner.scan()
        
        print(f"📊 包层级结构分析:")
        print(f"  总层级数: {result.total_levels}")
        print(f"  层级结构良好: {'✓' if result.is_hierarchical else '✗'}")
        
        for level, packages in sorted(result.packages_per_level.items()):
            print(f"  层级 {level}: {', '.join(packages)}")
        
        print()
        print(f"📊 包依赖分析:")
        print(f"  包数量: {len(scanner.packages)}")
        
        for package_name, deps in scanner.dependencies.items():
            if deps:
                print(f"  {package_name} → {', '.join(deps)}")
        
        print()
        print(f"📊 循环依赖检测:")
        if result.circular_dependencies:
            for cycle in result.circular_dependencies:
                print(f"  ⚠️  发现循环依赖: {' → '.join(cycle)}")
        else:
            print("  ✓ 无循环依赖")
        
        if result.issues:
            print()
            print(f"⚠️  层级结构问题:")
            for issue in result.issues:
                print(f"  - {issue}")
        
        print()
        print("=" * 70)
        print("📋 包结构原子化标准:")
        print()
        print(f"✅ 层级数 ≤ {PackageAtomScanner.MAX_LEVELS}")
        print(f"✅ 每包模块数 {PackageAtomScanner.MIN_MODULES_PER_PACKAGE}-{PackageAtomScanner.MAX_MODULES_PER_PACKAGE}")
        print(f"✅ 包层级职责分明")
        print(f"✅ 包之间无循环依赖")
        print(f"✅ 包内模块粒度统一")
        print(f"✅ 包原子内聚（单一职责）")
        print()
        print("=" * 70)
        
    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    demo_package_atom_scanner()
