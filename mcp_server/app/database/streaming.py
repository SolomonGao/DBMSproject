"""
流式查询模块

提供生成器式的流式查询，处理大数据量时内存友好。
支持背压控制（backpressure）和超时控制。
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Any, Callable
from contextlib import asynccontextmanager

import aiomysql

from .pool import DatabasePool

logger = logging.getLogger("streaming")


class StreamingQuery:
    """
    流式查询执行器
    
    使用 MySQL Cursor 的 SSCursor (Server Side Cursor) 实现真正的流式读取，
    数据分块返回，避免一次性加载到内存。
    
    Usage:
        async for row in StreamingQuery(pool).stream("SELECT * FROM big_table"):
            process(row)
    """
    
    def __init__(
        self, 
        pool: DatabasePool,
        chunk_size: int = 100,
        timeout: float = 30.0
    ):
        self.pool = pool
        self.chunk_size = chunk_size
        self.timeout = timeout
    
    async def stream(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> AsyncGenerator[dict, None]:
        """
        流式查询 - 生成器返回结果
        
        Args:
            query: SQL 查询
            params: 参数
            chunk_size: 每次获取行数
            
        Yields:
            单行数据（字典格式）
        """
        conn = None
        try:
            # 获取普通连接（SSCursor 需要特殊处理）
            conn = await self.pool.pool.acquire()
            
            # 使用 SSDictCursor 服务端游标
            async with conn.cursor(aiomysql.SSDictCursor) as cur:
                # 设置读取超时
                await cur.execute("SET SESSION net_read_timeout = %s", (int(self.timeout),))
                
                # 执行查询
                await asyncio.wait_for(
                    cur.execute(query, params),
                    timeout=self.timeout
                )
                
                row_count = 0
                while True:
                    # 分批读取
                    rows = await cur.fetchmany(self.chunk_size)
                    if not rows:
                        break
                    
                    for row in rows:
                        row_count += 1
                        yield row
                
                logger.debug(f"流式查询完成: {row_count} 行")
                
        except asyncio.TimeoutError:
            logger.error(f"流式查询超时: {self.timeout}s")
            raise
        finally:
            if conn is not None:
                self.pool.pool.release(conn)
    
    async def stream_with_transform(
        self,
        query: str,
        transform: Callable[[dict], Any],
        params: Optional[tuple] = None
    ) -> AsyncGenerator[Any, None]:
        """
        流式查询 + 实时转换
        
        在流式读取的同时进行数据转换，减少内存占用。
        """
        async for row in self.stream(query, params):
            yield transform(row)
    
    async def count(self, query: str, params: Optional[tuple] = None) -> int:
        """
        流式计数 - 不加载所有数据
        """
        count = 0
        async for _ in self.stream(query, params):
            count += 1
        return count
    
    async def to_list(
        self,
        query: str,
        params: Optional[tuple] = None,
        limit: int = 10000
    ) -> list[dict]:
        """
        流式转列表（带上限保护）
        """
        results = []
        async for row in self.stream(query, params):
            results.append(row)
            if len(results) >= limit:
                logger.warning(f"达到上限 {limit}，截断结果")
                break
        return results


class ParallelQuery:
    """
    并行查询执行器
    
    并发执行多个独立查询，总耗时 = 最慢查询的耗时。
    """
    
    def __init__(self, pool: DatabasePool, max_concurrent: int = 5):
        self.pool = pool
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_single(
        self,
        query: str,
        params: Optional[tuple] = None,
        query_name: str = ""
    ) -> dict:
        """执行单个查询（带信号量控制并发）"""
        async with self.semaphore:
            start = asyncio.get_event_loop().time()
            try:
                rows = await self.pool.fetchall(query, params)
                elapsed = asyncio.get_event_loop().time() - start
                return {
                    "name": query_name,
                    "rows": rows,
                    "count": len(rows),
                    "elapsed_ms": round(elapsed * 1000, 2),
                    "error": None
                }
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start
                return {
                    "name": query_name,
                    "rows": [],
                    "count": 0,
                    "elapsed_ms": round(elapsed * 1000, 2),
                    "error": str(e)
                }
    
    async def execute_many(
        self,
        queries: list[tuple[str, Optional[tuple], str]]
    ) -> list[dict]:
        """
        并发执行多个查询
        
        Args:
            queries: [(query, params, name), ...]
            
        Returns:
            每个查询的结果列表
        """
        tasks = [
            self.execute_single(query, params, name)
            for query, params, name in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "name": queries[i][2],
                    "rows": [],
                    "count": 0,
                    "elapsed_ms": 0,
                    "error": str(result)
                })
            else:
                processed.append(result)
        
        return processed


class BatchedInserter:
    """
    批量插入优化器
    
    自动分批次插入，避免单条插入性能问题。
    """
    
    def __init__(self, pool: DatabasePool, batch_size: int = 1000):
        self.pool = pool
        self.batch_size = batch_size
        self.buffer = []
    
    async def add(self, record: dict) -> None:
        """添加记录到缓冲区"""
        self.buffer.append(record)
        
        if len(self.buffer) >= self.batch_size:
            await self.flush()
    
    async def flush(self) -> int:
        """将缓冲区写入数据库"""
        if not self.buffer:
            return 0
        
        # 构建批量插入 SQL
        columns = list(self.buffer[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f"`{c}`" for c in columns])
        
        query = f"INSERT INTO events_table ({columns_str}) VALUES ({placeholders})"
        
        # 提取值
        values = [
            tuple(record.get(c) for c in columns)
            for record in self.buffer
        ]
        
        # 使用 executemany
        affected = await self.pool.execute_many(query, values)
        
        count = len(self.buffer)
        self.buffer.clear()
        
        logger.debug(f"批量插入: {count} 条记录")
        return affected
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.flush()


# 便捷函数
async def stream_query(
    query: str,
    params: Optional[tuple] = None,
    chunk_size: int = 100,
    timeout: float = 30.0
) -> AsyncGenerator[dict, None]:
    """
    便捷函数：流式查询
    """
    pool = DatabasePool()
    streamer = StreamingQuery(pool, chunk_size, timeout)
    async for row in streamer.stream(query, params):
        yield row


async def parallel_queries(
    queries: list[tuple[str, Optional[tuple], str]],
    max_concurrent: int = 5
) -> list[dict]:
    """
    便捷函数：并行查询
    
    Args:
        queries: [(sql, params, name), ...]
        max_concurrent: 最大并发数
        
    Returns:
        查询结果列表
        
    Example:
        results = await parallel_queries([
            ("SELECT COUNT(*) FROM events WHERE SQLDATE='2024-01-01'", None, "jan1_count"),
            ("SELECT COUNT(*) FROM events WHERE SQLDATE='2024-01-02'", None, "jan2_count"),
        ])
    """
    pool = DatabasePool()
    executor = ParallelQuery(pool, max_concurrent)
    return await executor.execute_many(queries)
