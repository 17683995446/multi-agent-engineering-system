#!/bin/bash
set -e

echo "===== 阶段25：类单一能力校验验证 ====="
echo ""

echo "1. 运行类单一能力校验器演示"
python -m src.code.class_single_ability_checker
echo ""

echo "2. 验证模块导入"
python -c "from src.code.class_single_ability_checker import ClassSingleAbilityAnalyzer, ClassCouplingAnalyzer; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
