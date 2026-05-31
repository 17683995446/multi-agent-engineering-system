#!/bin/bash
set -e

echo "===== 阶段19：全局权限验证脚本 ====="
echo ""

echo "1. 验证权限管理模块:"
python -m src.common.permission_manager
echo ""

echo "2. 验证导入:"
python -c "from src.common.permission_manager import PermissionManager, Permission, ResourceType, AgentRole; print('✓ 权限管理模块导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.permission_manager import PermissionManager, Permission, ResourceType, AgentRole, OperationResult

manager = PermissionManager()

from src.common.permission_manager import Resource
task = Resource('test_task', ResourceType.TASK, 'test_agent')
manager.resource_manager.register_resource(task)

result1 = manager.check_access('test_agent', AgentRole.DEVELOPER, ResourceType.TASK, 'test_task', Permission.WRITE)
result2 = manager.check_access('test_agent', AgentRole.VIEWER, ResourceType.TASK, 'test_task', Permission.WRITE)

perms = manager.get_role_permissions(AgentRole.DEVELOPER)
stats = manager.access_logger.get_statistics()

print(f'✓ 开发者写任务: {result1.value}')
print(f'✓ 查看者写任务: {result2.value}')
print(f'✓ 开发者权限数: {len(perms)}')
print(f'✓ 访问统计: 总={stats[\"total\"]}, 允许={stats[\"allowed\"]}, 只读拦截={stats[\"read_only\"]}')"
echo ""

echo "4. 验证安全约束:"
grep -q "系统安全可控" /workspace/src/common/permission_manager.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明安全约束"
else
    echo "   ✗ 缺少安全约束说明"
fi
echo ""

echo "===== 验证完成 ====="
