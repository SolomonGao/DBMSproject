"""
查询缓存模块

提供 LRU + TTL 缓存机制，减少重复查询数据库。
使用 orjson 进行高速序列化。
"""

import asyncio
import hashlib
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime, timedelta

# 尝试使用 orjson，回退到标准库
try:
    import orjson as json_module
    JSON_OPTS = json_module.OPT_SERIALIZE_NUMPY | json_module.OPT_NON_STR_KEYS
    USE_ORJSON = True
except ImportError:
    import json as json_module
    JSON_OPTS = 0
    USE_ORJSON = False
    logging.getLogger("cache").warning("orjson not installed, using standard json")

logger = logging.getLogger("query_cache")


class CacheEntry:
    """缓存条目"""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl_seconds
        self.access_count = 1
        self.last_accessed = self.created_at
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at
    
    def touch(self):
        """更新访问统计"""
        self.access_count += 1
        self.last_accessed = time.time()


class QueryCache:
    """
    异步查询缓存
    
    特性：
    - LRU 淘汰策略
    - TTL 过期控制
    - 内存上限保护
    - 命中率统计
    
    Usage:
        cache = QueryCache(maxsize=256, default_ttl=300)
        
        # 方式 1: 直接 get/set
        result = await cache.get_or_fetch(key, fetch_func)
        
        # 方式 2: 装饰器
        @cache.cached(ttl=600)
        async def expensive_query():
            return await db.fetchall(...)
    """
    
    def __init__(self, maxsize: int = 256, default_ttl: int = 300):
        self._cache: dict[str, CacheEntry] = {}
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        
        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def _make_key(self, query: str, params: Optional[tuple] = None) -> str:
        """
        生成缓存 key
        
        使用 MD5 哈希确保 key 长度固定，避免超长 SQL 导致内存问题。
        """
        if params:
            # 序列化参数
            if USE_ORJSON:
                params_str = json_module.dumps(params, option=JSON_OPTS).decode()
            else:
                params_str = json_module.dumps(params, default=str)
            key_data = f"{query}:{params_str}"
        else:
            key_data = query
        
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if entry.is_expired:
                del self._cache[key]
                return None
            
            entry.touch()
            self._hits += 1
            return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """设置缓存值"""
        async with self._lock:
            await self._set_unlocked(key, value, ttl)
    
    async def _set_unlocked(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """内部设置（无锁）"""
        # LRU 淘汰
        if len(self._cache) >= self._maxsize:
            await self._evict_lru()
        
        self._cache[key] = CacheEntry(value, ttl or self._default_ttl)
    
    async def _evict_lru(self) -> None:
        """LRU 淘汰：移除最久未访问的条目"""
        if not self._cache:
            return
        
        # 按最后访问时间排序，移除前 25%
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        evict_count = max(1, len(sorted_items) // 4)
        for key, _ in sorted_items[:evict_count]:
            del self._cache[key]
            self._evictions += 1
        
        logger.debug(f"LRU 淘汰: 移除 {evict_count} 个条目")
    
    async def get_or_fetch(
        self,
        query: str,
        params: Optional[tuple],
        fetch_func: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        缓存获取或执行查询
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            fetch_func: 实际查询函数
            ttl: 自定义过期时间（秒）
            
        Returns:
            查询结果（从缓存或新执行）
        """
        key = self._make_key(query, params)
        
        # 尝试从缓存获取
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"缓存命中: {key[:8]}...")
            return cached
        
        # 缓存未命中，执行查询
        self._misses += 1
        logger.debug(f"缓存未命中，执行查询: {key[:8]}...")
        
        result = await fetch_func()
        
        # 写入缓存（只缓存非空结果）
        if result:
            await self.set(key, result, ttl)
        
        return result
    
    def cached(self, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
        """
        装饰器：缓存函数结果
        
        Usage:
            @cache.cached(ttl=600)
            async def get_daily_stats(date: str):
                return await db.fetchall(...)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存 key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # 默认使用函数名 + 参数
                    cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                
                # 尝试获取缓存
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached
                
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 缓存结果
                if result:
                    await self.set(cache_key, result, ttl)
                
                return result
            
            # 附加清除缓存方法
            wrapper.cache_clear = lambda: self.clear()
            return wrapper
        return decorator
    
    async def clear(self) -> int:
        """清空缓存，返回清空的条目数"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """根据模式使缓存失效"""
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() 
                if pattern in key
            ]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2%}",
            "evictions": self._evictions,
        }
    
    async def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# 全局缓存实例
query_cache = QueryCache(maxsize=256, default_ttl=300)


async def cleanup_task(cache: QueryCache, interval: int = 60):
    """
    后台清理任务
    
    定期清理过期缓存条目。
    """
    while True:
        await asyncio.sleep(interval)
        try:
            cleaned = await cache.cleanup_expired()
            if cleaned > 0:
                logger.debug(f"清理过期缓存: {cleaned} 个条目")
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
