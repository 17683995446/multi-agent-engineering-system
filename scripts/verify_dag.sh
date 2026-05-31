#!/bin/bash
set -e

echo "===== 阶段12：全局DAG单向依赖校验验证脚本 ====="
echo ""

echo "1. 验证DAG依赖校验模块:"
python -m src.common.dag_checker
echo ""

echo "2. 验证导入:"
python -c "from src.common.dag_checker import DAGDependencyChecker; print('✓ DAGDependencyChecker 导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.dag_checker import DAGDependencyChecker
from pathlib import Path

project_root = Path('/workspace')
checker = DAGDependencyChecker(str(project_root))
result = checker.run_full_check()

print(f'总节点数: {result[\"total_nodes\"]}')
print(f'总边数: {result[\"total_edges\"]}')
print(f'循环依赖: {len(result[\"circular_dependencies\"])} 个')
print(f'双向依赖: {len(result[\"bidirectional_dependencies\"])} 对')
print(f'层级依赖合规: {\"✓\" if result[\"layer_dependency_valid\"] else \"✗\"}')
print(f'总体通过: {\"✓\" if result[\"passed\"] else \"✗\"}')
"
echo ""

echo "4. 验证第一性原理依赖单向性公理:"
grep -q "遵循第一性原理：依赖单向性公理" /workspace/src/common/dag_checker.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明依赖单向性公理"
else
    echo "   ✗ 缺少依赖单向性公理说明"
fi
echo ""

echo "===== 验证完成 ====="
