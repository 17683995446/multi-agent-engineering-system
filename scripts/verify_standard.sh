#!/bin/bash
set -e

echo "===== 阶段15：全局规范体系验证脚本 ====="
echo ""

echo "1. 验证全局规范管理模块:"
python -m src.common.global_standard
echo ""

echo "2. 验证导入:"
python -c "from src.common.global_standard import GlobalStandardManager; print('✓ GlobalStandardManager 导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.global_standard import GlobalStandardManager

manager = GlobalStandardManager()

code_rules = manager.get_code_standards()
task_rules = manager.get_task_standards()
collab_rules = manager.get_collaboration_standards()
doc_rules = manager.get_document_standards()

print(f'✓ 代码规范: {len(code_rules)} 个规则')
print(f'✓ 任务规范: {len(task_rules)} 个规则')
print(f'✓ 协作规范: {len(collab_rules)} 个规则')
print(f'✓ 文档规范: {len(doc_rules)} 个规则')

report = manager.generate_compliance_report()
print(f'✓ 代码合规: {report.code_compliance}%')
print(f'✓ 任务合规: {report.task_compliance}%')
print(f'✓ 协作合规: {report.collaboration_compliance}%')
print(f'✓ 文档合规: {report.document_compliance}%')
"
echo ""

echo "4. 验证最小熵规范原则:"
grep -q "遵循第一性原理：最小熵全局规范体系" /workspace/src/common/global_standard.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明最小熵规范体系"
else
    echo "   ✗ 缺少最小熵规范体系说明"
fi
echo ""

echo "===== 验证完成 ====="
