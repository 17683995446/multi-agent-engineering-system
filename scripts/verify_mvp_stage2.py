#!/usr/bin/env python3
"""
MVP阶段2验证脚本: 任务分解HTD算法
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mvp_core.htd_decomposer import (
    HTDDecomposer, TaskNode, TaskStatus, TaskPriority
)


def test_decompose_development():
    """测试开发类需求分解"""
    print("\n[Test] 开发类需求分解")
    
    decomposer = HTDDecomposer()
    requirement = "实现用户登录功能，包括用户名密码验证和JWT token生成"
    
    root = decomposer.decompose(requirement)
    
    assert root is not None
    assert root.name.startswith("需求:")
    assert len(root.children) == 5  # 分析、设计、编码、测试、审查
    
    print(f"  ✓ 分解成功: {len(root.children)} 个子任务")
    
    # 验证子任务
    task_names = [child.name for child in root.children]
    assert "需求分析" in task_names
    assert "架构设计" in task_names
    assert "编码实现" in task_names
    assert "单元测试" in task_names
    assert "代码审查" in task_names
    print(f"  ✓ 子任务类型正确: {task_names}")
    
    # 验证依赖关系
    coding_task = [c for c in root.children if c.name == "编码实现"][0]
    assert len(coding_task.dependencies) == 1  # 依赖架构设计
    print(f"  ✓ 依赖关系正确")
    
    print("[Pass] 开发类需求分解\n")
    return True


def test_decompose_testing():
    """测试测试类需求分解"""
    print("[Test] 测试类需求分解")
    
    decomposer = HTDDecomposer()
    requirement = "为登录模块编写测试用例并执行测试"
    
    root = decomposer.decompose(requirement)
    
    assert len(root.children) == 4  # 计划、用例、执行、报告
    
    task_names = [child.name for child in root.children]
    assert "测试计划" in task_names
    assert "测试用例设计" in task_names
    assert "测试执行" in task_names
    assert "测试报告" in task_names
    
    print(f"  ✓ 测试任务分解正确: {task_names}")
    print("[Pass] 测试类需求分解\n")
    return True


def test_decompose_documentation():
    """测试文档类需求分解"""
    print("[Test] 文档类需求分解")
    
    decomposer = HTDDecomposer()
    requirement = "编写API使用文档和README"
    
    root = decomposer.decompose(requirement)
    
    assert len(root.children) == 3  # 规划、编写、审核
    
    task_names = [child.name for child in root.children]
    assert "文档规划" in task_names
    assert "内容编写" in task_names
    assert "审核校对" in task_names
    
    print(f"  ✓ 文档任务分解正确: {task_names}")
    print("[Pass] 文档类需求分解\n")
    return True


def test_leaf_tasks():
    """测试叶子任务获取"""
    print("[Test] 叶子任务获取")
    
    decomposer = HTDDecomposer()
    root = decomposer.decompose("实现一个功能")
    
    leaves = decomposer.get_leaf_tasks(root)
    
    assert len(leaves) == len(root.children)  # MVP阶段所有子任务都是叶子
    assert all(leaf.is_leaf() for leaf in leaves)
    
    print(f"  ✓ 叶子任务数量: {len(leaves)}")
    for leaf in leaves:
        print(f"    - {leaf.name}: {leaf.description}")
    
    print("[Pass] 叶子任务获取\n")
    return True


def test_task_status_update():
    """测试任务状态更新"""
    print("[Test] 任务状态更新")
    
    decomposer = HTDDecomposer()
    root = decomposer.decompose("实现功能A")
    
    # 初始状态
    analysis_task = root.children[0]
    assert analysis_task.status == TaskStatus.PENDING
    
    # 更新状态
    assert decomposer.update_task_status(root, analysis_task.task_id, TaskStatus.COMPLETED) == True
    assert analysis_task.status == TaskStatus.COMPLETED
    
    # 检查依赖任务是否就绪
    ready_tasks = decomposer.get_ready_tasks(root)
    # 分析完成后，依赖分析的任务应该就绪
    assert len(ready_tasks) > 0
    
    print(f"  ✓ 状态更新成功")
    print(f"  ✓ 就绪任务数量: {len(ready_tasks)}")
    
    # 更新不存在的任务
    assert decomposer.update_task_status(root, "nonexistent", TaskStatus.COMPLETED) == False
    print(f"  ✓ 无效任务处理正确")
    
    print("[Pass] 任务状态更新\n")
    return True


def test_task_tree_structure():
    """测试任务树结构"""
    print("[Test] 任务树结构")
    
    decomposer = HTDDecomposer()
    root = decomposer.decompose("重构代码")
    
    tree = decomposer.get_task_tree(root)
    
    assert "task_id" in tree
    assert "name" in tree
    assert "children" in tree
    assert "status" in tree
    assert "is_leaf" in tree
    
    print(f"  ✓ 任务树结构完整")
    print(f"  ✓ 根任务: {tree['name']}")
    print(f"  ✓ 子任务数: {len(tree['children'])}")
    
    print("[Pass] 任务树结构\n")
    return True


def main():
    print("=" * 60)
    print("MVP阶段2验证: 任务分解HTD算法")
    print("=" * 60)
    
    results = []
    results.append(("开发类需求分解", test_decompose_development()))
    results.append(("测试类需求分解", test_decompose_testing()))
    results.append(("文档类需求分解", test_decompose_documentation()))
    results.append(("叶子任务获取", test_leaf_tasks()))
    results.append(("任务状态更新", test_task_status_update()))
    results.append(("任务树结构", test_task_tree_structure()))
    
    print("=" * 60)
    print("验收结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 MVP阶段2验收通过！")
        return 0
    else:
        print("\n⚠️ 存在失败测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
