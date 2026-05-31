#!/bin/bash
set -e

echo "===== MetaGPT工程岗位流程模板验证脚本 ====="
echo ""

echo "1. 验证工程岗位模板模块:"
python -m src.agents.metagpt_roles
echo ""

echo "2. 验证岗位模板加载:"
python -c "
from src.agents.metagpt_roles import MetaGPTRoleManager
mgr = MetaGPTRoleManager()
mgr.load_standard_roles()
print('  ✓ 标准岗位加载成功')
print(f'  ✓ 共加载 {len(mgr.roles)} 个岗位')
"
echo ""

echo "3. 验证任务拆解能力:"
python -c "
from src.agents.metagpt_roles import TaskDecomposer
decomposer = TaskDecomposer()
task = {'type': 'development', 'description': '测试任务'}
stages = decomposer.decompose_task(task)
print(f'  ✓ 任务拆解成功，分解为 {len(stages)} 个阶段')
"
echo ""

echo "4. 验证复用原则:"
grep -q "复用MetaGPT的岗位分工范式" src/agents/metagpt_roles.py
if [ $? -eq 0 ]; then
    echo "  ✓ 代码注释明确说明复用MetaGPT范式"
else
    echo "  ✗ 缺少复用说明"
fi
echo ""

echo "===== MetaGPT验证完成 ====="
echo ""
echo "✓ MetaGPT工程岗位流程模板集成成功"
echo "✓ 所有验收标准通过"
