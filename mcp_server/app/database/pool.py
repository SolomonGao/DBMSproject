"""
异步数据库连接池管理

使用 aiomysql 提供高性能的异步 MySQL 连接池。
"""

import os
import re
import asyncio
import logging
from typing import Optional, Any, Dict, List
from contextlib import asynccontextmanager

import aiomysql
from aiomysql import Pool, Connection, Cursor

from .errors import (
    DatabaseError,
    ConnectionLostError,
    classify_mysql_error,
)

# 配置日志
logger = logging.getLogger("db_pool")


class DatabasePool:
    """
    异步数据库连接池管理器
    
    单例模式确保全局只有一个连接池实例。
    提供连接获取、查询执行、事务管理、自动重试等功能。
    
    Usage:
        # 初始化连接池（应用启动时）
        await DatabasePool.initialize()
        
        # 执行查询（自动重试）
        pool = DatabasePool()
        results = await pool.fetchall("SELECT * FROM events_table LIMIT 10")
        
        # 使用事务
        async with pool.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO ...")
        
        # 关闭连接池
        await DatabasePool.close()
    """
    
    _instance: Optional["DatabasePool"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _pool: Optional[Pool] = None
    
    # 默认连接池配置
    DEFAULT_CONFIG = {
        "host": os.getenv("DB_HOST", "db"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "rootpassword"),
        "db": os.getenv("DB_NAME", "gdelt_db"),
        "charset": "utf8mb4",
        # 连接池配置
        "minsize": 1,
        "maxsize": 10,
        "autocommit": True,
        "connect_timeout": 30,
        # 连接回收：3600秒（1小时）后回收连接，防止 wait_timeout 断开
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
    }
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5  # 秒
    
    def __new__(cls) -> "DatabasePool":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    async def initialize(cls, **override_config) -> "DatabasePool":
        """
        初始化连接池
        
        Args:
            **override_config: 覆盖默认配置的参数
            
        Returns:
            DatabasePool: 连接池实例
        """
        async with cls._lock:
            if cls._pool is None:
                config = {**cls.DEFAULT_CONFIG, **override_config}
                try:
                    cls._pool = await aiomysql.create_pool(**config)
                    logger.info(f"连接池初始化成功: {config['host']}:{config['port']}")
                    
                    # 测试连接
                    async with cls._pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("SELECT 1")
                            await cur.fetchone()
                    logger.info("连接池测试通过")
                    
                except Exception as e:
                    logger.error(f"连接池初始化失败: {e}")
                    raise ConnectionError(f"数据库连接池初始化失败: {e}")
        return cls()
    
    @classmethod
    async def close(cls) -> None:
        """关闭连接池"""
        async with cls._lock:
            if cls._pool is not None:
                cls._pool.close()
                await cls._pool.wait_closed()
                cls._pool = None
                cls._instance = None
                logger.info("连接池已关闭")
    
    @property
    def pool(self) -> Pool:
        """获取底层连接池"""
        if self._pool is None:
            raise RuntimeError("连接池未初始化，请先调用 DatabasePool.initialize()")
        return self._pool
    
    async def _execute_with_retry(
        self, 
        operation: callable,
        operation_name: str = "operation"
    ) -> Any:
        """
        带重试机制的执行器
        
        对连接丢失类错误自动重试。
        
        Args:
            operation: 异步操作函数
            operation_name: 操作名称（用于日志）
            
        Returns:
            操作结果
            
        Raises:
            DatabaseError: 分类后的数据库异常
        """
        last_error = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await operation()
            except aiomysql.Error as e:
                db_error = classify_mysql_error(e)
                last_error = db_error
                
                # 只有可重试的错误才重试
                if db_error.is_retryable() and attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"{operation_name} 失败 (尝试 {attempt}/{self.MAX_RETRIES}): "
                        f"{db_error.error_code} - {db_error}"
                    )
                    await asyncio.sleep(self.RETRY_DELAY * attempt)  # 指数退避
                    continue
                else:
                    # 不可重试的错误或已用完重试次数
                    raise db_error
            except DatabaseError:
                # 已经是分类后的错误，直接抛出
                raise
            except Exception:
                # 非数据库错误直接抛出
                raise
        
        raise last_error
    
    @asynccontextmanager
    async def acquire(self) -> Connection:
        """
        获取连接上下文管理器（带探活检测）
        
        Usage:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
        """
        conn = None
        try:
            conn = await self.pool.acquire()
            
            # 简单探活：检查连接是否可用
            try:
                conn.ping(reconnect=True)
            except:
                pass  # ping 失败也没关系，aiomysql 会自动处理
            
            yield conn
        finally:
            if conn is not None:
                self.pool.release(conn)
    
    @asynccontextmanager
    async def transaction(self) -> Connection:
        """
        事务上下文管理器
        
        自动处理 commit 和 rollback。
        
        Usage:
            async with db_pool.transaction() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("INSERT INTO ...")
        """
        conn = None
        try:
            conn = await self.pool.acquire()
            await conn.begin()
            yield conn
            await conn.commit()
            logger.debug("事务提交成功")
        except Exception as e:
            if conn is not None:
                await conn.rollback()
                logger.warning(f"事务回滚: {e}")
            raise
        finally:
            if conn is not None:
                self.pool.release(conn)
    
    async def fetchall(
        self, 
        query: str, 
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        执行查询，返回所有结果（带重试）
        
        Args:
            query: SQL 查询语句
            params: 查询参数（防止 SQL 注入）
            
        Returns:
            结果列表，每行是一个字典
            
        Raises:
            DatabaseError: 数据库错误（已分类）
        """
        async def _do_fetch():
            async with self.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, params)
                    return await cur.fetchall()
        
        return await self._execute_with_retry(_do_fetch, "fetchall")
    
    async def fetchone(
        self, 
        query: str, 
        params: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """
        执行查询，返回第一条结果（带重试）
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            单行字典结果，如果没有则返回 None
        """
        async def _do_fetch():
            async with self.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, params)
                    return await cur.fetchone()
        
        return await self._execute_with_retry(_do_fetch, "fetchone")
    
    async def execute(
        self, 
        query: str, 
        params: Optional[tuple] = None
    ) -> int:
        """
        执行非查询语句（INSERT/UPDATE/DELETE，带重试）
        
        Args:
            query: SQL 语句
            params: 查询参数
            
        Returns:
            受影响的行数
        """
        async def _do_execute():
            async with self.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    await conn.commit()
                    return cur.rowcount
        
        return await self._execute_with_retry(_do_execute, "execute")
    
    async def execute_many(
        self, 
        query: str, 
        params_list: List[tuple]
    ) -> int:
        """
        批量执行同一语句（带重试）
        
        Args:
            query: SQL 语句
            params_list: 参数列表
            
        Returns:
            受影响的行数
        """
        async def _do_execute_many():
            async with self.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.executemany(query, params_list)
                    await conn.commit()
                    return cur.rowcount
        
        return await self._execute_with_retry(_do_execute_many, "execute_many")
    
    def _sanitize_table_name(self, table_name: str) -> str:
        """
        安全校验表名
        
        只允许字母、数字、下划线。
        
        Args:
            table_name: 原始表名
            
        Returns:
            校验后的表名
            
        Raises:
            ValueError: 表名不合法
        """
        if not table_name:
            raise ValueError("表名不能为空")
        
        # 只允许字母、数字、下划线
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValueError(f"非法表名: {table_name} (只允许字母、数字、下划线)")
        
        return table_name
    
    async def get_schema(self, table_name: str = "events_table") -> List[Dict[str, Any]]:
        """
        获取表结构信息（安全拼接表名）
        
        Args:
            table_name: 表名
            
        Returns:
            字段信息列表
        """
        # 安全校验表名后拼接（表名不能用参数化）
        safe_table_name = self._sanitize_table_name(table_name)
        query = f"DESCRIBE `{safe_table_name}`"
        
        return await self.fetchall(query)
    
    async def get_tables(self) -> List[str]:
        """
        获取数据库中所有表名
        
        Returns:
            表名列表
        """
        result = await self.fetchall("SHOW TABLES")
        # 提取表名（字典的第一个值）
        tables = []
        for row in result:
            # SHOW TABLES 返回的列名是 Tables_in_<dbname>
            table_name = list(row.values())[0]
            tables.append(table_name)
        return tables
    
    async def health_check(self) -> Dict[str, Any]:
        """
        详细健康检查
        
        Returns:
            健康状态字典
        """
        import time
        
        start_time = time.time()
        try:
            # 执行简单查询测试
            result = await self.fetchone("SELECT 1 as test, NOW() as server_time, CONNECTION_ID() as conn_id")
            latency_ms = round((time.time() - start_time) * 1000, 2)
            
            # 获取连接池状态
            pool_size = self.pool.size if self.pool else 0
            free_connections = self.pool.freesize if self.pool else 0
            
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "server_time": result.get("server_time") if result else None,
                "connection_id": result.get("conn_id") if result else None,
                "pool_size": pool_size,
                "free_connections": free_connections,
                "maxsize": self.DEFAULT_CONFIG.get("maxsize", 10),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "latency_ms": round((time.time() - start_time) * 1000, 2),
            }


# 全局连接池实例引用
_db_pool: Optional[DatabasePool] = None


async def get_db_pool() -> DatabasePool:
    """
    获取数据库连接池实例
    
    如果连接池未初始化，会自动初始化。
    
    Returns:
        DatabasePool: 连接池实例
    """
    global _db_pool
    if _db_pool is None:
        _db_pool = await DatabasePool.initialize()
    return _db_pool


async def close_db_pool() -> None:
    """关闭全局连接池"""
    global _db_pool
    if _db_pool is not None:
        await DatabasePool.close()
        _db_pool = None
