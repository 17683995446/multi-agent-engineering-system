#!/bin/bash
set -e

echo "===== 阶段13：三层状态隔离验证脚本 ====="
echo ""

echo "1. 验证三层状态管理模块:"
python -m src.common.state_manager
echo ""

echo "2. 验证导入:"
python -c "from src.common.state_manager import StateManager, TaskState, BusinessState, SystemState; print('✓ StateManager 导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.state_manager import StateManager, TaskStatus, BusinessStatus, SystemStatus

manager = StateManager()

manager.create_task_state('test_task', TaskStatus.PENDING)
manager.update_task_state('test_task', status=TaskStatus.RUNNING)

manager.create_business_state('test_order', BusinessStatus.INITIAL)
manager.update_business_state('test_order', status=BusinessStatus.PROCESSING)

manager.create_system_state('test_system', SystemStatus.HEALTHY)
manager.update_system_state('test_system', status=SystemStatus.HEALTHY, metrics={'cpu': 0.5})

task = manager.get_task_state('test_task')
business = manager.get_business_state('test_order')
system = manager.get_system_state('test_system')

history = manager.get_all_history()
isolation = manager.verify_state_isolation()

print(f'✓ 任务状态: {task.status.value}')
print(f'✓ 业务状态: {business.status.value}')
print(f'✓ 系统状态: {system.status.value}')
print(f'✓ 状态变更历史: {len(history)} 条')
print(f'✓ 状态隔离验证: {\"通过\" if isolation[\"isolation_verified\"] else \"失败\"}')"
echo ""

echo "4. 验证状态分离公理:"
grep -q "遵循第一性原理：状态分离公理" /workspace/src/common/state_manager.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明状态分离公理"
else
    echo "   ✗ 缺少状态分离公理说明"
fi
echo ""

echo "===== 验证完成 ====="
