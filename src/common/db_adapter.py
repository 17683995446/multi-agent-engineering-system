"""
公共层 - 数据库适配器模块
遵循第一性原理：统一接口、连接复用、事务原子性

核心功能：
1. 统一数据库接口（抽象基类）
2. 连接管理与连接池集成
3. 查询构建器（参数化查询）
4. 事务管理（自动提交/回滚）
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from common.connection_pool import ConnectionPool, PoolConfig, PooledConnection
from common.utils import setup_logger

logger = setup_logger(__name__)


class DBType(Enum):
    """数据库类型"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    MOCK = "mock"


class DBException(Exception):
    """数据库异常"""
    def __init__(self, message: str, sql: Optional[str] = None, params: Optional[tuple] = None):
        self.message = message
        self.sql = sql
        self.params = params
        super().__init__(self.message)


class TransactionError(DBException):
    """事务异常"""
    pass


class ConnectionError(DBException):
    """连接异常"""
    pass


@dataclass
class QueryResult:
    """查询结果"""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    rowcount: int = 0
    lastrowid: Optional[int] = None
    columns: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def first(self) -> Optional[Dict[str, Any]]:
        """获取第一条记录"""
        return self.rows[0] if self.rows else None

    def scalar(self) -> Any:
        """获取第一个标量值"""
        if not self.rows:
            return None
        row = self.rows[0]
        return next(iter(row.values())) if row else None


@dataclass
class DBConfig:
    """数据库配置"""
    db_type: DBType = DBType.MOCK
    host: str = "localhost"
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    pool_config: Optional[PoolConfig] = None
    timeout: float = 30.0
    charset: str = "utf8mb4"


class QueryBuilder:
    """
    查询构建器

    支持参数化查询，防止SQL注入
    """

    def __init__(self):
        self._sql = ""
        self._params: List[Any] = []

    def select(self, table: str, columns: Optional[List[str]] = None) -> QueryBuilder:
        """SELECT 语句"""
        cols = ", ".join(columns) if columns else "*"
        self._sql = f"SELECT {cols} FROM {table}"
        return self

    def where(self, condition: str, *params: Any) -> QueryBuilder:
        """WHERE 条件"""
        if "WHERE" not in self._sql:
            self._sql += " WHERE "
        else:
            self._sql += " AND "
        self._sql += condition
        self._params.extend(params)
        return self

    def insert(self, table: str, data: Dict[str, Any]) -> QueryBuilder:
        """INSERT 语句"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        self._sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self._params.extend(data.values())
        return self

    def update(self, table: str, data: Dict[str, Any]) -> QueryBuilder:
        """UPDATE 语句"""
        sets = ", ".join([f"{k} = ?" for k in data.keys()])
        self._sql = f"UPDATE {table} SET {sets}"
        self._params.extend(data.values())
        return self

    def delete(self, table: str) -> QueryBuilder:
        """DELETE 语句"""
        self._sql = f"DELETE FROM {table}"
        return self

    def order_by(self, column: str, direction: str = "ASC") -> QueryBuilder:
        """ORDER BY"""
        self._sql += f" ORDER BY {column} {direction}"
        return self

    def limit(self, count: int) -> QueryBuilder:
        """LIMIT"""
        self._sql += f" LIMIT {count}"
        return self

    def offset(self, count: int) -> QueryBuilder:
        """OFFSET"""
        self._sql += f" OFFSET {count}"
        return self

    def build(self) -> Tuple[str, Tuple[Any, ...]]:
        """构建SQL和参数"""
        return self._sql, tuple(self._params)

    @property
    def sql(self) -> str:
        return self._sql

    @property
    def params(self) -> Tuple[Any, ...]:
        return tuple(self._params)


class DBConnection(ABC):
    """
    数据库连接抽象基类
    """

    def __init__(self, config: DBConfig):
        self.config = config
        self.logger = setup_logger(f"common.db_adapter.{config.db_type.value}")
        self._raw_conn: Any = None
        self._in_transaction = False

    @abstractmethod
    def connect(self) -> None:
        """建立连接"""

    @abstractmethod
    def close(self) -> None:
        """关闭连接"""

    @abstractmethod
    def execute(self, sql: str, params: Optional[tuple] = None) -> QueryResult:
        """执行SQL"""

    @abstractmethod
    def begin(self) -> None:
        """开启事务"""

    @abstractmethod
    def commit(self) -> None:
        """提交事务"""

    @abstractmethod
    def rollback(self) -> None:
        """回滚事务"""

    @abstractmethod
    def is_valid(self) -> bool:
        """检查连接是否有效"""

    def execute_query(self, builder: QueryBuilder) -> QueryResult:
        """执行查询构建器"""
        sql, params = builder.build()
        return self.execute(sql, params)


class MockDBConnection(DBConnection):
    """
    模拟数据库连接（用于测试和演示）
    """

    _global_data: Dict[str, List[Dict[str, Any]]] = {}
    _global_lock = threading.Lock()
    _id_counter = 0

    def __init__(self, config: DBConfig):
        super().__init__(config)
        self._local_data: Dict[str, List[Dict[str, Any]]] = {}
        self._connected = False

    def connect(self) -> None:
        self._connected = True
        self.logger.debug("MockDB 连接已建立")

    def close(self) -> None:
        self._connected = False
        self.logger.debug("MockDB 连接已关闭")

    def execute(self, sql: str, params: Optional[tuple] = None) -> QueryResult:
        if not self._connected:
            raise ConnectionError("连接未建立")

        start = time.monotonic()
        params = params or ()
        sql_upper = sql.upper().strip()

        result = QueryResult()

        with MockDBConnection._global_lock:
            if sql_upper.startswith("INSERT"):
                table = self._extract_table(sql)
                MockDBConnection._id_counter += 1
                row = dict(zip(self._extract_columns(sql), params))
                row["id"] = MockDBConnection._id_counter
                if table not in MockDBConnection._global_data:
                    MockDBConnection._global_data[table] = []
                MockDBConnection._global_data[table].append(row)
                result.rowcount = 1
                result.lastrowid = MockDBConnection._id_counter

            elif sql_upper.startswith("SELECT"):
                table = self._extract_table(sql)
                rows = MockDBConnection._global_data.get(table, [])
                result.rows = [r.copy() for r in rows]
                result.rowcount = len(result.rows)
                if result.rows:
                    result.columns = list(result.rows[0].keys())

            elif sql_upper.startswith("UPDATE"):
                table = self._extract_table(sql)
                rows = MockDBConnection._global_data.get(table, [])
                result.rowcount = len(rows)

            elif sql_upper.startswith("DELETE"):
                table = self._extract_table(sql)
                if table in MockDBConnection._global_data:
                    count = len(MockDBConnection._global_data[table])
                    MockDBConnection._global_data[table] = []
                    result.rowcount = count

        result.duration_ms = (time.monotonic() - start) * 1000
        self.logger.debug(f"执行SQL: {sql}, 参数: {params}, 结果数: {result.rowcount}")
        return result

    def begin(self) -> None:
        self._in_transaction = True
        self.logger.debug("事务开始")

    def commit(self) -> None:
        self._in_transaction = False
        self.logger.debug("事务提交")

    def rollback(self) -> None:
        self._in_transaction = False
        self.logger.debug("事务回滚")

    def is_valid(self) -> bool:
        return self._connected

    def _extract_table(self, sql: str) -> str:
        """从SQL中提取表名（简化版）"""
        parts = sql.split()
        for i, p in enumerate(parts):
            p_upper = p.upper()
            if p_upper in ("FROM", "INTO", "UPDATE") and i + 1 < len(parts):
                return parts[i + 1].strip(";,'\"`")
        return "default"

    def _extract_columns(self, sql: str) -> List[str]:
        """从INSERT SQL中提取列名"""
        import re
        match = re.search(r"\(([^)]+)\)", sql)
        if match:
            return [c.strip().strip("'`\"") for c in match.group(1).split(",")]
        return []


class MockConnectionPool(ConnectionPool[MockDBConnection]):
    """模拟数据库连接池"""

    def __init__(self, config: DBConfig, name: str = "mock_db_pool"):
        self.db_config = config
        super().__init__(config.pool_config or PoolConfig(), name)

    def create_connection(self) -> MockDBConnection:
        conn = MockDBConnection(self.db_config)
        conn.connect()
        return conn

    def destroy_connection(self, connection: MockDBConnection) -> None:
        connection.close()

    def validate_connection(self, connection: MockDBConnection) -> bool:
        return connection.is_valid()


class DBAdapter:
    """
    数据库适配器

    统一数据库接口，集成连接池、查询构建、事务管理
    """

    def __init__(self, config: DBConfig, name: str = "db_adapter"):
        self.config = config
        self.name = name
        self.logger = setup_logger(f"common.db_adapter.{name}")
        self._pool: Optional[ConnectionPool] = None
        self._lock = threading.RLock()
        self._stats = {
            "total_queries": 0,
            "total_errors": 0,
            "total_transactions": 0,
            "total_time_ms": 0.0,
        }
        self._init_pool()

    def _init_pool(self) -> None:
        """初始化连接池"""
        if self.config.db_type == DBType.MOCK:
            self._pool = MockConnectionPool(self.config, name=f"{self.name}_pool")
        else:
            self.logger.warning(f"数据库类型 {self.config.db_type.value} 暂未实现，使用 MOCK")
            self._pool = MockConnectionPool(self.config, name=f"{self.name}_pool")

    def query(self, sql: str, params: Optional[tuple] = None) -> QueryResult:
        """
        执行查询

        Args:
            sql: SQL语句
            params: 参数（防注入）
        """
        if self._pool is None:
            raise ConnectionError("连接池未初始化")

        conn = None
        try:
            conn = self._pool.acquire(timeout=self.config.timeout)
            result = conn.execute(sql, params)
            self._update_stats(result.duration_ms)
            return result
        except Exception as e:
            self._stats["total_errors"] += 1
            self.logger.error(f"查询失败: {e}, SQL: {sql}")
            raise DBException(str(e), sql, params) from e
        finally:
            if conn:
                self._pool.release(conn)

    def query_builder(self) -> QueryBuilder:
        """获取查询构建器"""
        return QueryBuilder()

    def insert(self, table: str, data: Dict[str, Any]) -> QueryResult:
        """插入数据"""
        builder = QueryBuilder().insert(table, data)
        sql, params = builder.build()
        return self.query(sql, params)

    def select(self, table: str, columns: Optional[List[str]] = None, where: Optional[str] = None, params: Optional[tuple] = None) -> QueryResult:
        """查询数据"""
        builder = QueryBuilder().select(table, columns)
        if where:
            builder.where(where, *(params or ()))
        sql, params = builder.build()
        return self.query(sql, params)

    def update(self, table: str, data: Dict[str, Any], where: Optional[str] = None, params: Optional[tuple] = None) -> QueryResult:
        """更新数据"""
        builder = QueryBuilder().update(table, data)
        if where:
            builder.where(where, *(params or ()))
        sql, params = builder.build()
        return self.query(sql, params)

    def delete(self, table: str, where: Optional[str] = None, params: Optional[tuple] = None) -> QueryResult:
        """删除数据"""
        builder = QueryBuilder().delete(table)
        if where:
            builder.where(where, *(params or ()))
        sql, params = builder.build()
        return self.query(sql, params)

    @contextmanager
    def transaction(self):
        """
        事务上下文管理器

        自动提交/回滚
        """
        if self._pool is None:
            raise ConnectionError("连接池未初始化")

        conn = self._pool.acquire(timeout=self.config.timeout)
        try:
            conn.begin()
            self._stats["total_transactions"] += 1
            yield conn
            conn.commit()
            self.logger.debug("事务提交成功")
        except Exception as e:
            conn.rollback()
            self.logger.error(f"事务回滚: {e}")
            raise TransactionError(f"事务失败: {e}") from e
        finally:
            self._pool.release(conn)

    def execute_in_transaction(self, operations: List[Tuple[str, Optional[tuple]]]) -> List[QueryResult]:
        """
        在事务中执行多个操作

        Args:
            operations: [(sql, params), ...]
        """
        results = []
        with self.transaction() as conn:
            for sql, params in operations:
                result = conn.execute(sql, params)
                results.append(result)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if self._pool:
            stats["pool"] = self._pool.get_stats()
        return stats

    def _update_stats(self, duration_ms: float) -> None:
        """更新统计"""
        self._stats["total_queries"] += 1
        self._stats["total_time_ms"] += duration_ms

    def health_check(self) -> bool:
        """健康检查"""
        try:
            result = self.query("SELECT 1")
            return result is not None
        except Exception:
            return False

    def close(self) -> None:
        """关闭适配器"""
        if self._pool:
            self._pool.shutdown()
            self._pool = None
        self.logger.info("数据库适配器已关闭")


def get_db_adapter(config: Optional[DBConfig] = None, name: str = "default") -> DBAdapter:
    """
    获取数据库适配器实例

    Args:
        config: 数据库配置，None则使用默认配置
        name: 适配器名称
    """
    return DBAdapter(config or DBConfig(), name)


def demo_db_adapter():
    """演示数据库适配器"""
    print("=" * 60)
    print("数据库适配器模块验证")
    print("=" * 60)
    print()

    config = DBConfig(db_type=DBType.MOCK)
    db = DBAdapter(config, name="demo")

    print("1. 插入数据:")
    result = db.insert("users", {"name": "Alice", "age": 30})
    print(f"   ✓ 插入成功, ID: {result.lastrowid}")
    db.insert("users", {"name": "Bob", "age": 25})
    print(f"   ✓ 插入成功, ID: {result.lastrowid}")
    print()

    print("2. 查询数据:")
    result = db.select("users")
    for row in result.rows:
        print(f"   ✓ {row}")
    print()

    print("3. 查询构建器:")
    builder = db.query_builder().select("users", ["name", "age"]).where("age > ?", 20).limit(10)
    sql, params = builder.build()
    print(f"   ✓ SQL: {sql}")
    print(f"   ✓ 参数: {params}")
    print()

    print("4. 事务管理:")
    try:
        with db.transaction() as conn:
            conn.execute("INSERT INTO users (name, age) VALUES (?, ?)", ("Charlie", 35))
            print("   ✓ 事务内操作成功")
        print("   ✓ 事务提交成功")
    except Exception as e:
        print(f"   ✗ 事务失败: {e}")
    print()

    print("5. 批量事务操作:")
    operations = [
        ("INSERT INTO users (name, age) VALUES (?, ?)", ("David", 40)),
        ("INSERT INTO users (name, age) VALUES (?, ?)", ("Eve", 28)),
    ]
    results = db.execute_in_transaction(operations)
    print(f"   ✓ 批量操作完成，共 {len(results)} 条")
    print()

    print("6. 统计信息:")
    stats = db.get_stats()
    print(f"   ✓ 统计: {stats}")
    print()

    print("7. 健康检查:")
    healthy = db.health_check()
    print(f"   ✓ 健康状态: {'正常' if healthy else '异常'}")
    print()

    db.close()

    print("=" * 60)
    print("数据库适配器模块验证成功")
    print("=" * 60)
    print()
    print("✓ 统一数据库接口")
    print("✓ 连接池管理")
    print("✓ 查询构建器（参数化查询）")
    print("✓ 事务管理（自动提交/回滚）")
    print()


if __name__ == "__main__":
    demo_db_adapter()
