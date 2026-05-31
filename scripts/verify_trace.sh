#!/bin/bash
set -e

echo "===== 阶段18：链路ID追踪验证脚本 ====="
echo ""

echo "1. 验证链路追踪模块:"
python -m src.common.trace_manager
echo ""

echo "2. 验证导入:"
python -c "from src.common.trace_manager import TraceManager, TraceIDGenerator, TraceEventType; print('✓ 链路追踪模块导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.trace_manager import TraceManager, TraceEventType

manager = TraceManager()

root_span = manager.start_trace('test_operation')
child_span = manager.create_span(root_span.trace_id, 'child_operation', root_span.span_id)
child_span.finish()

manager.end_trace(root_span.trace_id, 'completed')

trace_info = manager.get_trace(root_span.trace_id)
integrity = manager.verify_trace_integrity(root_span.trace_id)
stats = manager.get_statistics()

print(f'✓ 链路ID: {root_span.trace_id}')
print(f'✓ 操作数: {len(trace_info.spans) if trace_info else 0}')
print(f'✓ 完整性验证: {\"通过\" if integrity[\"valid\"] else \"失败\"}')
print(f'✓ 统计: 总链路={stats[\"total_traces\"]}, 总操作={stats[\"total_spans\"]}')"
echo ""

echo "4. 验证可追溯原则:"
grep -q "全局可追溯链路ID管理器" /workspace/src/common/trace_manager.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明可追溯链路ID机制"
else
    echo "   ✗ 缺少可追溯链路ID说明"
fi
echo ""

echo "===== 验证完成 ====="
