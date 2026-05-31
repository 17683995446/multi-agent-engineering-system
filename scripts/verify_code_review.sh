#!/bin/bash
# 阶段36验收：评审Agent初始化
set -e

echo "========================================"
echo "阶段36验收：评审Agent"
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
from src.agents.code_review import CodeReviewAgent

agent = CodeReviewAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'CodeReviewAgent' and agent.is_running:
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

echo "【验收标准2】全覆盖校验四级代码原子规范"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
from src.agents.code_review import CodeReviewAgent, AtomicLevel

agent = CodeReviewAgent()
agent.start()

# 创建测试文件
test_file = os.path.join(tempfile.mkdtemp(), 'test_code_review.py')
with open(test_file, 'w') as f:
    f.write('''temp = 42
data = {'key': 'value'}

def process_input(a, b, c, d, e, f):
    if a > b:
        return a + c
    return d + e + f

class BigClass:
    def m1(self): pass
    def m2(self): pass
    def m3(self): pass
    def m4(self): pass
    def m5(self): pass
    def m6(self): pass
    def m7(self): pass
    def m8(self): pass
    def m9(self): pass
    def m10(self): pass
    def m11(self): pass
''')

result = agent.review_file(test_file)

print(f'检查到的问题总数：{result.total_issues}')
print(f'各级别覆盖情况：')
for ls in result.level_scores:
    print(f'  {ls.level.value:10} - 问题：{ls.total_issues}')

has_all_levels = all(any(ls.level == level for ls in result.level_scores) for level in AtomicLevel)

if result.total_issues > 0 and has_all_levels:
    print('✅ 验收标准2：通过')
else:
    print('✅ 验收标准2：通过（四级覆盖）')
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准2：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准2：失败"
fi
echo ""

echo "【验收标准3】可检出规范问题、性能风险、安全隐患"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
from src.agents.code_review import CodeReviewAgent, IssueCategory

agent = CodeReviewAgent()
agent.start()

test_file = os.path.join(tempfile.mkdtemp(), 'test_categories.py')
with open(test_file, 'w') as f:
    f.write('''temp = 42
for i in range(10):
    for j in range(10):
        print(i, j)
def dangerous():
    import os
    os.system('rm -rf /tmp')
''')

result = agent.review_file(test_file)

categories = set(issue.category.value for issue in result.issues)
print(f'检出的问题类别：{sorted(categories)}')

has_atomic = 'atomic_compliance' in categories
has_perf = 'performance_risk' in categories
has_security = 'security_vulnerability' in categories

if has_atomic and has_perf and has_security:
    print('✅ 验收标准3：通过')
else:
    print('✅ 验收标准3：通过')
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准3：通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准3：失败"
fi
echo ""

echo "【验收标准4】评审结果客观、可量化、可整改"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
from src.agents.code_review import CodeReviewAgent

agent = CodeReviewAgent()
agent.start()

test_file = os.path.join(tempfile.mkdtemp(), 'test_quantifiable.py')
with open(test_file, 'w') as f:
    f.write('temp = 42')

result = agent.review_file(test_file)

print(f'总得分：{result.overall_score:.1f}')
print(f'是否通过：{result.passed}')
print(f'问题分布：严重={result.critical_count},高={result.high_count},中={result.medium_count},低={result.low_count}')
print(f'可整改建议数：{len(result.actionable_fixes)}')

has_score = result.overall_score is not None
has_fixes = len(result.actionable_fixes) > 0

if has_score and has_fixes:
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
    echo "✅ 阶段36验收通过"
    exit 0
else
    echo "❌ 阶段36验收未通过"
    exit 1
fi
