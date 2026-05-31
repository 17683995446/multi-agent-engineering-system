#!/bin/bash
set -e

echo "===== 阶段22：方法原子化验证 ====="
echo ""

echo "1. 运行方法扫描器演示"
python -m src.code.method_atom_scanner
echo ""

echo "2. 运行完整功能演示"
python -m src.code.method_atom_scanner full
echo ""

echo "3. 验证模块导入"
python -c "from src.code.method_atom_scanner import MethodAtomScanner, MethodSplitter, scan_methods; print('✓ 模块导入成功')"
echo ""

echo "4. 扫描项目中的方法"
python -c "
from src.code.method_atom_scanner import scan_directory_for_methods
import sys, os

results = scan_directory_for_methods('src')

total_methods = 0
issue_methods = 0

for path, result in results.items():
    total_methods += result.total_methods
    issue_methods += result.issue_methods

print(f'✓ 扫描了 {len(results)} 个文件')
print(f'✓ 总方法数: {total_methods}')
print(f'✓ 有问题的方法数: {issue_methods}')
"
echo ""

echo "===== 验证完成 ====="
