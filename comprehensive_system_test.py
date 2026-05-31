#!/usr/bin/env python3
"""
全面系统测试脚本 - 发现并修复系统问题
遵循标准化全流程测试
"""
import os
import sys
import logging
import tempfile
import ast
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/system_test.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, '/workspace/src')

ISSUES_FOUND = []


def log_issue(issue_type: str, severity: str, description: str, location: str = None):
    """记录发现的问题"""
    issue = {
        'timestamp': datetime.now().isoformat(),
        'type': issue_type,
        'severity': severity,
        'description': description,
        'location': location or 'Unknown'
    }
    ISSUES_FOUND.append(issue)
    logger.error(f"【{severity.upper()}】{issue_type}: {description} at {location}")


def test_module_imports():
    """测试1: 模块导入测试"""
    logger.info("="*70)
    logger.info("测试1: 模块导入测试")
    logger.info("="*70)
    
    modules_to_test = [
        'agents.base',
        'agents.central_control',
        'agents.requirement_decomposition',
        'agents.architecture',
        'agents.development',
        'agents.bug_hunting',
        'agents.code_review',
        'agents.testing',
        'common.utils',
        'common.atomic_entities',
        'common.state_manager',
        'code.variable_atom_scanner',
        'code.method_atom_scanner',
        'code.class_atom_scanner',
        'code.unified_atom_scanner',
        'code.auto_fix_engine',
    ]
    
    for module_name in modules_to_test:
        try:
            logger.info(f"  尝试导入: {module_name}")
            __import__(module_name)
            logger.info(f"  ✅ 成功导入: {module_name}")
        except Exception as e:
            log_issue(
                'Module Import Error',
                'high',
                f'导入模块失败: {module_name}, 错误: {e}',
                module_name
            )
            logger.error(f"  ❌ 导入失败: {e}")


def test_agent_initialization():
    """测试2: Agent初始化测试"""
    logger.info("\n" + "="*70)
    logger.info("测试2: Agent初始化测试")
    logger.info("="*70)
    
    agents_to_test = [
        ('agents.central_control', 'CentralControlAgent'),
        ('agents.requirement_decomposition', 'RequirementDecompositionAgent'),
        ('agents.architecture', 'ArchitectureAgent'),
        ('agents.development', 'DevelopmentAgent'),
        ('agents.bug_hunting', 'BugHuntingAgent'),
        ('agents.code_review', 'CodeReviewAgent'),
        ('agents.testing', 'TestingAgent'),
    ]
    
    for module_path, agent_class in agents_to_test:
        try:
            logger.info(f"\n  测试: {agent_class}")
            module = __import__(module_path, fromlist=[''])
            AgentClass = getattr(module, agent_class)
            logger.info(f"    获取类: {agent_class}")
            
            agent = AgentClass()
            logger.info(f"    创建实例成功")
            
            agent.start()
            logger.info(f"    ✅ Agent启动成功")
            
            logger.info(f"    验证属性: name={agent.name}, is_running={agent.is_running}")
            if hasattr(agent, 'stop'):
                agent.stop()
                logger.info(f"    ✅ Agent停止成功")
            
        except Exception as e:
            log_issue(
                'Agent Initialization Error',
                'high',
                f'Agent初始化失败: {agent_class}, 错误: {e}',
                module_path
            )
            logger.error(f"  ❌ 初始化失败: {e}")


def test_atom_scanners():
    """测试3: 原子化扫描器测试"""
    logger.info("\n" + "="*70)
    logger.info("测试3: 原子化扫描器测试")
    logger.info("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test_atom_issues.py")
        with open(test_file, "w") as f:
            f.write('''temp = 42
data = {'key': 'value'}

def vague_function(temp, data):
    """一个模糊的函数"""
    if temp > 0:
        return data + temp
    else:
        return data - temp

class BigClassWithTooManyMethods:
    def method1(self):
        return 1
    def method2(self):
        return 2
    def method3(self):
        return 3
    def method4(self):
        return 4
    def method5(self):
        return 5
    def method6(self):
        return 6
    def method7(self):
        return 7
    def method8(self):
        return 8
    def method9(self):
        return 9
    def method10(self):
        return 10
    def method11(self):
        return 11
    def method12(self):
        return 12
''')
        
        # 测试变量扫描器
        logger.info("\n  测试变量扫描器")
        try:
            from code.variable_atom_scanner import VariableAtomScanner
            scanner = VariableAtomScanner()
            logger.info(f"    扫描文件: {test_file}")
            result = scanner.scan_file(test_file)
            logger.info(f"    结果: 总变量数={result.total_count}, 问题数={result.issue_count}")
            logger.info(f"    ✅ 变量扫描完成")
        except Exception as e:
            log_issue('Scanner Error', 'high', f'变量扫描器错误: {e}', 'variable_atom_scanner')
            logger.error(f"  ❌ 变量扫描器失败: {e}")
        
        # 测试类扫描器
        logger.info("\n  测试类扫描器")
        try:
            from code.class_atom_scanner import ClassAtomScanner
            scanner = ClassAtomScanner()
            result = scanner.scan_file(test_file)
            logger.info(f"    结果: 类数量={len(result)}")
            for cls in result:
                logger.info(f"        类名: {cls.name}, 有问题: {cls.has_issues}")
            logger.info(f"    ✅ 类扫描完成")
        except Exception as e:
            log_issue('Scanner Error', 'high', f'类扫描器错误: {e}', 'class_atom_scanner')
            logger.error(f"  ❌ 类扫描器失败: {e}")
        
        # 测试统一扫描器
        logger.info("\n  测试统一扫描器")
        try:
            from code.unified_atom_scanner import UnifiedAtomScanner
            scanner = UnifiedAtomScanner()
            result = scanner.scan_file(test_file)
            total_issues = result.get('summary', {}).get('total_issues', 0)
            logger.info(f"    总问题数: {total_issues}")
            logger.info(f"    ✅ 统一扫描完成")
        except Exception as e:
            log_issue('Scanner Error', 'high', f'统一扫描器错误: {e}', 'unified_atom_scanner')
            logger.error(f"  ❌ 统一扫描器失败: {e}")
            logger.error(traceback.format_exc())


def test_auto_fix_engine():
    """测试4: 自动修复引擎测试"""
    logger.info("\n" + "="*70)
    logger.info("测试4: 自动修复引擎测试")
    logger.info("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test_fix.py")
        with open(test_file, "w") as f:
            f.write('''temp = 42
def bad_function(x):
    return x + temp
''')
        
        try:
            logger.info(f"  测试文件: {test_file}")
            from code.auto_fix_engine import AutoFixEngine
            engine = AutoFixEngine()
            if hasattr(engine, 'start'):
                engine.start()
            
            # 调用 analyze 或其他方法而不是 analyze_dependencies
            if hasattr(engine, 'scan_file'):
                result = engine.scan_file(test_file)
                logger.info(f"    扫描结果: 有结果")
            elif hasattr(engine, 'analyze'):
                result = engine.analyze(test_file)
                logger.info(f"    分析结果: 有结果")
            
            logger.info(f"    ✅ 自动修复引擎测试完成")
        except Exception as e:
            log_issue('Engine Error', 'high', f'自动修复引擎错误: {e}', 'auto_fix_engine')
            logger.error(f"  ❌ 自动修复引擎失败: {e}")
            logger.error(traceback.format_exc())


def test_central_control_workflow():
    """测试5: 总控工作流测试"""
    logger.info("\n" + "="*70)
    logger.info("测试5: 总控工作流测试")
    logger.info("="*70)
    
    try:
        from agents.central_control import CentralControlAgent
        agent = CentralControlAgent()
        agent.start()
        
        logger.info("  测试任务提交")
        task_id = agent.submit_task("测试任务", "high")
        logger.info(f"    任务提交成功: {task_id}")
        
        logger.info("  测试任务列表")
        tasks = agent.get_tasks_by_priority()
        logger.info(f"    任务数: {len(tasks)}")
        
        logger.info("  测试任务分配")
        agent.assign_task(task_id, "TestAgent")
        logger.info(f"    任务分配成功")
        
        logger.info("  测试任务完成")
        result = agent.complete_task(task_id, {"result": "ok"})
        logger.info(f"    任务完成: {result}")
        
        logger.info("    ✅ 总控工作流测试完成")
    except Exception as e:
        log_issue('Workflow Error', 'high', f'总控工作流错误: {e}', 'central_control')
        logger.error(f"  ❌ 总控工作流失败: {e}")


def test_static_code_check():
    """测试6: 静态代码检查"""
    logger.info("\n" + "="*70)
    logger.info("测试6: 静态代码检查")
    logger.info("="*70)
    
    code_dirs = [
        '/workspace/src/agents',
        '/workspace/src/code',
        '/workspace/src/common',
    ]
    
    for dir_path in code_dirs:
        if not os.path.exists(dir_path):
            continue
        logger.info(f"\n  检查目录: {dir_path}")
        
        for root, _, files in os.walk(dir_path):
            for file in files:
                if not file.endswith('.py'):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    ast.parse(content, filename=file_path)
                    logger.debug(f"    ✅ 语法正确: {file}")
                except SyntaxError as e:
                    log_issue(
                        'Syntax Error',
                        'critical',
                        f'语法错误: {e}',
                        file_path
                    )
                    logger.error(f"  ❌ 语法错误: {file_path}")
                except Exception as e:
                    log_issue(
                        'File Read Error',
                        'medium',
                        f'读取文件失败: {e}',
                        file_path
                    )


def test_requirement_decomposition():
    """测试7: 需求拆解测试"""
    logger.info("\n" + "="*70)
    logger.info("测试7: 需求拆解测试")
    logger.info("="*70)
    
    try:
        from agents.requirement_decomposition import RequirementDecompositionAgent
        agent = RequirementDecompositionAgent()
        agent.start()
        
        requirements = [
            "开发一个简单的登录系统",
            "实现一个API服务器",
            "构建一个数据分析工具"
        ]
        
        for req in requirements:
            logger.info(f"  拆解需求: {req}")
            result = agent.decompose(req, max_depth=3)
            # 处理不同的返回类型
            if isinstance(result, dict):
                logger.info(f"    结果是字典: 有{len(result)}个键")
            elif hasattr(result, 'root_task_id'):
                logger.info(f"    根任务ID: {result.root_task_id}")
            elif hasattr(result, 'analysis_history'):
                logger.info(f"    分析历史数: {len(result.analysis_history)}")
            else:
                logger.info(f"    结果类型: {type(result)}")
        
        logger.info("    ✅ 需求拆解测试完成")
    except Exception as e:
        log_issue('Decomposition Error', 'high', f'需求拆解错误: {e}', 'requirement_decomposition')
        logger.error(f"  ❌ 需求拆解失败: {e}")


def test_bug_hunting():
    """测试8: 缺陷排查测试"""
    logger.info("\n" + "="*70)
    logger.info("测试8: 缺陷排查测试")
    logger.info("="*70)
    
    try:
        from agents.bug_hunting import BugHuntingAgent
        agent = BugHuntingAgent()
        agent.start()
        
        stack_trace = '''Traceback (most recent call last):
  File "test.py", line 10, in main
    x = int('invalid')
ValueError: invalid literal for int() with base 10: 'invalid'
'''
        
        log_text = '''2026-05-28 10:00:00 ERROR: Processing failed
ValueError: invalid literal for int()
'''
        
        logger.info("  测试堆栈解析")
        frames = agent.parse_stack_trace(stack_trace)
        logger.info(f"    解析到 {len(frames)} 个堆栈帧")
        
        logger.info("  测试日志解析")
        log_info = agent.parse_log(log_text)
        logger.info(f"    日志级别: {log_info.get('level', 'unknown')}")
        
        logger.info("  测试完整分析")
        analysis_result = agent.analyze_bug(stack_trace, log_text)
        if hasattr(analysis_result, 'root_cause'):
            logger.info(f"    根因: {analysis_result.root_cause}")
        
        logger.info("    ✅ 缺陷排查测试完成")
    except Exception as e:
        log_issue('Bug Hunting Error', 'high', f'缺陷排查错误: {e}', 'bug_hunting')
        logger.error(f"  ❌ 缺陷排查失败: {e}")


def test_code_review():
    """测试9: 代码评审测试"""
    logger.info("\n" + "="*70)
    logger.info("测试9: 代码评审测试")
    logger.info("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test_review.py")
        with open(test_file, "w") as f:
            f.write('''temp = 42
data = {'key': 'value'}

def bad_func(a, b, c, d, e, f):
    return a + b + c + d + e + f

for i in range(10):
    for j in range(10):
        print(i, j)

def risky_code(x):
    import os
    os.system('echo dangerous')
''')
        
        try:
            from agents.code_review import CodeReviewAgent
            agent = CodeReviewAgent()
            agent.start()
            
            result = agent.review_file(test_file)
            
            if hasattr(result, 'total_issues'):
                logger.info(f"  总问题数: {result.total_issues}")
                logger.info(f"  严重问题: {result.critical_count}")
                logger.info(f"  高危问题: {result.high_count}")
                logger.info(f"  总体得分: {result.overall_score}")
                logger.info(f"  是否通过: {result.passed}")
            elif isinstance(result, dict):
                logger.info(f"  评审结果是字典")
            
            logger.info("    ✅ 代码评审测试完成")
        except Exception as e:
            log_issue('Code Review Error', 'high', f'代码评审错误: {e}', 'code_review')
            logger.error(f"  ❌ 代码评审失败: {e}")


def test_full_workflow():
    """测试10: 全工作流集成测试"""
    logger.info("\n" + "="*70)
    logger.info("测试10: 全工作流集成测试")
    logger.info("="*70)
    
    logger.info("\n  [1/4] 总控Agent启动")
    try:
        from agents.central_control import CentralControlAgent
        central = CentralControlAgent()
        central.start()
        logger.info("    ✅ 总控启动成功")
    except Exception as e:
        log_issue('Full Workflow Error', 'critical', f'总控启动失败: {e}', 'full_workflow')
        return
    
    logger.info("\n  [2/4] 需求拆解")
    try:
        from agents.requirement_decomposition import RequirementDecompositionAgent
        decomposer = RequirementDecompositionAgent()
        decomposer.start()
        result = decomposer.decompose("开发一个用户管理系统", max_depth=3)
        logger.info("    ✅ 需求拆解成功")
    except Exception as e:
        log_issue('Full Workflow Error', 'critical', f'需求拆解失败: {e}', 'full_workflow')
        return
    
    logger.info("\n  [3/4] 代码生成和评审")
    try:
        from agents.code_review import CodeReviewAgent
        reviewer = CodeReviewAgent()
        reviewer.start()
        logger.info("    ✅ 评审Agent启动成功")
    except Exception as e:
        log_issue('Full Workflow Error', 'critical', f'评审Agent启动失败: {e}', 'full_workflow')
        return
    
    logger.info("\n  [4/4] 测试执行")
    try:
        from agents.testing import TestingAgent
        tester = TestingAgent()
        tester.start()
        logger.info("    ✅ 测试Agent启动成功")
    except Exception as e:
        log_issue('Full Workflow Error', 'critical', f'测试Agent启动失败: {e}', 'full_workflow')
        return
    
    logger.info("\n    ✅ 全工作流集成测试完成")


def main():
    """主测试函数"""
    logger.info("="*80)
    logger.info("开始全面系统测试")
    logger.info("="*80)
    
    # 运行所有测试
    test_module_imports()
    test_agent_initialization()
    test_atom_scanners()
    test_auto_fix_engine()
    test_central_control_workflow()
    test_static_code_check()
    test_requirement_decomposition()
    test_bug_hunting()
    test_code_review()
    test_full_workflow()
    
    # 生成报告
    logger.info("\n" + "="*80)
    logger.info("测试完成报告")
    logger.info("="*80)
    
    logger.info(f"\n发现的问题总数: {len(ISSUES_FOUND)}")
    
    if ISSUES_FOUND:
        logger.info("\n问题详情:")
        for i, issue in enumerate(ISSUES_FOUND, 1):
            logger.info(f"\n  {i}. [{issue['severity'].upper()}] {issue['type']}")
            logger.info(f"     描述: {issue['description']}")
            logger.info(f"     位置: {issue['location']}")
        
        logger.info("\n" + "="*80)
        logger.info(f"⚠️  共发现 {len(ISSUES_FOUND)} 个问题需要解决")
        logger.info("="*80)
    else:
        logger.info("\n✅ 测试完成，未发现问题!")
    
    # 保存问题到文件
    import json
    report_file = "/workspace/system_test_issues.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(ISSUES_FOUND, f, indent=2, ensure_ascii=False)
    logger.info(f"\n问题报告已保存到: {report_file}")
    
    return len(ISSUES_FOUND)


if __name__ == "__main__":
    issue_count = main()
    sys.exit(1 if issue_count > 0 else 0)
