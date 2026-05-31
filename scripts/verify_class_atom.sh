#!/bin/bash
set -e

echo "===== 阶段24：类原子三区分离验证 ====="
echo ""

echo "1. 运行类原子化扫描器演示"
python -m src.code.class_atom_scanner
echo ""

echo "2. 验证模块导入"
python -c "from src.code.class_atom_scanner import ClassAtomScanner, ClassComplianceChecker; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
