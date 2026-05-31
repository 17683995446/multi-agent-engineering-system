#!/bin/bash
# 阶段35验收：缺陷排查Agent初始化
set -e

echo "========================================"
echo "阶段35验收：缺陷排查Agent"
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
from src.agents.bug_hunting import BugHuntingAgent

agent = BugHuntingAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'BugHuntingAgent' and agent.is_running:
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

echo "【验收标准2】可解析日志、堆栈信息"
echo "----------------------------------------"
python3 -c "
from src.agents.bug_hunting import BugHuntingAgent

agent = BugHuntingAgent()
agent.start()

sample_stack = '''Traceback (most recent call last):
  File \"test.py\", line 10, in main
    x = int('abc')
ValueError: invalid literal for int()
'''

sample_log = '''2026-05-28 10:30:15 ERROR: ValueError in test
'''

# 解析堆栈
frames = agent.parse_stack_trace(sample_stack)
print(f'解析堆栈帧数：{len(frames)}')
print(f'第一帧：{frames[0].file}:{frames[0].line} in {frames[0].function}')

# 解析日志
log_info = agent.parse_log(sample_log)
print(f'日志级别：{log_info[\"level\"]}')
print(f'日志消息：{log_info[\"message\"]}')

if len(frames) > 0 and log_info['level']:
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

echo "【验收标准3】精准定位Bug根因、复现条件、影响范围"
echo "----------------------------------------"
python3 -c "
from src.agents.bug_hunting import BugHuntingAgent, ErrorType

agent = BugHuntingAgent()
agent.start()

sample_stack = '''Traceback (most recent call last):
  File \"user_service.py\", line 42, in get_user
    return database.query(user_id)
  File \"database.py\", line 15, in query
    cursor.execute(sql)
ValueError: invalid literal for int() with base 10: 'abc'
'''

sample_log = '''2026-05-28 10:30:15 ERROR: ValueError in get_user'''

result = agent.analyze_bug(sample_stack, sample_log)

print(f'Bug ID：{result.bug_id}')
print(f'根因：{result.root_cause}')
print(f'位置：{result.location.file}:{result.location.line}')
print(f'错误类型：{result.location.error_type.value}')
print(f'严重程度：{result.location.severity}')
print(f'置信度：{result.confidence}')
print()
print(f'复现条件：{result.reproduction.trigger}')
print(f'影响模块：{result.impact.affected_modules}')
print(f'影响函数：{result.impact.affected_functions}')

if result.root_cause and result.location.error_type == ErrorType.VALUE_ERROR:
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

echo "【验收标准4】输出可落地修复方案"
echo "----------------------------------------"
python3 -c "
from src.agents.bug_hunting import BugHuntingAgent

agent = BugHuntingAgent()
agent.start()

sample_stack = '''Traceback (most recent call last):
  File \"test.py\", line 10, in main
    x = int('abc')
ValueError: invalid literal for int()
'''

sample_log = '''2026-05-28 10:30:15 ERROR: ValueError'''

result = agent.analyze_bug(sample_stack, sample_log)

print(f'修复建议数：{len(result.fix_suggestions)}')
for fix in result.fix_suggestions:
    print(f'  [{fix.priority}] {fix.title}')
    print(f'    描述：{fix.description}')
    print(f'    风险：{fix.risk_level}，耗时：{fix.estimated_time}')

if len(result.fix_suggestions) > 0 and result.fix_suggestions[0].estimated_time:
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
    echo "✅ 阶段35验收通过"
    exit 0
else
    echo "❌ 阶段35验收未通过"
    exit 1
fi
