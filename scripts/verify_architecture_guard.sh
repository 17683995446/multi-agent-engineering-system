#!/bin/bash
set -e

echo "===== 阶段20：架构底层约束固化验证 ====="
echo ""

echo "1. 验证架构守卫模块:"
python -m src.common.architecture_guard
echo ""

echo "2. 验证导入:"
python -c "from src.common.architecture_guard import ArchitectureGuard, ArchitectureEnforcer, ArchitectureAxiom; print('✓ 架构守卫模块导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.architecture_guard import ArchitectureGuard, ArchitectureAxiom, ArchitectureBaseline

guard = ArchitectureGuard()

baseline = ArchitectureBaseline(
    name='TestBaseline',
    version='0.1.0',
    axioms=set(ArchitectureAxiom)
)
guard.register_baseline(baseline)
guard.lock_baseline('TestBaseline')

context1 = {'dependencies': {'a': ['b'], 'b': ['a']}}
violations = guard.validate(context1)
print(f'✓ 违规检测: 检测到 {len(violations)} 个违规')

allowed = guard.is_operation_allowed({'dependencies': {'input': ['output'], 'output': []}})
print(f'✓ 操作验证: {allowed}')

stats = guard.get_violation_statistics()
print(f'✓ 统计信息: {stats}')
"
echo ""

echo "4. 验证架构基线锁定:"
python -c "
from src.common.architecture_guard import ArchitectureGuard, ArchitectureBaseline

guard = ArchitectureGuard()

baseline = ArchitectureBaseline(
    name='LockedBaseline',
    version='1.0.0',
    axioms=set()
)
guard.register_baseline(baseline)
guard.lock_baseline('LockedBaseline')

try:
    guard.register_baseline(ArchitectureBaseline(
        name='LockedBaseline',
        version='2.0.0',
        axioms=set()
    ))
    print('✗ 错误: 基线被覆盖了')
except PermissionError:
    print('✓ 正确: 锁定的基线不可覆盖')
"
echo ""

echo "===== 验证完成 ====="
