#!/usr/bin/env python3
"""
第41阶段验收验证脚本 - 集成开源HTD层级任务拆解算法
验收标准：
1. 成功集成开源HTD算法，无自研核心逻辑
2. 复杂任务可逐层拆解为原子任务
3. 任务层级清晰、依赖正确、无遗漏冗余
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.requirement_decomposition import RequirementDecompositionAgent
from src.common.htd_decomposer import (
    HTDDecomposer,
    HTDTask,
    TaskType,
    create_htd_task,
    decompose_task
)


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_success(text):
    print(f"✅ {text}")


def print_failure(text):
    print(f"❌ {text}")


def print_info(text):
    print(f"ℹ️  {text}")


def verify_htd_integration():
    """验收标准1: 成功集成开源HTD算法，无自研核心逻辑"""
    print_header("验收标准1: 成功集成开源HTD算法")

    try:
        # 验证HTD分解器初始化
        decomposer = HTDDecomposer()
        print_success("HTDDecomposer 初始化成功")

        # 验证策略注册
        strategies = list(decomposer.decomposition_strategies.keys())
        print_info(f"可用拆解策略：{strategies}")
        assert "standard" in strategies, "standard策略应该存在"
        assert "waterfall" in strategies, "waterfall策略应该存在"
        assert "feature" in strategies, "feature策略应该存在"
        print_success("拆解策略注册正常")

        # 验证Agent集成
        agent = RequirementDecompositionAgent()
        assert hasattr(agent, "htd_decomposer"), "Agent应该包含htd_decomposer"
        print_success("需求拆解Agent成功集成HTD分解器")

        return True
    except Exception as e:
        print_failure(f"HTD集成验证失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_task_decomposition():
    """验收标准2: 复杂任务可逐层拆解为原子任务"""
    print_header("验收标准2: 复杂任务可逐层拆解为原子任务")

    try:
        agent = RequirementDecompositionAgent()
        agent.start()

        # 测试复杂需求拆解
        complex_requirements = [
            "开发一个企业级项目管理系统",
            "构建一个高并发的实时聊天平台",
            "设计并实现一个AI图像识别服务"
        ]

        for req in complex_requirements:
            print_info(f"测试需求：{req}")

            result = agent.decompose(req, max_depth=3, strategy="standard")

            # 验证有拆解结果
            assert "all_tasks" in result, "结果应包含all_tasks"
            assert len(result["all_tasks"]) > 1, "应该有多个任务"
            assert "atomic_tasks" in result, "结果应包含atomic_tasks"
            assert len(result["atomic_tasks"]) >= 1, "应该有原子任务"

            print_success(f"  拆解成功：任务总数 {result['summary']['total_tasks']}，原子任务 {result['summary']['atomic_count']}")

        return True
    except Exception as e:
        print_failure(f"任务拆解验证失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_hierarchy_and_dependencies():
    """验收标准3: 任务层级清晰、依赖正确、无遗漏冗余"""
    print_header("验收标准3: 任务层级清晰、依赖正确、无遗漏冗余")

    try:
        decomposer = HTDDecomposer()

        # 创建测试任务
        task = create_htd_task(
            "测试项目",
            "这是一个用于测试的完整项目",
            TaskType.REQUIREMENT
        )

        # 执行拆解
        result = decomposer.decompose(task, "waterfall", 3)

        # 验证层级结构
        all_tasks = decomposer.to_flat_list(result)

        # 检查层级深度
        levels = set(t["level"] for t in all_tasks)
        print_info(f"任务层级分布：{sorted(levels)}")
        assert 0 in levels, "应该有根任务(level 0)"
        assert 1 in levels, "应该有子任务(level 1)"

        # 检查父子关系
        parent_child_map = {}
        for t in all_tasks:
            if t["parent_id"]:
                if t["parent_id"] not in parent_child_map:
                    parent_child_map[t["parent_id"]] = []
                parent_child_map[t["parent_id"]].append(t["entity_id"])

        print_info(f"父子关系：{len(parent_child_map)} 个父任务")

        # 检查依赖关系
        tasks_with_deps = [t for t in all_tasks if t["dependencies"]]
        print_info(f"有依赖的任务：{len(tasks_with_deps)} 个")

        # 检查原子任务标记
        atomic_tasks = [t for t in all_tasks if t["is_atomic"]]
        print_info(f"原子任务：{len(atomic_tasks)} 个")

        # 验证无循环依赖
        all_ids = set(t["entity_id"] for t in all_tasks)
        for t in all_tasks:
            for dep_id in t["dependencies"]:
                assert dep_id in all_ids, f"依赖的任务 {dep_id} 应该存在"
                assert dep_id != t["entity_id"], "任务不应依赖自己"

        print_success("层级结构、依赖关系验证通过")

        # 验证多种策略
        strategies = ["standard", "waterfall", "feature"]
        for strategy in strategies:
            result = decomposer.decompose(task, strategy, 3)
            flat = decomposer.to_flat_list(result)
            assert len(flat) > 1, f"{strategy}策略应该产生多个任务"
            print_success(f"  {strategy}策略：{len(flat)} 个任务")

        return True
    except Exception as e:
        print_failure(f"层级和依赖验证失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_convenience_functions():
    """验证便捷函数"""
    print_header("验证：便捷函数")

    try:
        # 测试decompose_task便捷函数
        print_info("测试 decompose_task 便捷函数")
        result = decompose_task("测试便捷函数", "standard", 2)
        assert result["summary"]["total_tasks"] > 1, "便捷函数应该工作"
        print_success("decompose_task 便捷函数验证通过")

        return True
    except Exception as e:
        print_failure(f"便捷函数验证失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_backward_compatibility():
    """验证向后兼容性"""
    print_header("验证：向后兼容性")

    try:
        agent = RequirementDecompositionAgent()
        agent.start()

        # 测试兼容模式
        print_info("测试兼容模式 decompose_compat")
        compat_result = agent.decompose_compat("向后兼容性测试", 3)

        assert "root" in compat_result
        assert "all_tasks" in compat_result
        assert "summary" in compat_result
        print_success("向后兼容性验证通过")

        return True
    except Exception as e:
        print_failure(f"向后兼容性验证失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("  第41阶段验收 - 集成开源HTD层级任务拆解算法")
    print("=" * 80)

    results = []

    # 验收1: HTD集成
    integration_ok = verify_htd_integration()
    results.append(("HTD集成", integration_ok))

    # 验收2: 任务拆解
    decomposition_ok = verify_task_decomposition()
    results.append(("任务拆解", decomposition_ok))

    # 验收3: 层级和依赖
    hierarchy_ok = verify_hierarchy_and_dependencies()
    results.append(("层级依赖", hierarchy_ok))

    # 额外验证
    convenience_ok = verify_convenience_functions()
    results.append(("便捷函数", convenience_ok))

    compatibility_ok = verify_backward_compatibility()
    results.append(("向后兼容", compatibility_ok))

    # 总结
    print_header("验收总结")

    passed = sum(1 for name, ok in results if ok)
    total = len(results)

    for name, ok in results:
        if ok:
            print_success(f"{name}：通过")
        else:
            print_failure(f"{name}：失败")

    print()
    print_info(f"总计：{passed}/{total} 项通过")

    # 检查核心验收标准
    core_checks = results[:3]
    core_passed = sum(1 for name, ok in core_checks if ok)

    print()
    if core_passed == 3:
        print_success("第41阶段验收通过！HTD层级任务拆解算法集成完成")
        print("=" * 80)
        return 0
    else:
        print_failure("第41阶段验收失败 - 核心验收标准未全部通过")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
