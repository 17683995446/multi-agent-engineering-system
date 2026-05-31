"""
全局DAG单向依赖校验器
遵循第一性原理：依赖单向性公理

功能：
1. 自动检测项目所有依赖关系
2. 精准识别循环依赖、双向依赖
3. 支持依赖拓扑可视化输出
4. 严格符合第一性依赖单向性公理
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from src.common.utils import setup_logger

logger = setup_logger(__name__)


@dataclass
class DependencyNode:
    """依赖节点"""
    module_name: str
    file_path: str
    imports: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)


@dataclass
class DependencyEdge:
    """依赖边"""
    from_module: str
    to_module: str
    file_path: str
    import_line: int


@dataclass
class DependencyGraph:
    """依赖图"""
    nodes: Dict[str, DependencyNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    
    def add_node(self, module_name: str, file_path: str) -> None:
        if module_name not in self.nodes:
            self.nodes[module_name] = DependencyNode(
                module_name=module_name,
                file_path=file_path
            )
    
    def add_edge(self, from_module: str, to_module: str, file_path: str, import_line: int) -> None:
        edge = DependencyEdge(
            from_module=from_module,
            to_module=to_module,
            file_path=file_path,
            import_line=import_line
        )
        self.edges.append(edge)
        
        if from_module in self.nodes and to_module in self.nodes:
            if to_module not in self.nodes[from_module].imports:
                self.nodes[from_module].imports.append(to_module)
            if from_module not in self.nodes[to_module].imported_by:
                self.nodes[to_module].imported_by.append(from_module)


class ImportVisitor(ast.NodeVisitor):
    """AST导入语句访问器"""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports: List[Tuple[str, int]] = []
    
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.append((node.module, node.lineno))
        self.generic_visit(node)


class DAGDependencyChecker:
    """
    DAG单向依赖校验器
    
    遵循第一性原理依赖单向性公理：
    - 检测所有模块依赖关系
    - 识别循环依赖
    - 识别双向依赖
    - 验证层级单向依赖规则
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.dependency_graph = DependencyGraph()
        self.layer_mapping = self._init_layer_mapping()
    
    def _init_layer_mapping(self) -> Dict[str, str]:
        """初始化层级映射"""
        return {
            "src.input": "input",
            "src.workflow": "workflow",
            "src.agents": "agent",
            "src.code": "code",
            "src.common": "common"
        }
    
    def _get_module_name(self, file_path: Path) -> str:
        """从文件路径获取模块名"""
        rel_path = file_path.relative_to(self.project_root)
        module_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
        
        if module_parts[0] == 'src':
            module_parts = module_parts[1:]
        
        return ".".join(module_parts)
    
    def _get_module_layer(self, module_name: str) -> Optional[str]:
        """获取模块所属层级"""
        for prefix, layer in self.layer_mapping.items():
            if module_name.startswith(prefix):
                return layer
        return None
    
    def _is_valid_import(self, import_name: str) -> bool:
        """判断是否为有效的项目内导入"""
        return import_name.startswith("src.") or import_name in self.layer_mapping
    
    def _should_include_file(self, file_path: Path) -> bool:
        """判断是否应包含该文件"""
        if not file_path.suffix == '.py':
            return False
        if '__pycache__' in str(file_path):
            return False
        if file_path.name.startswith('.'):
            return False
        return True
    
    def scan_dependencies(self) -> DependencyGraph:
        """
        扫描项目依赖关系
        
        Returns:
            DependencyGraph: 依赖图
        """
        logger.info(f"开始扫描项目依赖: {self.project_root}")
        
        for py_file in self.project_root.rglob("*.py"):
            if not self._should_include_file(py_file):
                continue
            
            try:
                module_name = self._get_module_name(py_file)
                self.dependency_graph.add_node(module_name, str(py_file))
                
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                tree = ast.parse(source)
                visitor = ImportVisitor(module_name)
                visitor.visit(tree)
                
                for import_name, import_line in visitor.imports:
                    if self._is_valid_import(import_name):
                        self.dependency_graph.add_edge(
                            from_module=module_name,
                            to_module=import_name,
                            file_path=str(py_file),
                            import_line=import_line
                        )
                        
                        if import_name not in self.dependency_graph.nodes:
                            self.dependency_graph.add_node(import_name, "external")
                
                logger.debug(f"扫描模块: {module_name}, 导入: {visitor.imports}")
            
            except Exception as e:
                logger.error(f"扫描文件失败 {py_file}: {e}")
        
        logger.info(f"依赖扫描完成: {len(self.dependency_graph.nodes)} 个节点, {len(self.dependency_graph.edges)} 条边")
        return self.dependency_graph
    
    def detect_circular_dependencies(self) -> List[List[str]]:
        """
        检测循环依赖
        
        Returns:
            List[List[str]]: 循环依赖链列表
        """
        logger.info("开始检测循环依赖...")
        
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            if node in self.dependency_graph.nodes:
                for neighbor in self.dependency_graph.nodes[node].imports:
                    if neighbor not in visited:
                        dfs(neighbor)
                    elif neighbor in rec_stack:
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        if cycle not in cycles:
                            cycles.append(cycle)
            
            path.pop()
            rec_stack.remove(node)
        
        for node in self.dependency_graph.nodes:
            if node not in visited:
                dfs(node)
        
        logger.info(f"检测到 {len(cycles)} 个循环依赖")
        for i, cycle in enumerate(cycles, 1):
            logger.warning(f"循环依赖 {i}: {' -> '.join(cycle)}")
        
        return cycles
    
    def detect_bidirectional_dependencies(self) -> List[Tuple[str, str]]:
        """
        检测双向依赖
        
        Returns:
            List[Tuple[str, str]]: 双向依赖对列表
        """
        logger.info("开始检测双向依赖...")
        
        bidirectional = []
        checked = set()
        
        for node_name, node in self.dependency_graph.nodes.items():
            for neighbor in node.imports:
                pair = tuple(sorted([node_name, neighbor]))
                if pair not in checked and pair[0] != pair[1]:
                    if neighbor in self.dependency_graph.nodes:
                        if node_name in self.dependency_graph.nodes[neighbor].imports:
                            bidirectional.append(pair)
                            logger.warning(f"双向依赖: {pair[0]} <-> {pair[1]}")
                checked.add(pair)
        
        logger.info(f"检测到 {len(bidirectional)} 对双向依赖")
        return bidirectional
    
    def verify_layer_dependencies(self) -> Tuple[bool, List[str]]:
        """
        验证层级单向依赖规则
        
        层级依赖顺序：input -> workflow -> agent -> code -> common
        
        Returns:
            Tuple[bool, List[str]]: (是否合规, 违规信息列表)
        """
        logger.info("开始验证层级单向依赖...")
        
        violations = []
        layer_order = ["common", "input", "workflow", "agent", "code"]
        
        for node_name, node in self.dependency_graph.nodes.items():
            src_layer = self._get_module_layer(node_name)
            if not src_layer:
                continue
            
            for dep in node.imports:
                dst_layer = self._get_module_layer(dep)
                if not dst_layer:
                    continue
                
                src_idx = layer_order.index(src_layer) if src_layer in layer_order else -1
                dst_idx = layer_order.index(dst_layer) if dst_layer in layer_order else -1
                
                if src_idx > 0 and dst_idx > 0:
                    if src_idx <= dst_idx and src_layer != dst_layer:
                        if src_layer != "common" and dst_layer != "common":
                            violation = f"层级依赖违规: {node_name}({src_layer}) 不能依赖 {dep}({dst_layer})"
                            violations.append(violation)
                            logger.warning(violation)
        
        is_valid = len(violations) == 0
        if is_valid:
            logger.info("✓ 层级单向依赖验证通过")
        else:
            logger.error(f"✗ 检测到 {len(violations)} 个层级依赖违规")
        
        return is_valid, violations
    
    def generate_topology(self) -> str:
        """
        生成依赖拓扑结构
        
        Returns:
            str: 拓扑结构字符串
        """
        logger.info("生成依赖拓扑...")
        
        lines = ["依赖拓扑结构:", "=" * 60]
        
        layer_groups = defaultdict(list)
        for node_name in sorted(self.dependency_graph.nodes.keys()):
            layer = self._get_module_layer(node_name) or "unknown"
            layer_groups[layer].append(node_name)
        
        for layer in ["input", "workflow", "agent", "code", "common", "unknown"]:
            if layer in layer_groups:
                lines.append(f"\n[{layer.upper()} 层]")
                for module in sorted(layer_groups[layer]):
                    imports = self.dependency_graph.nodes[module].imports
                    if imports:
                        lines.append(f"  {module} -> {', '.join(imports)}")
                    else:
                        lines.append(f"  {module}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    def visualize_dependencies(self) -> str:
        """
        生成可视化依赖图（文本格式）
        
        Returns:
            str: 可视化依赖图
        """
        logger.info("生成可视化依赖图...")
        
        lines = ["依赖关系可视化:", "-" * 60]
        
        for edge in sorted(self.dependency_graph.edges, key=lambda e: e.from_module):
            src_layer = self._get_module_layer(edge.from_module) or "?"
            dst_layer = self._get_module_layer(edge.to_module) or "?"
            lines.append(f"{edge.from_module}({src_layer}) -> {edge.to_module}({dst_layer}) @ {edge.file_path}:{edge.import_line}")
        
        lines.append("-" * 60)
        return "\n".join(lines)
    
    def run_full_check(self) -> Dict[str, any]:
        """
        运行完整依赖检查
        
        Returns:
            Dict: 检查结果
        """
        logger.info("=" * 60)
        logger.info("开始全局DAG单向依赖校验")
        logger.info("=" * 60)
        
        self.scan_dependencies()
        
        circular_deps = self.detect_circular_dependencies()
        bidirectional_deps = self.detect_bidirectional_dependencies()
        layer_valid, layer_violations = self.verify_layer_dependencies()
        
        result = {
            "total_nodes": len(self.dependency_graph.nodes),
            "total_edges": len(self.dependency_graph.edges),
            "circular_dependencies": circular_deps,
            "bidirectional_dependencies": bidirectional_deps,
            "layer_dependency_valid": layer_valid,
            "layer_violations": layer_violations,
            "topology": self.generate_topology(),
            "visualization": self.visualize_dependencies(),
            "passed": layer_valid and len(circular_deps) == 0 and len(bidirectional_deps) == 0
        }
        
        logger.info("=" * 60)
        logger.info("依赖校验结果:")
        logger.info(f"  总节点数: {result['total_nodes']}")
        logger.info(f"  总边数: {result['total_edges']}")
        logger.info(f"  循环依赖: {len(circular_deps)} 个")
        logger.info(f"  双向依赖: {len(bidirectional_deps)} 对")
        logger.info(f"  层级依赖合规: {'✓' if layer_valid else '✗'}")
        logger.info(f"  总体通过: {'✓' if result['passed'] else '✗'}")
        logger.info("=" * 60)
        
        return result


def demo_dag_checker():
    """演示DAG依赖校验"""
    print("=" * 60)
    print("全局DAG单向依赖校验演示")
    print("=" * 60)
    print()
    
    project_root = Path(__file__).parent.parent.parent
    checker = DAGDependencyChecker(str(project_root))
    
    result = checker.run_full_check()
    
    print("\n依赖拓扑:")
    print(result['topology'])
    print()
    
    print("依赖可视化:")
    print(result['visualization'])
    print()
    
    print("=" * 60)
    print("校验结果:")
    print(f"  总节点数: {result['total_nodes']}")
    print(f"  总边数: {result['total_edges']}")
    print(f"  循环依赖: {len(result['circular_dependencies'])} 个")
    print(f"  双向依赖: {len(result['bidirectional_dependencies'])} 对")
    print(f"  层级依赖合规: {'✓' if result['layer_dependency_valid'] else '✗'}")
    print(f"  总体通过: {'✓' if result['passed'] else '✗'}")
    print("=" * 60)
    
    if not result['passed']:
        if result['circular_dependencies']:
            print("\n循环依赖详情:")
            for i, cycle in enumerate(result['circular_dependencies'], 1):
                print(f"  {i}. {' -> '.join(cycle)}")
        
        if result['bidirectional_dependencies']:
            print("\n双向依赖详情:")
            for pair in result['bidirectional_dependencies']:
                print(f"  {pair[0]} <-> {pair[1]}")
        
        if result['layer_violations']:
            print("\n层级依赖违规详情:")
            for violation in result['layer_violations']:
                print(f"  ✗ {violation}")
    
    return result


if __name__ == "__main__":
    demo_dag_checker()
