#!/bin/bash
set -e

echo "===== 阶段26：模块原子化约束验证 ====="
echo ""

echo "1. 运行模块原子化扫描器演示"
python -m src.code.module_atom_scanner
echo ""

echo "2. 验证模块导入"
python -c "from src.code.module_atom_scanner import ModuleAtomScanner, ModuleDependencyAnalyzer; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
