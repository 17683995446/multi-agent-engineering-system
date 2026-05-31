#!/bin/bash
set -e

echo "===== 项目目录架构验证脚本 ====="
echo ""

echo "1. 检查四层架构目录..."
echo ""

echo "   [第1层] 输入层 src/input/"
if [ -d "src/input" ]; then
    echo "   ✓ src/input 存在"
    if [ -f "src/input/__init__.py" ]; then
        echo "   ✓ src/input/__init__.py 存在"
    else
        echo "   ✗ src/input/__init__.py 缺失"
        exit 1
    fi
else
    echo "   ✗ src/input 目录缺失"
    exit 1
fi
echo ""

echo "   [第2层] 调度层 src/workflow/"
if [ -d "src/workflow" ]; then
    echo "   ✓ src/workflow 存在"
    if [ -f "src/workflow/__init__.py" ]; then
        echo "   ✓ src/workflow/__init__.py 存在"
    else
        echo "   ✗ src/workflow/__init__.py 缺失"
        exit 1
    fi
else
    echo "   ✗ src/workflow 目录缺失"
    exit 1
fi
echo ""

echo "   [第3层] 协作层 src/agents/"
if [ -d "src/agents" ]; then
    echo "   ✓ src/agents 存在"
    if [ -f "src/agents/__init__.py" ]; then
        echo "   ✓ src/agents/__init__.py 存在"
    else
        echo "   ✗ src/agents/__init__.py 缺失"
        exit 1
    fi
else
    echo "   ✗ src/agents 目录缺失"
    exit 1
fi
echo ""

echo "   [第4层] 执行层 src/code/"
if [ -d "src/code" ]; then
    echo "   ✓ src/code 存在"
    if [ -f "src/code/__init__.py" ]; then
        echo "   ✓ src/code/__init__.py 存在"
    else
        echo "   ✗ src/code/__init__.py 缺失"
        exit 1
    fi
else
    echo "   ✗ src/code 目录缺失"
    exit 1
fi
echo ""

echo "   [公共层] src/common/"
if [ -d "src/common" ]; then
    echo "   ✓ src/common 存在"
    if [ -f "src/common/__init__.py" ]; then
        echo "   ✓ src/common/__init__.py 存在"
    else
        echo "   ✗ src/common/__init__.py 缺失"
        exit 1
    fi
else
    echo "   ✗ src/common 目录缺失"
    exit 1
fi
echo ""

echo "2. 检查其他必要目录..."
echo ""

dirs=("tests" "docs" "scripts" "configs")
for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "   ✓ $dir/ 存在"
    else
        echo "   ✗ $dir/ 目录缺失"
        exit 1
    fi
done
echo ""

echo "3. 验证单向依赖规则..."
echo ""

echo "   检查跨层级反向依赖（应该为空）..."
# 检查下层是否引用了上层
reverse_deps=$(grep -r "from src.input" src/workflow src/agents src/code 2>/dev/null || true)
if [ -n "$reverse_deps" ]; then
    echo "   ✗ 发现反向依赖："
    echo "$reverse_deps"
    exit 1
else
    echo "   ✓ 无 input → workflow/agents/code 反向依赖"
fi

reverse_deps=$(grep -r "from src.workflow" src/agents src/code 2>/dev/null || true)
if [ -n "$reverse_deps" ]; then
    echo "   ✗ 发现反向依赖："
    echo "$reverse_deps"
    exit 1
else
    echo "   ✓ 无 workflow → agents/code 反向依赖"
fi

reverse_deps=$(grep -r "from src.agents" src/code 2>/dev/null || true)
if [ -n "$reverse_deps" ]; then
    echo "   ✗ 发现反向依赖："
    echo "$reverse_deps"
    exit 1
else
    echo "   ✓ 无 agents → code 反向依赖"
fi
echo ""

echo "4. 验证架构文档..."
if [ -f "src/ARCHITECTURE.py" ]; then
    echo "   ✓ src/ARCHITECTURE.py 存在"
else
    echo "   ✗ src/ARCHITECTURE.py 缺失"
    exit 1
fi
echo ""

echo "5. 显示最终目录结构..."
echo ""
tree -L 3 -I '__pycache__|*.pyc|.pytest_cache' src/ 2>/dev/null || find src/ -maxdepth 3 -type f -name "*.py" | sort
echo ""

echo "===== 目录架构验证完成 ====="
echo ""
echo "✓ 所有目录结构符合四层架构要求"
echo "✓ 单向依赖规则验证通过"
echo "✓ 目录架构验收通过"
