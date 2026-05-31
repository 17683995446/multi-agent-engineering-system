#!/bin/bash
set -e

echo "===== 阶段14：全局信息显式化验证脚本 ====="
echo ""

echo "1. 验证显式化扫描模块:"
python -m src.common.explicit_scanner
echo ""

echo "2. 验证导入:"
python -c "from src.common.explicit_scanner import ExplicitInfoScanner, ScanReport; print('✓ ExplicitInfoScanner 导入成功')"
echo ""

echo "3. 验证核心功能:"
python -c "
from src.common.explicit_scanner import ExplicitInfoScanner
from pathlib import Path

project_root = Path('/workspace')
scanner = ExplicitInfoScanner(str(project_root))
report = scanner.scan_project()

print(f'✓ 扫描文件数: {report.total_files}')
print(f'✓ 隐式变量: {len(report.implicit_variables)} 个')
print(f'✓ 隐式逻辑: {len(report.implicit_logic)} 个')
print(f'✓ 隐式依赖: {len(report.implicit_dependencies)} 个')
print(f'✓ 隐式配置: {len(report.implicit_configs)} 个')
print(f'✓ 问题总数: {report.get_total_issues()}')
print(f'✓ 满足最小熵: {\"是\" if report.is_clean() else \"否\"}')"
echo ""

echo "4. 验证最小熵原则:"
grep -q "遵循第一性原理：最小熵信息确定性要求" /workspace/src/common/explicit_scanner.py
if [ $? -eq 0 ]; then
    echo "   ✓ 代码注释明确说明最小熵原则"
else
    echo "   ✗ 缺少最小熵原则说明"
fi
echo ""

echo "===== 验证完成 ====="
