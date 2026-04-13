#!/usr/bin/env python3
"""
databasestatusstatechecktool
used formonitorindexusecaseandquery性can
"""

import sys
import os
sys.path.insert(0, 'mcp_server')

from app.database.pool import DatabasePool
import asyncio

async def check_status():
    """check databasestatusstate"""
    await DatabasePool.initialize()
    pool = DatabasePool()
    
    print("=" * 70)
    print("📊 GDELT databasestatusstatecheck")
    print("=" * 70)
    
    # 1. tablesizeandrow count
    print("\n1️⃣  tablesizestatistics:")
    result = await pool.fetchone("""
        SELECT 
            table_rows,
            round((data_length / 1024 / 1024 / 1024), 2) AS data_gb,
            round((index_length / 1024 / 1024 / 1024), 2) AS index_gb,
            round(((data_length + index_length) / 1024 / 1024 / 1024), 2) AS total_gb
        FROM information_schema.TABLES
        WHERE table_schema = 'gdelt' 
          AND table_name = 'events_table'
    """)
    print(f"   总row count: {result['table_rows']:,}")
    print(f"   datasize: {result['data_gb']} GB")
    print(f"   indexsize: {result['index_gb']} GB")
    print(f"   total: {result['total_gb']} GB")
    
    # 2. indexcolumntable
    print("\n2️⃣  indexcolumntable:")
    indexes = await pool.fetchall("""
        SELECT 
            INDEX_NAME,
            COLUMN_NAME,
            INDEX_TYPE,
            CARDINALITY
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = 'gdelt'
          AND TABLE_NAME = 'events_table'
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """)
    
    current_idx = None
    for idx in indexes:
        if idx['INDEX_NAME'] != current_idx:
            current_idx = idx['INDEX_NAME']
            print(f"   📌 {current_idx} ({idx['INDEX_TYPE']}) - 基number: {idx['CARDINALITY']:,}")
        print(f"      └─ {idx['COLUMN_NAME']}")
    
    # 3. daterange
    print("\n3️⃣  datatimerange:")
    result = await pool.fetchone("""
        SELECT 
            MIN(SQLDATE) as min_date,
            MAX(SQLDATE) as max_date,
            COUNT(DISTINCT SQLDATE) as unique_days
        FROM events_table
    """)
    print(f"   most早: {result['min_date']}")
    print(f"   most晚: {result['max_date']}")
    print(f"   daynumber: {result['unique_days']}")
    
    # 4. locationprocessdataoverride
    print("\n4️⃣  locationprocessdataoverride:")
    result = await pool.fetchone("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ActionGeo_Lat IS NOT NULL 
                      AND ActionGeo_Long IS NOT NULL 
                      AND ActionGeo_Lat != 0 
                      AND ActionGeo_Long != 0 
                THEN 1 ELSE 0 END) as with_geo
        FROM events_table
    """)
    geo_pct = result['with_geo'] / result['total'] * 100 if result['total'] > 0 else 0
    print(f"   haslocationprocess坐mark: {result['with_geo']:,} / {result['total']:,} ({geo_pct:.1f}%)")
    
    # 5. importrecordlog
    print("\n5️⃣  CSV importrecordlog:")
    try:
        logs = await pool.fetchall("""
            SELECT file_name, imported_at, row_count 
            FROM _import_log 
            ORDER BY imported_at DESC 
            LIMIT 10
        """)
        if logs:
            for log in logs[:5]:
                print(f"   ✅ {log['file_name']}: {log['row_count']:,} row ({log['imported_at']})")
            if len(logs) > 5:
                print(f"   ... 还has {len(logs) - 5} file")
        else:
            print("   暂noimportrecordlog")
    except:
        print("   importrecordlogtablenotsave在")
    
    # 6. querycachestatusstate
    print("\n6️⃣  querycachestatusstate:")
    from app.cache import query_cache
    stats = query_cache.get_stats()
    print(f"   cacheitemproject: {stats['size']} / {stats['maxsize']}")
    print(f"   commandintimenumber: {stats['hits']:,}")
    print(f"   notcommandin: {stats['misses']:,}")
    print(f"   commandinrate: {stats['hit_rate']}")
    
    print("\n" + "=" * 70)
    print("checkcompleted！")
    print("=" * 70)
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(check_status())
