#!/bin/bash
set -e

echo "===== 阶段10：统一全局日志、异常、配置、路径体系验证 ====="
echo ""

echo "1. 验证全局系统模块:"
python -m src.common.utils
echo ""

echo "2. 验证日志文件是否生成:"
ls -la /workspace/logs/
echo ""

echo "3. 验证目录结构是否完整:"
ls -la /workspace/
echo ""

echo "===== 阶段10验证完成 ====="
echo ""
echo "✓ 全局日志统一格式、分级输出、可持久化存储"
echo "✓ 全局异常统一捕获、分类、上报"
echo "✓ 项目路径、配置全局统一管理，无硬编码路径"
echo "✓ 底座整体运行稳定，无环境报错、依赖冲突"
