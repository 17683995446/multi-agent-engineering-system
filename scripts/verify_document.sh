#!/bin/bash
# 阶段38验收：文档Agent初始化
set -e

echo "========================================"
echo "阶段38验收：文档Agent"
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
from src.agents.document import DocumentAgent

agent = DocumentAgent()
agent.start()

print(f'Agent名称: {agent.name}')
print(f'运行状态: {agent.is_running}')

if agent.name == 'DocumentAgent' and agent.is_running:
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

echo "【验收标准2】自动生成需求&设计文档"
echo "----------------------------------------"
python3 -c "
from src.agents.document import DocumentAgent, DocumentType

agent = DocumentAgent()
agent.start()

# 生成需求文档
req_doc = agent.generate_requirement_document(
    '测试功能模块',
    '测试描述内容',
    ['标准1', '标准2'],
    ['依赖A', '依赖B']
)
print(f'✅ 需求文档创建: {req_doc.title}')
print(f'   类型: {req_doc.doc_type.value}')

# 生成设计文档
design_doc = agent.generate_design_document(
    '测试模块',
    '架构概述内容',
    [
        {
            'name': 'Module1',
            'responsibility': '测试职责',
            'interfaces': 'test()'
        }
    ]
)
print(f'✅ 设计文档创建: {design_doc.title}')
print(f'   类型: {design_doc.doc_type.value}')

if req_doc.doc_type == DocumentType.REQUIREMENT and design_doc.doc_type == DocumentType.DESIGN:
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

echo "【验收标准3】文档归档与版本化"
echo "----------------------------------------"
python3 -c "
from src.agents.document import DocumentAgent, DocumentStatus, DocumentType

agent = DocumentAgent()
agent.start()

# 创建初始文档
doc = agent.create_document(DocumentType.REQUIREMENT, '测试文档', '初始内容')
print(f'✅ 文档创建: {doc.title}')
print(f'   初始版本: {doc.current_version}')

# 更新文档
agent.update_document(doc.doc_id, '更新后的内容', '第一次更新')
doc_updated = agent.get_document(doc.doc_id)
print(f'✅ 文档更新到版本: {doc_updated.current_version}')
print(f'   版本数: {len(doc_updated.versions)}')

# 归档文档
success = agent.archive_document(doc.doc_id)
doc_archived = agent.get_document(doc.doc_id)
print(f'✅ 文档归档成功: {success}')
print(f'   状态: {doc_archived.status.value}')

if doc_archived.status == DocumentStatus.ARCHIVED and len(doc_archived.versions) >= 2:
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

echo "【验收标准4】代码变更触发文档更新"
echo "----------------------------------------"
python3 -c "
from src.agents.document import DocumentAgent

agent = DocumentAgent()
agent.start()

# 记录代码变更
change1 = agent.record_code_change('/test/file1.py', 'add')
print(f'✅ 记录变更 1: {change1.change_id}')

change2 = agent.record_code_change('/test/file2.py', 'modify', '旧内容', '新内容')
print(f'✅ 记录变更 2: {change2.change_id}')

# 生成变更日志
changelog = agent.generate_changelog()
print(f'✅ 变更日志生成: {changelog.title}')
print(f'   变更数: {len(agent.change_history)}')

if len(agent.change_history) >= 2:
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
    echo "✅ 阶段38验收通过"
    exit 0
else
    echo "❌ 阶段38验收未通过"
    exit 1
fi
