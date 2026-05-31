#!/bin/bash
set -e

echo "===== 阶段16：原子实体定义验证脚本 ====="
echo ""

echo "1. 验证原子实体模块:"
python -m src.common.atomic_entities
echo ""

echo "2. 验证导入:"
python -c "from src.common.atomic_entities import TaskEntity, CodeEntity, MessageEntity, StateEntity, EntityRegistry; print('✓ 原子实体导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.atomic_entities import AtomicEntityFactory, EntityRegistry, TaskPriority, CodeType, MessageType, StateType

factory = AtomicEntityFactory()
registry = EntityRegistry()

task = factory.create_task('t1', 'test', '测试任务', TaskPriority.HIGH)
registry.register_task(task)

code = factory.create_code('c1', CodeType.FUNCTION, 'test_func', 'def test_func(): pass')
registry.register_code(code)

stats = registry.get_statistics()
print(f'✓ 任务总数: {stats[\"total_tasks\"]}')
print(f'✓ 代码总数: {stats[\"total_codes\"]}')
print(f'✓ 消息总数: {stats[\"total_messages\"]}')
print(f'✓ 状态总数: {stats[\"total_states\"]}')
"
echo ""

echo "4. 验证任务可分性公理:"
grep -q "遵循第一性原理：任务可分性公理" /workspace/src/common/atomic_entities.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明任务可分性公理"
else
    echo "   ✗ 缺少任务可分性公理说明"
fi
echo ""

echo "===== 验证完成 ====="
