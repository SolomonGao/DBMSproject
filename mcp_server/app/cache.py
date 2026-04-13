"""
Query Cache Module

Provides LRU + TTL caching mechanism to reduce repeated database queries.
Uses orjson for high-speed serialization.
"""

import asyncio
import hashlib
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime, timedelta

# Try to use orjson, fallback to standard library
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
    """Cache entry"""
    
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
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = time.time()


class QueryCache:
    """
    Async Query Cache
    
    Features:
    - LRU eviction policy
    - TTL expiration control
    - Memory limit protection
    - Hit rate statistics
    
    Usage:
        cache = QueryCache(maxsize=256, default_ttl=300)
        
        # Method 1: Direct get/set
        result = await cache.get_or_fetch(key, fetch_func)
        
        # Method 2: Decorator
        @cache.cached(ttl=600)
        async def expensive_query():
            return await db.fetchall(...)
    """
    
    def __init__(self, maxsize: int = 256, default_ttl: int = 300):
        self._cache: dict[str, CacheEntry] = {}
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def _make_key(self, query: str, params: Optional[tuple] = None) -> str:
        """
        Generate cache key
        
        Uses MD5 hash to ensure fixed key length, avoiding memory issues from超长 SQL.
        """
        if params:
            # Serialize parameters
            if USE_ORJSON:
                params_str = json_module.dumps(params, option=JSON_OPTS).decode()
            else:
                params_str = json_module.dumps(params, default=str)
            key_data = f"{query}:{params_str}"
        else:
            key_data = query
        
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
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
        """Set cached value"""
        async with self._lock:
            await self._set_unlocked(key, value, ttl)
    
    async def _set_unlocked(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """Internal set (no lock)"""
        # LRU eviction
        if len(self._cache) >= self._maxsize:
            await self._evict_lru()
        
        self._cache[key] = CacheEntry(value, ttl or self._default_ttl)
    
    async def _evict_lru(self) -> None:
        """LRU eviction: remove least recently accessed entries"""
        if not self._cache:
            return
        
        # Sort by last access time, remove top 25%
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        evict_count = max(1, len(sorted_items) // 4)
        for key, _ in sorted_items[:evict_count]:
            del self._cache[key]
            self._evictions += 1
        
        logger.debug(f"LRU eviction: removed {evict_count} entries")
    
    async def get_or_fetch(
        self,
        query: str,
        params: Optional[tuple],
        fetch_func: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Cache get or execute query
        
        Args:
            query: SQL query statement
            params: Query parameters
            fetch_func: Actual query function
            ttl: Custom expiration time (seconds)
            
        Returns:
            Query result (from cache or newly executed)
        """
        key = self._make_key(query, params)
        
        # Try to get from cache
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"Cache hit: {key[:8]}...")
            return cached
        
        # Cache miss, execute query
        self._misses += 1
        logger.debug(f"Cache miss, executing query: {key[:8]}...")
        
        result = await fetch_func()
        
        # Write to cache (only cache non-empty results)
        if result:
            await self.set(key, result, ttl)
        
        return result
    
    def cached(self, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
        """
        Decorator: Cache function results
        
        Usage:
            @cache.cached(ttl=600)
            async def get_daily_stats(date: str):
                return await db.fetchall(...)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default use function name + parameters
                    cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                
                # Try to get from cache
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                if result:
                    await self.set(cache_key, result, ttl)
                
                return result
            
            # Attach cache clear method
            wrapper.cache_clear = lambda: self.clear()
            return wrapper
        return decorator
    
    async def clear(self) -> int:
        """Clear cache, return number of cleared entries"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache by pattern"""
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() 
                if pattern in key
            ]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
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
        """Clean up expired entries, return count cleaned"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# Global cache instance
query_cache = QueryCache(maxsize=256, default_ttl=300)


async def cleanup_task(cache: QueryCache, interval: int = 60):
    """
    Background cleanup task
    
    Periodically clean up expired cache entries.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            cleaned = await cache.cleanup_expired()
            if cleaned > 0:
                logger.debug(f"Cleaned expired cache: {cleaned} entries")
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
