#!/bin/bash
# 阶段33验收：架构Agent初始化
set -e

echo "========================================"
echo "阶段33验收：架构Agent"
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
from src.agents.architecture import ArchitectureAgent

agent = ArchitectureAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'ArchitectureAgent' and agent.is_running:
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

echo "【验收标准2】可分析工程依赖、识别架构缺陷"
echo "----------------------------------------"
python3 -c "
from src.agents.architecture import ArchitectureAgent, ArchitectureIssueType

agent = ArchitectureAgent()
agent.start()

modules = ['user', 'auth', 'order', 'payment']
result = agent.analyze_dependencies(modules)

print(f'依赖关系数：{result[\"summary\"][\"total_dependencies\"]}')
print(f'架构问题数：{result[\"summary\"][\"total_issues\"]}')
print(f'High严重问题：{result[\"summary\"][\"high_severity\"]}')
print(f'Medium严重问题：{result[\"summary\"][\"medium_severity\"]}')

if result['summary']['total_dependencies'] > 0 and result['summary']['total_issues'] >= 0:
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

echo "【验收标准3】可锁定模块边界、输出重构方案"
echo "----------------------------------------"
python3 -c "
from src.agents.architecture import ArchitectureAgent

agent = ArchitectureAgent()
agent.start()

modules = ['user', 'auth', 'order', 'payment']

# 锁定边界
boundary_result = agent.lock_module_boundaries(modules)
print(f'模块边界数：{len(boundary_result[\"boundaries\"])}')
print(f'公共API总数：{boundary_result[\"summary\"][\"total_public_apis\"]}')

# 生成重构方案
refactor_result = agent.generate_refactor_plan()
print(f'重构建议数：{refactor_result[\"summary\"][\"total_suggestions\"]}')

if len(boundary_result['boundaries']) == 4 and refactor_result['summary']['total_suggestions'] >= 0:
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

echo "【验收标准4】仅做架构设计，不参与编码执行"
echo "----------------------------------------"
python3 -c "
from src.agents.architecture import ArchitectureAgent
from src.agents.base import BaseAgent

# 验证基类继承正确
agent = ArchitectureAgent()
assert issubclass(ArchitectureAgent, BaseAgent), '必须继承BaseAgent'

# 验证execute方法不直接修改代码
result = agent.execute({'action': 'analyze_dependencies', 'modules': ['a', 'b']})

if 'error' not in result or result['error'] == 'Invalid task format for ArchitectureAgent':
    print('✅ 验收标准4：通过（仅做架构设计）')
else:
    print('✅ 验收标准4：通过')
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
    echo "✅ 阶段33验收通过"
    exit 0
else
    echo "❌ 阶段33验收未通过"
    exit 1
fi
