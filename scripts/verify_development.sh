#!/bin/bash
# 阶段34验收：开发Agent初始化
set -e

echo "========================================"
echo "阶段34验收：开发Agent"
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
from src.agents.development import DevelopmentAgent

agent = DevelopmentAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'DevelopmentAgent' and agent.is_running:
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

echo "【验收标准2】支持代码新增、修改、重构、修复操作"
echo "----------------------------------------"
python3 -c "
from src.agents.development import DevelopmentAgent, CodeOperationType, ChangeStatus

agent = DevelopmentAgent()
agent.start()

# 1. 创建文件
change1 = agent.create_file('/tmp/test_dev.py', 'test = 123', '创建测试文件')
assert change1.operation == CodeOperationType.NEW_FILE

# 2. 修改文件
change2 = agent.modify_file('/tmp/test_dev.py', 1, 'test = 123', 'test = 456', '修改值')
assert change2.operation == CodeOperationType.MODIFY

# 3. 重构
change3 = agent.refactor_code('/tmp/test_dev.py', '重构测试代码', 'rename')
assert change3.operation == CodeOperationType.REFACTOR

# 4. 修复
change4 = agent.fix_issue('/tmp/test_dev.py', 1, '修复问题', 'test = 789')
assert change4.operation == CodeOperationType.FIX

print(f'创建：{change1.operation.value}')
print(f'修改：{change2.operation.value}')
print(f'重构：{change3.operation.value}')
print(f'修复：{change4.operation.value}')

if len(agent.pending_changes) == 4:
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

echo "【验收标准3】严格遵循原子化规范编码"
echo "----------------------------------------"
python3 -c "
from src.agents.development import DevelopmentAgent

agent = DevelopmentAgent()
agent.start()

# 创建符合规范的代码
good_code = ''''''\"\"\"演示模块\"\"\"

def good_function(name: str) -> str:
    \"\"\"好的函数\"\"\"
    return f'Hello {name}'
''''''
change1 = agent.create_file('/tmp/good.py', good_code, '符合规范')
print(f'符合规范的代码：验证错误数={len(change1.validation_errors)}')

# 创建可能有问题的代码
bad_code = '''temp = 123
x = temp + 456'''
change2 = agent.create_file('/tmp/bad.py', bad_code, '可能有问题')
print(f'简单代码：验证建议数（如果有）')

if len(change1.validation_errors) == 0:
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

echo "【验收标准4】无越权修改架构、无违规改动依赖"
echo "----------------------------------------"
python3 -c "
from src.agents.development import DevelopmentAgent, ChangeStatus

agent = DevelopmentAgent()
agent.start()

# 尝试修改架构（应该被拒绝）
arch_change = agent.modify_file(
    '/tmp/arch.py',
    1,
    'old',
    'class NewAgent:',
    '尝试添加Agent类'
)
print(f'架构修改状态：{arch_change.status.value}')
print(f'架构修改错误：{arch_change.validation_errors}')

# 尝试修改依赖（应该被拒绝）
dep_change = agent.modify_file(
    '/tmp/dep.py',
    1,
    'old',
    'import sys',
    '尝试添加导入'
)
print(f'依赖修改状态：{dep_change.status.value}')
print(f'依赖修改错误：{dep_change.validation_errors}')

if arch_change.status == ChangeStatus.REJECTED and dep_change.status == ChangeStatus.REJECTED:
    print('✅ 验收标准4：通过')
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
    echo "✅ 阶段34验收通过"
    exit 0
else
    echo "❌ 阶段34验收未通过"
    exit 1
fi
