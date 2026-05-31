#!/bin/bash
set -e

echo "===== 阶段21: 变量原子化验证 ====="
echo ""

echo "1. 运行扫描器演示"
python -m src.code.variable_atom_scanner
echo ""

echo "2. 运行完整功能演示"
python -m src.code.variable_atom_scanner full
echo ""

echo "3. 验证模块导入"
python -c "from src.code.variable_atom_scanner import VariableAtomScanner, VariableCategory, SingleSemanticValidator; print('✓ 模块导入成功')"
echo ""

echo "4. 扫描项目代码"
python -c "
from src.code.variable_atom_scanner import scan_directory
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
results = scan_directory('src')
total_vars = 0
total_issues = 0
for path, res in results.items():
    total_vars += res.total_count
    total_issues += res.issue_count
print(f'✓ 扫描完成: {len(results)} 个文件')
print(f'✓ 总变量数: {total_vars}')
print(f'✓ 有问题的变量数: {total_issues}')
"
echo ""

echo "===== 验证完成 ====="
