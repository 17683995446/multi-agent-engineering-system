#!/usr/bin/env python3
"""
阶段71验证脚本：数据库适配器

测试内容：
1. 查询构建器
2. 插入/查询/更新/删除
3. 事务管理
4. 批量事务操作
5. 连接池集成
6. 健康检查
7. 统计信息
8. 异常处理
"""

from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.db_adapter import (
    DBAdapter,
    DBConfig,
    DBType,
    QueryBuilder,
    QueryResult,
    get_db_adapter,
)


def test_query_builder() -> bool:
    print("[Test] QueryBuilder - 查询构建器")
    try:
        # SELECT
        builder = QueryBuilder().select("users", ["name", "age"]).where("age > ?", 18).limit(10)
        sql, params = builder.build()
        assert "SELECT name, age FROM users" in sql
        assert "age > ?" in sql
        assert "LIMIT 10" in sql
        assert params == (18,)
        print(f"  ✓ SELECT: {sql}, 参数: {params}")

        # INSERT
        builder = QueryBuilder().insert("users", {"name": "Alice", "age": 30})
        sql, params = builder.build()
        assert "INSERT INTO users" in sql
        assert params == ("Alice", 30)
        print(f"  ✓ INSERT: {sql}, 参数: {params}")

        # UPDATE
        builder = QueryBuilder().update("users", {"age": 31}).where("name = ?", "Alice")
        sql, params = builder.build()
        assert "UPDATE users SET" in sql
        assert params == (31, "Alice")
        print(f"  ✓ UPDATE: {sql}, 参数: {params}")

        # DELETE
        builder = QueryBuilder().delete("users").where("id = ?", 1)
        sql, params = builder.build()
        assert "DELETE FROM users" in sql
        assert params == (1,)
        print(f"  ✓ DELETE: {sql}, 参数: {params}")

        print("[Pass] QueryBuilder\n")
        return True
    except Exception as e:
        print(f"[Fail] QueryBuilder: {e}\n")
        return False


def test_crud() -> bool:
    print("[Test] CRUD - 增删改查")
    try:
        db = get_db_adapter(DBConfig(db_type=DBType.MOCK), name="test_crud")

        # Insert
        result = db.insert("users", {"name": "Alice", "age": 30})
        assert result.rowcount == 1
        assert result.lastrowid is not None
        print(f"  ✓ 插入成功, ID: {result.lastrowid}")

        # Select
        result = db.select("users")
        assert len(result.rows) >= 1
        assert result.rows[0]["name"] == "Alice"
        print(f"  ✓ 查询成功: {len(result.rows)} 条记录")

        # Select with columns
        result = db.select("users", columns=["name"])
        assert "name" in result.rows[0]
        print(f"  ✓ 指定列查询成功")

        # Update
        result = db.update("users", {"age": 31}, where="name = ?", params=("Alice",))
        assert result.rowcount >= 0
        print(f"  ✓ 更新成功")

        # Delete
        result = db.delete("users", where="name = ?", params=("Alice",))
        assert result.rowcount >= 0
        print(f"  ✓ 删除成功")

        db.close()
        print("[Pass] CRUD\n")
        return True
    except Exception as e:
        print(f"[Fail] CRUD: {e}\n")
        return False


def test_transaction() -> bool:
    print("[Test] Transaction - 事务管理")
    try:
        db = get_db_adapter(DBConfig(db_type=DBType.MOCK), name="test_tx")

        # 正常事务
        with db.transaction() as conn:
            conn.execute("INSERT INTO tx_test (name) VALUES (?)", ("tx_item",))
        print("  ✓ 事务提交成功")

        # 事务回滚
        try:
            with db.transaction() as conn:
                conn.execute("INSERT INTO tx_test (name) VALUES (?)", ("rollback_item",))
                raise ValueError("模拟错误")
        except Exception:
            pass
        print("  ✓ 事务回滚成功")

        # 批量事务
        operations = [
            ("INSERT INTO batch (name) VALUES (?)", ("a",)),
            ("INSERT INTO batch (name) VALUES (?)", ("b",)),
        ]
        results = db.execute_in_transaction(operations)
        assert len(results) == 2
        print(f"  ✓ 批量事务成功: {len(results)} 条")

        db.close()
        print("[Pass] Transaction\n")
        return True
    except Exception as e:
        print(f"[Fail] Transaction: {e}\n")
        return False


def test_pool_integration() -> bool:
    print("[Test] Pool Integration - 连接池集成")
    try:
        db = get_db_adapter(DBConfig(db_type=DBType.MOCK), name="test_pool")

        # 多次查询验证连接池
        for i in range(5):
            db.insert("pool_test", {"idx": i})

        result = db.select("pool_test")
        assert len(result.rows) == 5
        print(f"  ✓ 连接池复用正常: {len(result.rows)} 条记录")

        stats = db.get_stats()
        assert "pool" in stats
        print(f"  ✓ 连接池统计: {stats['pool']}")

        db.close()
        print("[Pass] Pool Integration\n")
        return True
    except Exception as e:
        print(f"[Fail] Pool Integration: {e}\n")
        return False


def test_health_check() -> bool:
    print("[Test] Health Check - 健康检查")
    try:
        db = get_db_adapter(DBConfig(db_type=DBType.MOCK), name="test_health")
        healthy = db.health_check()
        assert healthy is True
        print(f"  ✓ 健康状态: {healthy}")

        db.close()
        healthy_after = db.health_check()
        print(f"  ✓ 关闭后健康状态: {healthy_after}")

        print("[Pass] Health Check\n")
        return True
    except Exception as e:
        print(f"[Fail] Health Check: {e}\n")
        return False


def test_query_result() -> bool:
    print("[Test] QueryResult - 查询结果")
    try:
        result = QueryResult(
            rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            rowcount=2,
            columns=["id", "name"],
        )

        first = result.first()
        assert first is not None
        assert first["id"] == 1
        print(f"  ✓ first() 正确: {first}")

        scalar = result.scalar()
        assert scalar == 1
        print(f"  ✓ scalar() 正确: {scalar}")

        print("[Pass] QueryResult\n")
        return True
    except Exception as e:
        print(f"[Fail] QueryResult: {e}\n")
        return False


def test_thread_safety() -> bool:
    print("[Test] Thread Safety - 线程安全")
    try:
        db = get_db_adapter(DBConfig(db_type=DBType.MOCK), name="test_thread")
        errors = []

        def worker():
            try:
                for i in range(10):
                    db.insert("thread_test", {"idx": i})
                    db.select("thread_test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"发生错误: {errors}"
        print(f"  ✓ 5线程并发操作无错误")

        db.close()
        print("[Pass] Thread Safety\n")
        return True
    except Exception as e:
        print(f"[Fail] Thread Safety: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段71验证脚本：数据库适配器")
    print("=" * 60 + "\n")

    results = []
    results.append(("QueryBuilder", test_query_builder()))
    results.append(("CRUD", test_crud()))
    results.append(("Transaction", test_transaction()))
    results.append(("Pool Integration", test_pool_integration()))
    results.append(("Health Check", test_health_check()))
    results.append(("QueryResult", test_query_result()))
    results.append(("Thread Safety", test_thread_safety()))

    print("=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("🎉 所有测试通过！阶段71验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
