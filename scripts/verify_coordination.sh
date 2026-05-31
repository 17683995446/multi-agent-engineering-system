#!/bin/bash
# 阶段39验收：协调Agent初始化
set -e

echo "========================================"
echo "阶段39验收：协调Agent"
echo "========================================"
echo ""

WORKSPACE="/workspace"
SRC_DIR="$WORKSPACE/src"
TOTAL_SCORE=0
MAX_SCORE=10

echo "【验收标准1】实例启动正常"
echo "----------------------------------------"
python3 -c "
from src.agents.coordination import CoordinationAgent

agent = CoordinationAgent()
agent.start()

print(f'Agent名称: {agent.name}')
print(f'运行状态: {agent.is_running}')

if agent.name == 'CoordinationAgent' and agent.is_running:
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

echo "【验收标准2】多Agent工作流编排能力"
echo "----------------------------------------"
python3 -c "
from src.agents.coordination import CoordinationAgent

coordinator = CoordinationAgent()
coordinator.start()

from src.agents.testing import TestingAgent

test_agent = TestingAgent()
test_agent.start()
coordinator.register_agent('TestingAgent', test_agent)

print(f'注册Agent数: {len(coordinator.registered_agents)}')

workflow = coordinator.create_workflow(
    '测试流程',
    '测试工作流',
    [
        {
            'agent_name': 'TestingAgent',
            'action': 'generate_unit_tests',
            'params': {'source_file': '/test.py', 'function_names': ['add']}
        }
    ]
)

print(f'✅ 工作流创建: {workflow.name}')
print(f'   任务数: {len(workflow.tasks)}')
print(f'   状态: {workflow.status.value}')

if len(workflow.tasks) > 0:
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

echo "【验收标准3】Agent间消息传递机制"
echo "----------------------------------------"
python3 -c "
from src.agents.coordination import CoordinationAgent, MessageType

coordinator = CoordinationAgent()
coordinator.start()

msg = coordinator.send_message(
    'AgentA',
    'AgentB',
    MessageType.REQUEST,
    {'action': 'test'}
)

print(f'✅ 消息发送成功')
print(f'   消息ID: {msg.msg_id}')
print(f'   发送者: {msg.sender}')
print(f'   接收者: {msg.receiver}')
print(f'   消息类型: {msg.msg_type.value}')
print(f'   历史记录数: {len(coordinator.message_history)}')

if msg.msg_id and len(coordinator.message_history) > 0:
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

echo "【验收标准4】工作流状态跟踪和异常处理"
echo "----------------------------------------"
python3 -c "
from src.agents.coordination import CoordinationAgent, WorkflowStatus, TaskStatus

coordinator = CoordinationAgent()
coordinator.start()

from src.agents.testing import TestingAgent

test_agent = TestingAgent()
test_agent.start()
coordinator.register_agent('TestingAgent', test_agent)

workflow = coordinator.create_workflow(
    '异常处理测试',
    '测试工作流',
    [
        {
            'agent_name': 'TestingAgent',
            'action': 'generate_unit_tests',
            'params': {'source_file': '/test.py', 'function_names': ['test_func']}
        }
    ]
)

result = coordinator.execute_workflow(workflow.workflow_id)

print(f'✅ 工作流执行完成')
print(f'   工作流ID: {result.workflow_id}')
print(f'   最终状态: {result.status.value}')
print(f'   任务数: {len(result.tasks)}')

for task in result.tasks:
    print(f'   任务 {task.task_id}: {task.status.value}')

if result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
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
    echo "✅ 阶段39验收通过"
    exit 0
else
    echo "❌ 阶段39验收未通过"
    exit 1
fi
