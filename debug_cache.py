#!/usr/bin/env python3
"""
Cache Debug Tool - 验证缓存是否工作

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
    """测试缓存是否正常工作"""
    print("🔍 缓存调试工具")
    print("=" * 60)
    
    # 初始化数据库连接
    await DatabasePool.initialize()
    
    service = GDELTService()
    
    # 查看初始缓存状态
    print("\n📊 初始缓存状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 执行第一次查询
    print("\n🔍 第一次查询 'Virginia'...")
    start = asyncio.get_event_loop().time()
    result1 = await service.query_by_actor("Virginia", limit=10)
    elapsed1 = asyncio.get_event_loop().time() - start
    print(f"   耗时: {elapsed1:.3f}s")
    print(f"   结果长度: {len(result1)} 字符")
    
    # 查看缓存状态
    print("\n📊 第一次查询后缓存状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 执行第二次相同查询
    print("\n🔍 第二次查询 'Virginia' (应该命中缓存)...")
    start = asyncio.get_event_loop().time()
    result2 = await service.query_by_actor("Virginia", limit=10)
    elapsed2 = asyncio.get_event_loop().time() - start
    print(f"   耗时: {elapsed2:.3f}s")
    print(f"   结果长度: {len(result2)} 字符")
    
    # 查看缓存状态
    print("\n📊 第二次查询后缓存状态:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 计算加速比
    if elapsed1 > 0:
        speedup = elapsed1 / elapsed2
        print(f"\n🚀 加速比: {speedup:.1f}x")
        
        if speedup > 10:
            print("✅ 缓存工作正常！")
        elif elapsed2 < 0.01:
            print("✅ 可能是缓存命中（或者查询本身就很快）")
        else:
            print("⚠️  可能没有命中缓存")
    
    # 显示缓存 key 示例
    print("\n🔑 缓存 Key 生成示例:")
    query = """SELECT SQLDATE, Actor1Name, Actor1CountryCode, 
               Actor2Name, Actor2CountryCode, EventCode,
               GoldsteinScale, AvgTone, SOURCEURL
        FROM events_table
        WHERE (Actor1Name LIKE '%Virginia%' OR Actor2Name LIKE '%Virginia%')
        
        ORDER BY SQLDATE DESC
        LIMIT 10"""
    key = query_cache._make_key(query, None)
    print(f"  查询: {query[:50]}...")
    print(f"  Key: {key}")
    
    await DatabasePool.close()


if __name__ == "__main__":
    asyncio.run(test_cache())
