#!/bin/bash
set -e

echo "===== 阶段23：方法四段式结构验证 ====="
echo ""

echo "1. 运行四段式重构器演示"
python -m src.code.method_four_section
echo ""

echo "2. 验证模块导入"
python -c "from src.code.method_four_section import FourSectionAnalyzer, FourSectionRefactorer; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
