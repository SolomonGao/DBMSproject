#!/usr/bin/env python3
"""
Cache Debug Tool - validatecacheisNowork

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
    """testcacheisNonormalwork"""
    print("🔍 cachedebugtool")
    print("=" * 60)
    
    # Initializedatabasejoin
    await DatabasePool.initialize()
    
    service = GDELTService()
    
    # queryseeinitialstartcachestatusstate
    print("\n📊 initialstartcachestatusstate:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # execrowNo.onetimequery
    print("\n🔍 No.onetimequery 'Virginia'...")
    start = asyncio.get_event_loop().time()
    result1 = await service.query_by_actor("Virginia", limit=10)
    elapsed1 = asyncio.get_event_loop().time() - start
    print(f"   consumewhen: {elapsed1:.3f}s")
    print(f"   resultresultlongschedule: {len(result1)} character")
    
    # queryseecachestatusstate
    print("\n📊 No.onetimequeryaftercachestatusstate:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # execrowNo.twotimesamequery
    print("\n🔍 No.twotimequery 'Virginia' (shouldthishitcache)...")
    start = asyncio.get_event_loop().time()
    result2 = await service.query_by_actor("Virginia", limit=10)
    elapsed2 = asyncio.get_event_loop().time() - start
    print(f"   consumewhen: {elapsed2:.3f}s")
    print(f"   resultresultlongschedule: {len(result2)} character")
    
    # queryseecachestatusstate
    print("\n📊 No.twotimequeryaftercachestatusstate:")
    stats = query_cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # calculateaddspeed ratio
    if elapsed1 > 0:
        speedup = elapsed1 / elapsed2
        print(f"\n🚀 addspeed ratio: {speedup:.1f}x")
        
        if speedup > 10:
            print("✅ cacheworknormal！")
        elif elapsed2 < 0.01:
            print("✅ cancaniscachehit（orpersonquerythisbodyveryfast）")
        else:
            print("⚠️  cancannohashitcache")
    
    # displaycache key Example
    print("\n🔑 cache Key generateExample:")
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
