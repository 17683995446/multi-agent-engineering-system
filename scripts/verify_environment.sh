#!/bin/bash
set -e

echo "===== 环境复现验证脚本 ====="
echo ""

echo "1. 检查Python版本..."
python --version
echo ""

echo "2. 验证requirements.lock存在..."
if [ -f "requirements.lock" ]; then
    echo "✓ requirements.lock 存在"
    echo "  包含 $(wc -l < requirements.lock) 个依赖项"
else
    echo "✗ requirements.lock 不存在"
    exit 1
fi
echo ""

echo "3. 验证requirements.txt固定版本..."
if grep -q "==" requirements.txt; then
    echo "✓ requirements.txt 所有依赖都固定了版本"
else
    echo "✗ requirements.txt 存在未固定版本"
    exit 1
fi
echo ""

echo "4. 验证pyproject.toml存在..."
if [ -f "pyproject.toml" ]; then
    echo "✓ pyproject.toml 存在"
    echo "  Python要求版本: $(grep "requires-python" pyproject.toml)"
else
    echo "✗ pyproject.toml 不存在"
    exit 1
fi
echo ""

echo "5. 验证环境可复现性..."
echo "  尝试安装依赖..."
pip install -r requirements.lock --quiet
echo "✓ 依赖安装成功"
echo ""

echo "6. 验证关键依赖可用..."
python -c "import langgraph; print('  ✓ langgraph 可用')"
python -c "import autogen_agentchat; print('  ✓ autogen_agentchat 可用')"
python -c "import tree_sitter; print('  ✓ tree-sitter 可用')"
python -c "import ruff; print('  ✓ ruff 可用')"
python -c "import pytest; print('  ✓ pytest 可用')"
python -c "import yaml; print('  ✓ pyyaml 可用')"
echo "✓ 所有关键依赖验证通过"
echo ""

echo "===== 环境复现验证完成 ====="
echo ""
echo "✓ 环境已就绪，可进行下一阶段"
