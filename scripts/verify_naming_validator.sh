#!/bin/bash
set -e

echo "===== 阶段28：命名规范全链路校验 ====="
echo ""

echo "1. 运行命名规范全链路校验器演示"
python -m src.code.naming_validator
echo ""

echo "2. 验证模块导入"
python -c "from src.code.naming_validator import NamingValidator, NamingCheckResult; print('✓ 模块导入成功')"
echo ""

echo "===== 验证完成 ====="
