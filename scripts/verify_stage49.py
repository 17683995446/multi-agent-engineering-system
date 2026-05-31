#!/usr/bin/env python3
"""
阶段49验证脚本：知识库构建

验收标准：
1. 知识库正常初始化
2. 知识条目添加正常
3. 知识搜索正常
4. 知识索引正常
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.common.knowledge_base import (
    KnowledgeBase, KnowledgeEntry, KnowledgeIndexer,
    KnowledgeSearch, create_knowledge_base, KnowledgeBaseException
)


def test_knowledge_base_initialization():
    """测试知识库初始化"""
    print("\n=== 验收标准1: 知识库正常初始化 ===")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "kb.json"
            kb = KnowledgeBase(storage_path=storage)
            print(f"✅ 知识库初始化成功")
            print(f"   - 存储路径: {kb._storage_path}")
            print(f"   - 初始条目数: {kb.count()}")
            assert kb.count() == 0, "初始应为空"
        return True
    except Exception as e:
        print(f"❌ 知识库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_entry_crud():
    """测试知识条目CRUD"""
    print("\n=== 验收标准2: 知识条目添加正常 ===")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "kb.json"
            kb = KnowledgeBase(storage_path=storage)

            # Create
            entry = KnowledgeEntry(
                title="Python 装饰器",
                content="装饰器是Python中用于修改函数行为的高级特性。",
                tags={"python", "advanced"},
                category="编程语言",
                author="system"
            )
            created = kb.create(entry)
            print(f"✅ 创建条目成功: {created.id}")
            print(f"   - 标题: {created.title}")
            print(f"   - 版本: {created.version}")
            assert kb.count() == 1

            # Read
            fetched = kb.get(created.id)
            assert fetched is not None
            assert fetched.title == "Python 装饰器"
            print(f"✅ 读取条目成功")

            # Update
            updated = kb.update(created.id, title="Python 装饰器详解", content="扩展内容")
            assert updated.version == 2
            assert updated.title == "Python 装饰器详解"
            print(f"✅ 更新条目成功，新版本: {updated.version}")

            # Delete
            deleted = kb.delete(created.id)
            assert deleted is True
            assert kb.count() == 0
            print(f"✅ 删除条目成功")

        return True
    except Exception as e:
        print(f"❌ 知识条目CRUD测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_search():
    """测试知识搜索"""
    print("\n=== 验收标准3: 知识搜索正常 ===")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "kb.json"
            kb = KnowledgeBase(storage_path=storage)

            entries = [
                KnowledgeEntry(title="Python 基础", content="Python是一种解释型语言", tags={"python", "beginner"}, category="编程语言"),
                KnowledgeEntry(title="Python 高级", content="Python支持元类和描述符", tags={"python", "advanced"}, category="编程语言"),
                KnowledgeEntry(title="Java 基础", content="Java是一种静态类型语言", tags={"java", "beginner"}, category="编程语言"),
                KnowledgeEntry(title="Docker 入门", content="Docker用于容器化部署", tags={"docker", "devops"}, category="运维"),
            ]
            for e in entries:
                kb.create(e)

            # 全文搜索
            results = kb.search("Python")
            assert len(results) == 2, f"期望2条，实际{len(results)}条"
            print(f"✅ 全文搜索 'Python' 返回 {len(results)} 条结果")

            # 标签搜索
            results = kb.search_by_tag(["beginner"])
            assert len(results) == 2
            print(f"✅ 标签搜索 'beginner' 返回 {len(results)} 条结果")

            results = kb.search_by_tag(["python", "advanced"], match_all=True)
            assert len(results) == 1
            print(f"✅ 标签交集搜索返回 {len(results)} 条结果")

            # 分类搜索
            results = kb.search_by_category("编程语言")
            assert len(results) == 3
            print(f"✅ 分类搜索 '编程语言' 返回 {len(results)} 条结果")

            # 组合搜索
            results = kb.combined_search(query="Python", tags=["advanced"])
            assert len(results) == 1
            print(f"✅ 组合搜索返回 {len(results)} 条结果")

        return True
    except Exception as e:
        print(f"❌ 知识搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_indexer():
    """测试知识索引"""
    print("\n=== 验收标准4: 知识索引正常 ===")

    try:
        indexer = KnowledgeIndexer()

        e1 = KnowledgeEntry(id="e1", title="Hello World", content="Python basics", tags={"py", "beginner"}, category="code")
        e2 = KnowledgeEntry(id="e2", title="Advanced Python", content="Python metaclasses", tags={"py", "advanced"}, category="code")

        indexer.index_entry(e1)
        indexer.index_entry(e2)

        # 关键词索引
        ids = indexer.search_by_keyword("python")
        assert "e1" in ids and "e2" in ids
        print(f"✅ 关键词索引正常: 'python' 命中 {len(ids)} 条")

        ids = indexer.search_by_keyword("metaclasses")
        assert "e2" in ids
        print(f"✅ 关键词索引正常: 'metaclasses' 命中 {len(ids)} 条")

        # 标签索引
        ids = indexer.search_by_tag("py")
        assert ids == {"e1", "e2"}
        print(f"✅ 标签索引正常: 'py' 命中 {len(ids)} 条")

        ids = indexer.search_by_tag("advanced")
        assert ids == {"e2"}
        print(f"✅ 标签索引正常: 'advanced' 命中 {len(ids)} 条")

        # 分类索引
        ids = indexer.search_by_category("code")
        assert ids == {"e1", "e2"}
        print(f"✅ 分类索引正常: 'code' 命中 {len(ids)} 条")

        # 获取全部标签/分类
        assert indexer.get_all_tags() == {"py", "beginner", "advanced"}
        assert indexer.get_all_categories() == {"code"}
        print(f"✅ 索引元数据正常: 标签={indexer.get_all_tags()}, 分类={indexer.get_all_categories()}")

        # 移除索引
        indexer.remove_entry(e1)
        ids = indexer.search_by_tag("beginner")
        assert "e1" not in ids
        print(f"✅ 索引移除正常")

        return True
    except Exception as e:
        print(f"❌ 知识索引测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_version_management():
    """测试版本管理"""
    print("\n=== 附加测试: 版本管理 ===")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "kb.json"
            kb = KnowledgeBase(storage_path=storage)

            entry = KnowledgeEntry(title="Version Test", content="v1")
            kb.create(entry)

            kb.update(entry.id, content="v2")
            kb.update(entry.id, content="v3")

            history = kb.get_history(entry.id)
            assert len(history) == 2
            print(f"✅ 历史版本记录正常: {len(history)} 个历史版本")

            # 回滚到版本1
            rolled = kb.rollback(entry.id, version=1)
            assert rolled is not None
            # 回滚后 bump_version 一次，所以版本 = 1 + 1 = 2
            assert rolled.version == 2
            print(f"✅ 版本回滚正常: 回滚到版本1后当前版本为 {rolled.version}")

        return True
    except Exception as e:
        print(f"❌ 版本管理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_persistence():
    """测试持久化"""
    print("\n=== 附加测试: 持久化 ===")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "kb.json"

            kb1 = KnowledgeBase(storage_path=storage)
            entry = KnowledgeEntry(title="Persist Test", content="data", tags={"test"}, category="qa")
            kb1.create(entry)

            # 重新加载
            kb2 = KnowledgeBase(storage_path=storage)
            assert kb2.count() == 1
            fetched = kb2.get(entry.id)
            assert fetched is not None
            assert fetched.title == "Persist Test"
            assert fetched.tags == {"test"}
            print(f"✅ 持久化与加载正常: 加载后 {kb2.count()} 条条目")

        return True
    except Exception as e:
        print(f"❌ 持久化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段49验证：知识库构建")
    print("=" * 60)

    results = []

    results.append(("知识库初始化", test_knowledge_base_initialization()))
    results.append(("知识条目CRUD", test_knowledge_entry_crud()))
    results.append(("知识搜索", test_knowledge_search()))
    results.append(("知识索引", test_knowledge_indexer()))
    results.append(("版本管理", test_version_management()))
    results.append(("持久化", test_persistence()))

    print("\n" + "=" * 60)
    print("验收结果汇总")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n🎉 阶段49验收通过！")
        return 0
    else:
        print("\n❌ 阶段49验收未通过！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
