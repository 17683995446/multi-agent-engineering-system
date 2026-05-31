#!/bin/bash
set -e

echo "===== 阶段17：全局错误码体系验证脚本 ====="
echo ""

echo "1. 验证错误码模块:"
python -m src.common.error_code
echo ""

echo "2. 验证导入:"
python -c "from src.common.error_code import SystemException, ErrorCodeRegistry, ErrorStatistics, ErrorInfo; print('✓ 错误码体系导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.error_code import ErrorCodeRegistry, ErrorStatistics, ErrorInfo, ErrorCategory, ErrorSeverity

registry = ErrorCodeRegistry()

all_codes = registry.get_all_codes()
print(f'✓ 错误码总数: {len(all_codes)} 个')

codes_by_category = {}
for cat in ErrorCategory:
    codes = registry.get_codes_by_category(cat)
    codes_by_category[cat.value] = len(codes)
print(f'✓ 分类统计: {codes_by_category}')

stats = ErrorStatistics()
test_errors = [
    ErrorInfo('TSK-3001-00', 'task', 'high', '任务不存在'),
    ErrorInfo('SYS-1001-00', 'system', 'critical', '系统初始化失败'),
]
for error in test_errors:
    stats.record(error)
print(f'✓ 错误统计: 总数={stats.get_total()}, 按分类={stats._by_category}')
"
echo ""

echo "4. 验证错误码原则:"
grep -q "全局唯一错误码体系" /workspace/src/common/error_code.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明错误码体系"
else
    echo "   ✗ 缺少错误码体系说明"
fi
echo ""

echo "===== 验证完成 ====="
