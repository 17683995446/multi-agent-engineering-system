#!/bin/bash
set -e

echo "===== 阶段27：包结构原子化验证 ====="
echo ""

echo "1. 运行包结构原子化扫描器演示"
python -m src.code.package_atom_scanner
echo ""

echo "2. 验证模块导入"
python -c "from src.code.package_atom_scanner import PackageAtomScanner, PackageAnalysis; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
