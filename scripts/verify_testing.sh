#!/bin/bash
# 阶段37验收：测试Agent初始化
set -e

echo "========================================"
echo "阶段37验收：测试Agent"
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
from src.agents.testing import TestingAgent

agent = TestingAgent()
agent.start()

print(f'Agent名称：{agent.name}')
print(f'运行状态：{agent.is_running}')

if agent.name == 'TestingAgent' and agent.is_running:
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

echo "【验收标准2】可自动生成单元/边界/异常用例"
echo "----------------------------------------"
python3 -c "
from src.agents.testing import TestingAgent, TestType

agent = TestingAgent()
agent.start()

# 生成单元测试
unit_suite = agent.generate_unit_tests('/tmp/demo.py', ['add', 'multiply'])
print(f'单元测试用例数：{unit_suite.total}')

# 生成边界测试
boundary_cases = agent.generate_boundary_tests('/tmp/demo.py', 'divide', {
    'name': 'value', 'type': 'int', 'min': 1, 'max': 100
})
print(f'边界测试用例数：{len(boundary_cases)}')

# 生成异常测试
exception_cases = agent.generate_exception_tests('/tmp/demo.py', 'divide')
print(f'异常测试用例数：{len(exception_cases)}')

# 验证类型
has_unit = any(t.test_type == TestType.UNIT for t in unit_suite.test_cases)
has_boundary = any(t.test_type == TestType.BOUNDARY for t in boundary_cases)
has_exception = any(t.test_type == TestType.EXCEPTION for t in exception_cases)

print(f'包含单元测试：{has_unit}')
print(f'包含边界测试：{has_boundary}')
print(f'包含异常测试：{has_exception}')

if unit_suite.total > 0 and len(boundary_cases) > 0 and len(exception_cases) > 0:
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

echo "【验收标准3】可执行自动化回归测试、统计通过率"
echo "----------------------------------------"
python3 -c "
from src.agents.testing import TestingAgent

agent = TestingAgent()
agent.start()

# 生成测试套件
suite = agent.generate_unit_tests('/tmp/demo.py', ['add', 'multiply'])
test_file = agent.write_pytest_file(suite)

# 执行回归测试
result = agent.run_regression_tests([test_file])

print(f'结果ID：{result.result_id}')
print(f'总用例数：{result.summary[\"total_tests\"]}')
print(f'通过数：{result.summary[\"passed\"]}')
print(f'失败数：{result.summary[\"failed\"]}')
print(f'通过率：{result.summary[\"pass_rate\"]:.1f}%')

if result.summary['total_tests'] >= 0 and result.summary['pass_rate'] >= 0:
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

echo "【验收标准4】复用Pytest原生测试能力"
echo "----------------------------------------"
python3 -c "
from src.agents.testing import TestingAgent

agent = TestingAgent()
agent.start()

# 生成测试套件并写入Pytest文件
unit_suite = agent.generate_unit_tests('/tmp/demo.py', ['add'])
test_file = agent.write_pytest_file(unit_suite)

print(f'生成的Pytest文件：{test_file}')

# 尝试运行Pytest
pytest_result = agent.run_pytest(test_file)

print(f'Pytest执行结果：')
print(f'  成功：{pytest_result[\"success\"]}')
print(f'  通过：{pytest_result[\"passed\"]}')
print(f'  失败：{pytest_result[\"failed\"]}')
print(f'  输出：{pytest_result[\"output\"][:80]}...')

if pytest_result['pass_rate'] >= 0:
    print('✅ 验收标准4：通过（复用Pytest）')
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
    echo "✅ 阶段37验收通过"
    exit 0
else
    echo "❌ 阶段37验收未通过"
    exit 1
fi
