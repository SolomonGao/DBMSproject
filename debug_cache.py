#!/usr/bin/env python3
"""
Cache Debug Tool - 验证cacheisNo工作

Usage:
    python debug_cache.py
"""

import sys
import asyncio

sys.path.insert(0, 'mcp_server')

from app.cache import query_cache
from app.database.pool import DatabasePool
from app.services.gdelt import GDELTService


async def test_cache():
    """测试cacheisNonormal工作"""
    print("🔍 cachedebug工具")
    print("=" * 60)
    
    # Initializedatabasejoin
    await DatabasePool.initialize()
    
    service = GDELTService()
    
    # 查看初始cache状态
    print("\n📊 初始cache状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 执row第一次query
    print("\n🔍 第一次query 'Virginia'...")
    start = asyncio.get_event_loop().time()
    result1 = await service.query_by_actor("Virginia", limit=10)
    elapsed1 = asyncio.get_event_loop().time() - start
    print(f"   耗时: {elapsed1:.3f}s")
    print(f"   结果长度: {len(result1)} 字符")
    
    # 查看cache状态
    print("\n📊 第一次queryaftercache状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 执row第二次相同query
    print("\n🔍 第二次query 'Virginia' (应该hitcache)...")
    start = asyncio.get_event_loop().time()
    result2 = await service.query_by_actor("Virginia", limit=10)
    elapsed2 = asyncio.get_event_loop().time() - start
    print(f"   耗时: {elapsed2:.3f}s")
    print(f"   结果长度: {len(result2)} 字符")
    
    # 查看cache状态
    print("\n📊 第二次queryaftercache状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 计算加速比
    if elapsed1 > 0:
        speedup = elapsed1 / elapsed2
        print(f"\n🚀 加速比: {speedup:.1f}x")
        
        if speedup > 10:
            print("✅ cache工作normal！")
        elif elapsed2 < 0.01:
            print("✅ 可能iscachehit（or者query本身就很快）")
        else:
            print("⚠️  可能没hashitcache")
    
    # 显示cache key Example
    print("\n🔑 cache Key 生成Example:")
    query = """SELECT SQLDATE, Actor1Name, Actor1CountryCode, 
               Actor2Name, Actor2CountryCode, EventCode,
               GoldsteinScale, AvgTone, SOURCEURL
        FROM events_table
        WHERE (Actor1Name LIKE '%Virginia%' OR Actor2Name LIKE '%Virginia%')
        
        ORDER BY SQLDATE DESC
        LIMIT 10"""
    key = query_cache._make_key(query, None)
    print(f"  query: {query[:50]}...")
    print(f"  Key: {key}")
    
    await DatabasePool.close()


if __name__ == "__main__":
    asyncio.run(test_cache())
