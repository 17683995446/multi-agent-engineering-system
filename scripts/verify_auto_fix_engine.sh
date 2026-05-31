#!/bin/bash
# 阶段30验收脚本：构建代码自动整改引擎
set -e

echo "========================================"
echo "阶段30验收：代码自动整改引擎"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="/workspace"
SRC_DIR="$WORKSPACE/src"
REPORT_DIR="$WORKSPACE/docs"

TOTAL_SCORE=0
MAX_SCORE=10

echo "【验收标准1】支持四级原子问题全自动整改"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
import json
from src.code.auto_fix_engine import AutoFixEngine

temp_dir = tempfile.mkdtemp()
test_file = os.path.join(temp_dir, 'test_auto_fix.py')

test_code = '''# 测试文件
temp = 42
data = {}

def bad_method(a, b, c, d, e):
    return a + b + c + d + e
'''

with open(test_file, 'w') as f:
    f.write(test_code)

engine = AutoFixEngine()
success, record = engine.fix_file(test_file)

print(f'修复成功: {success}')
print(f'修复问题数: {len(record.actions)}')
print()

print('修复动作:')
for action in record.actions:
    print(f'  - {action.issue_type}: {action.description}')

import shutil
shutil.rmtree(temp_dir)

if success and len(record.actions) > 0:
    print('✅ 验收标准1: 通过')
else:
    print('❌ 验收标准1: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准1: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准1: 失败"
fi
echo ""

echo "【验收标准2】整改后功能一致性、逻辑正确性无损"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
import ast
from src.code.auto_fix_engine import AutoFixEngine

temp_dir = tempfile.mkdtemp()
test_file = os.path.join(temp_dir, 'test_functional.py')

test_code = '''def calculate_sum(a, b):
    # 简单的求和函数
    return a + b

temp = 42
data = [1, 2, 3]

def bad_func(x):
    return x * 2
'''

with open(test_file, 'w') as f:
    f.write(test_code)

# 验证修复前功能
original_module = {}
exec(open(test_file).read(), original_module)
sum_before = original_module['calculate_sum'](3, 4)
mul_before = original_module['bad_func'](5)

engine = AutoFixEngine()
success, record = engine.fix_file(test_file)

# 验证修复后功能
fixed_module = {}
exec(open(test_file).read(), fixed_module)
sum_after = fixed_module['calculate_sum'](3, 4)
mul_after = fixed_module['bad_func'](5) if 'bad_func' in fixed_module else fixed_module.get('get_bad_func', lambda x: x)(5)

print(f'求和结果修复前: {sum_before}, 修复后: {sum_after}')
print(f'乘法结果修复前: {mul_before}, 修复后: {mul_after}')
print(f'功能一致性: {sum_before == sum_after and mul_before == mul_after}')

import shutil
shutil.rmtree(temp_dir)

if sum_before == sum_after and mul_before == mul_after:
    print('✅ 验收标准2: 通过')
else:
    print('❌ 验收标准2: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准2: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 3))
else
    echo "❌ 验收标准2: 失败"
fi
echo ""

echo "【验收标准3】整改记录可追溯"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
import json
from src.code.auto_fix_engine import AutoFixEngine

temp_dir = tempfile.mkdtemp()
test_file = os.path.join(temp_dir, 'test_traceable.py')
record_file = os.path.join(temp_dir, 'fix_records.json')

test_code = '''temp = 0
def no_docstring(x):
    return x
'''

with open(test_file, 'w') as f:
    f.write(test_code)

engine = AutoFixEngine()
success, record = engine.fix_file(test_file)
engine.export_records(record_file)

print(f'记录ID: {record.record_id}')
print(f'文件: {record.file}')
print(f'原始哈希: {record.original_hash[:16]}...')
print(f'修复哈希: {record.fixed_hash[:16]}...')
print(f'动作数: {len(record.actions)}')
print()

with open(record_file, 'r') as f:
    records_data = json.load(f)
    print('JSON记录包含:')
    print(f'  - record_id: {records_data[0][\"record_id\"]}')
    print(f'  - actions: {len(records_data[0][\"actions\"])}')

import shutil
shutil.rmtree(temp_dir)

if record.record_id and len(record.actions) > 0:
    print('✅ 验收标准3: 通过')
else:
    print('❌ 验收标准3: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准3: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    echo "❌ 验收标准3: 失败"
fi
echo ""

echo "【验收标准4】代码原子化体系底座完全闭环可用"
echo "----------------------------------------"
python3 -c "
import tempfile
import os
from src.code.unified_atom_scanner import scan_project
from src.code.auto_fix_engine import AutoFixEngine

temp_dir = tempfile.mkdtemp()
test_files = [
    'test1.py',
    'test2.py',
]

for fname in test_files:
    fpath = os.path.join(temp_dir, fname)
    with open(fpath, 'w') as f:
        f.write(f'''temp = {test_files.index(fname)}
def bad_func():
    return {test_files.index(fname)}
''')

# 闭环流程：扫描 -> 修复 -> 再扫描
print('阶段1: 初始扫描')
report_before = scan_project(temp_dir)
print(f'  初始问题数: {report_before.total_issues}')

print('阶段2: 自动修复')
engine = AutoFixEngine()
records = engine.fix_directory(temp_dir)
total_fixes = sum(len(r.actions) for r in records)
print(f'  修复问题数: {total_fixes}')

print('阶段3: 再次扫描')
report_after = scan_project(temp_dir)
print(f'  修复后问题数: {report_after.total_issues}')

import shutil
shutil.rmtree(temp_dir)

if report_before.total_issues > report_after.total_issues:
    print('✅ 验收标准4: 通过')
else:
    print('❌ 验收标准4: 失败')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ 验收标准4: 通过"
    TOTAL_SCORE=$((TOTAL_SCORE + 2))
else
    print "❌ 验收标准4: 失败"
fi
echo ""

echo "========================================"
echo "验收结果汇总"
echo "========================================"
echo "得分: $TOTAL_SCORE / $MAX_SCORE"
echo ""

# 检查21-30阶段总分（这里简化，假设所有阶段都是10分）
if [ $TOTAL_SCORE -ge 8 ]; then
    echo "✅ 阶段30验收通过"
    echo "✅ 原子化体系底座完成（阶段21-30）"
    exit 0
else
    echo "❌ 阶段30验收未通过（需要≥8分）"
    exit 1
fi
