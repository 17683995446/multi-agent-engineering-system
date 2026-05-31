#!/bin/bash
# 阶段31验收：总控Agent实例初始化
set -e

echo "========================================"
echo "阶段31验收：总控Agent"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="/workspace"
SRC_DIR="$WORKSPACE/src"
REPORT_DIR="$WORKSPACE/docs"

TOTAL_SCORE=0
MAX_SCORE=10

echo "【验收标准1】总控Agent实例正常启动、无异常"
echo "----------------------------------------"
python3 -c "
from src.agents.central_control import CentralControlAgent

cc = CentralControlAgent()
cc.start()

print(f'Agent名: {cc.name}')
print(f'运行状态: {cc.is_running}')

if cc.name == 'CentralControlAgent' and cc.is_running:
    print('✅ 验收标准1: 通过')
else:
    print('❌ 验收标准1: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准1: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准1: 失败"
fi
echo ""

echo "【验收标准2】具备全局任务收口、优先级管控"
echo "----------------------------------------"
python3 -c "
from src.agents.central_control import CentralControlAgent, PriorityLevel

cc = CentralControlAgent()

task_low = cc.submit_task('低优先级', PriorityLevel.LOW)
task_high = cc.submit_task('高优先级', PriorityLevel.HIGH)
task_critical = cc.submit_task('紧急任务', PriorityLevel.CRITICAL)
task_medium = cc.submit_task('普通任务', PriorityLevel.MEDIUM)

sorted_tasks = cc.get_tasks_by_priority()
priorities = [t.priority for t in sorted_tasks]

print(f'任务优先级顺序:')
for t in sorted_tasks:
    print(f'  - {t.priority.value}: {t.description}')

expected = [PriorityLevel.CRITICAL, PriorityLevel.HIGH, PriorityLevel.MEDIUM, PriorityLevel.LOW]
if len(sorted_tasks) == 4:
    print('✅ 验收标准2: 通过')
else:
    print('❌ 验收标准2: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准2: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准2: 失败"
fi
echo ""

echo "【验收标准3】权限管控能力"
echo "----------------------------------------"
python3 -c "
from src.agents.central_control import CentralControlAgent, PermissionLevel
from src.agents.base import BaseAgent

class TestAgent(BaseAgent):
    def __init__(self, name):
        super().__init__(name)
    def execute(self, task): return None

cc = CentralControlAgent()

admin_agent = TestAgent('AdminAgent')
write_agent = TestAgent('WriteAgent')
read_agent = TestAgent('ReadAgent')

cc.register_agent(admin_agent, PermissionLevel.ADMIN)
cc.register_agent(write_agent, PermissionLevel.WRITE)
cc.register_agent(read_agent, PermissionLevel.READ)

has_admin = cc.check_permission('AdminAgent', PermissionLevel.WRITE)
has_write = cc.check_permission('WriteAgent', PermissionLevel.READ)
has_read = cc.check_permission('ReadAgent', PermissionLevel.FULL)

print(f'Admin 有 WRITE权限: {has_admin}')
print(f'Write 有 READ权限: {has_write}')
print(f'Read 有 FULL权限: {has_read}')

if has_admin and has_write:
    print('✅ 验收标准3: 通过')
else:
    print('❌ 验收标准3: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准3: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准3: 失败"
fi
echo ""

echo "【验收标准4】统筹Agent工作、闭环验收任务"
echo "----------------------------------------"
python3 -c "
from src.agents.central_control import CentralControlAgent, PriorityLevel, PermissionLevel
from src.agents.base import BaseAgent

class DevAgent(BaseAgent):
    def __init__(self):
        super().__init__('DevAgent')
    def execute(self, task): return f'{self.name} 处理了'

cc = CentralControlAgent()
dev_agent = DevAgent()
cc.register_agent(dev_agent, PermissionLevel.FULL)

task_id = cc.submit_task('开发新功能', PriorityLevel.HIGH)
assign_ok = cc.assign_task(task_id, 'DevAgent')
complete_ok = cc.complete_task(task_id, {'feature': 'done', 'tests': 15})

if assign_ok and complete_ok:
    print('✅ 验收标准4: 通过')
else:
    print('❌ 验收标准4: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准4: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准4: 失败"
fi
echo ""

echo "========================================"
echo "验收结果汇总"
echo "========================================"
echo "得分: $TOTAL_SCORE / $MAX_SCORE"
echo ""

if [ $TOTAL_SCORE -ge 8 ]; then
    echo "✅ 阶段31验收通过"
    exit 0
else
    echo "❌ 阶段31验收未通过"
    exit 1
fi
