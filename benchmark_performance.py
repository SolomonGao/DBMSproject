"""
performance comparisontest：optimizationbefore vs optimizationafter

testproject：
1. serial vs androw查询
2. cache命中率
3. streaming查询memory占用
4. data库端aggregation vs Python 端aggregation
"""

import asyncio
import time
import tracemalloc
from datetime import datetime

import sys
sys.path.insert(0, 'mcp_server')

from app.database.pool import DatabasePool, get_db_pool
from app.services.gdelt import GDELTService
from app.services.gdelt_optimized import GDELTServiceOptimized
from app.cache import query_cache
from app.database.streaming import ParallelQuery


class PerformanceBenchmark:
    """performance test器"""
    
    def __init__(self):
        self.results = []
    
    async def setup(self):
        """初始化"""
        await DatabasePool.initialize()
        # pre热
        await GDELTServiceOptimized.warmup_connections(3)
    
    def benchmark(self, name: str):
        """装饰器：自动timing和memorystatistics"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # 开始memory追踪
                tracemalloc.start()
                start_mem = tracemalloc.get_traced_memory()[0]
                
                # timing
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                
                # memorystatistics
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                self.results.append({
                    "name": name,
                    "time_ms": round(elapsed * 1000, 2),
                    "memory_kb": round((peak - start_mem) / 1024, 2),
                    "result_count": len(result) if isinstance(result, list) else 0
                })
                
                return result
            return wrapper
        return decorator
    
    def print_results(self):
        """printtestresults"""
        print("\n" + "="*80)
        print("📊 performance testreport")
        print("="*80)
        print(f"{'testproject':<30} {'time cost(ms)':<12} {'memory(KB)':<12} {'resultsnumber':<10}")
        print("-"*80)
        
        for r in self.results:
            print(f"{r['name']:<30} {r['time_ms']:<12} {r['memory_kb']:<12} {r['result_count']:<10}")
        
        print("="*80)
        
        # 计算加速比
        baseline_times = {}
        for r in self.results:
            if "serial" in r['name'] or "原始" in r['name']:
                baseline_times[r['name']] = r['time_ms']
        
        print("\n🚀 optimization效果：")
        for r in self.results:
            for baseline_name, baseline_time in baseline_times.items():
                if baseline_name.replace("serial", "").replace("原始", "") in r['name'] and r['name'] != baseline_name:
                    speedup = baseline_time / r['time_ms'] if r['time_ms'] > 0 else 0
                    print(f"  {baseline_name} → {r['name']}: 加速 {speedup:.2f}x")


async def main():
    bench = PerformanceBenchmark()
    await bench.setup()
    
    pool = DatabasePool()
    service_old = GDELTService()
    service_new = GDELTServiceOptimized()
    
    start_date, end_date = "2024-01-01", "2024-01-31"
    
    print("开始performance test...")
    print(f"testdaterange: {start_date} 至 {end_date}")
    print("-"*80)
    
    # ========== test 1: serial vs androw查询 ==========
    
    @bench.benchmark("1a. serial执row 4 个statistics查询 (原始)")
    async def test_serial_queries():
        results = []
        results.append(await service_old.analyze_events_by_date(start_date, end_date))
        results.append(await service_old.analyze_top_actors(start_date, end_date))
        results.append(await service_old.analyze_conflict_cooperation_trend(start_date, end_date))
        # Plus a custom query
        query = f"SELECT SQLDATE, COUNT(*) FROM events_table WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}' GROUP BY SQLDATE"
        results.append(await service_old.execute_sql(query))
        return results
    
    @bench.benchmark("1b. androw执row 4 个statistics查询 (optimization)")
    async def test_parallel_queries():
        return await service_new.get_dashboard_data(start_date, end_date)
    
    await test_serial_queries()
    await test_parallel_queries()
    
    # ========== test 2: cache效果 ==========
    
    query = f"SELECT * FROM events_table WHERE SQLDATE BETWEEN '{start_date}' AND '{start_date}' LIMIT 50"
    
    @bench.benchmark("2a. 首次查询 (无cache)")
    async def test_cache_miss():
        await query_cache.clear()
        return await service_new.execute_sql_cached(query, cache_ttl=60)
    
    @bench.benchmark("2b. cache命中查询")
    async def test_cache_hit():
        return await service_new.execute_sql_cached(query, cache_ttl=60)
    
    await test_cache_miss()
    await test_cache_hit()
    
    # ========== test 3: data库端aggregation vs Python 端 ==========
    
    @bench.benchmark("3a. Python 端分组aggregation (原始)")
    async def test_python_aggregate():
        # 原始方式：取出alldata，Python 分组
        rows = await pool.fetchall(
            f"SELECT SQLDATE, GoldsteinScale FROM events_table "
            f"WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}' LIMIT 1000"
        )
        # Python 端aggregation
        from collections import defaultdict
        result = defaultdict(lambda: {"count": 0, "sum": 0})
        for row in rows:
            date = row['SQLDATE']
            result[date]["count"] += 1
            result[date]["sum"] += row['GoldsteinScale'] or 0
        return list(result.items())
    
    @bench.benchmark("3b. data库端aggregation (optimization)")
    async def test_db_aggregate():
        return await service_new.analyze_time_series_advanced(
            start_date, end_date, granularity="day"
        )
    
    await test_python_aggregate()
    await test_db_aggregate()
    
    # ========== test 4: batch查询 vs 单条查询 ==========
    
    @bench.benchmark("4a. serial单条查询 10 次")
    async def test_single_queries():
        results = []
        for i in range(10):
            row = await pool.fetchone(
                "SELECT * FROM events_table WHERE SQLDATE = %s LIMIT 1",
                (f"2024-01-{i+1:02d}",)
            )
            results.append(row)
        return results
    
    @bench.benchmark("4b. batch查询 10 条")
    async def test_batch_query():
        ids = list(range(1000, 1010))  # 示例 ID
        return await service_new.batch_fetch_by_ids(ids)
    
    await test_single_queries()
    await test_batch_query()
    
    # printresults
    bench.print_results()
    
    # cachestatistics
    print("\n📦 cachestatistics:")
    stats = query_cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    await DatabasePool.close()


if __name__ == "__main__":
    asyncio.run(main())
