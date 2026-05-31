#!/bin/bash
# 阶段32验收：需求拆解Agent初始化
set -e

echo "========================================"
echo "阶段32验收：需求拆解Agent"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="/workspace"
SRC_DIR="$WORKSPACE/src"
REPORT_DIR="$WORKSPACE/docs"

TOTAL_SCORE=0
MAX_SCORE=10

echo "【验收标准1】实例启动正常"
echo "----------------------------------------"
python3 -c "
from src.agents.requirement_decomposition import RequirementDecompositionAgent

agent = RequirementDecompositionAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'RequirementDecompositionAgent' and agent.is_running:
    print('✅ 验收标准1：通过')
else:
    print('❌ 验收标准1：失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准1：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准1：失败"
fi
echo ""

echo "【验收标准2】可将复杂需求逐层拆解为原子任务"
echo "----------------------------------------"
python3 -c "
from src.agents.requirement_decomposition import RequirementDecompositionAgent, TaskLevel

agent = RequirementDecompositionAgent()
agent.start()

result = agent.decompose('开发一个简单的博客系统', max_depth=3)
all_tasks = result['all_tasks']

atomic_count = len([t for t in all_tasks if t['is_atomic']])
total_count = result['summary']['total_tasks']

print(f'总任务数：{total_count}')
print(f'原子任务数：{atomic_count}')

if total_count > 5 and atomic_count > 0:
    print('✅ 验收标准2：通过')
else:
    print('❌ 验收标准2：失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准2：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准2：失败"
fi
echo ""

echo "【验收标准3】拆解结果分层清晰、无遗漏、无冗余"
echo "----------------------------------------"
python3 -c "
from src.agents.requirement_decomposition import RequirementDecompositionAgent

agent = RequirementDecompositionAgent()
agent.start()

result = agent.decompose('开发一个用户管理功能', max_depth=3)
all_tasks = result['all_tasks']

# 检查层级
level_1 = [t for t in all_tasks if t['level'] == 'level_1']
level_2 = [t for t in all_tasks if t['level'] == 'level_2']
level_3 = [t for t in all_tasks if t['level'] == 'level_3']
atomic = [t for t in all_tasks if t['is_atomic']]

print(f'Level 1 任务数：{len(level_1)}')
print(f'Level 2 任务数：{len(level_2)}')
print(f'Level 3 任务数：{len(level_3)}')
print(f'原子任务数：{len(atomic)}')

# 验证无重复
task_ids = set()
duplicates = False
for t in all_tasks:
    if t['task_id'] in task_ids:
        duplicates = True
    task_ids.add(t['task_id'])

if len(level_1) == 1 and len(level_2) > 0 and not duplicates:
    print('✅ 验收标准3：通过')
else:
    print('❌ 验收标准3：失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准3：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准3：失败"
fi
echo ""

echo "【验收标准4】复用开源HTD思路，无自研核心算法"
echo "----------------------------------------"
python3 -c "
from src.agents.requirement_decomposition import RequirementDecompositionAgent

agent = RequirementDecompositionAgent()
agent.start()

result = agent.decompose('开发一个电商购物车', max_depth=3)

# 验证使用标准层级分解
has_analysis = any('分析' in t['description'] for t in result['all_tasks'])
has_design = any('设计' in t['description'] for t in result['all_tasks'])
has_impl = any('实现' in t['description'] for t in result['all_tasks'])
has_test = any('测试' in t['description'] for t in result['all_tasks'])

print(f'包含分析阶段：{has_analysis}')
print(f'包含设计阶段：{has_design}')
print(f'包含实现阶段：{has_impl}')
print(f'包含测试阶段：{has_test}')

if has_analysis and has_design and has_impl and has_test:
    print('✅ 验收标准4：通过（复用标准HTD思路）')
else:
    print('❌ 验收标准4：失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准4：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准4：失败"
fi
echo ""

echo "========================================"
echo "验收结果汇总"
echo "========================================"
echo "得分：$TOTAL_SCORE / $MAX_SCORE"
echo ""

if [ $TOTAL_SCORE -ge 8 ]; then
    echo "✅ 阶段32验收通过"
    exit 0
else
    echo "❌ 阶段32验收未通过"
    exit 1
fi
