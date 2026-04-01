"""
性能对比测试：优化前 vs 优化后

测试项目：
1. 串行 vs 并行查询
2. 缓存命中率
3. 流式查询内存占用
4. 数据库端聚合 vs Python 端聚合
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
    """性能测试器"""
    
    def __init__(self):
        self.results = []
    
    async def setup(self):
        """初始化"""
        await DatabasePool.initialize()
        # 预热
        await GDELTServiceOptimized.warmup_connections(3)
    
    def benchmark(self, name: str):
        """装饰器：自动计时和内存统计"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # 开始内存追踪
                tracemalloc.start()
                start_mem = tracemalloc.get_traced_memory()[0]
                
                # 计时
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                
                # 内存统计
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
        """打印测试结果"""
        print("\n" + "="*80)
        print("📊 性能测试报告")
        print("="*80)
        print(f"{'测试项目':<30} {'耗时(ms)':<12} {'内存(KB)':<12} {'结果数':<10}")
        print("-"*80)
        
        for r in self.results:
            print(f"{r['name']:<30} {r['time_ms']:<12} {r['memory_kb']:<12} {r['result_count']:<10}")
        
        print("="*80)
        
        # 计算加速比
        baseline_times = {}
        for r in self.results:
            if "串行" in r['name'] or "原始" in r['name']:
                baseline_times[r['name']] = r['time_ms']
        
        print("\n🚀 优化效果：")
        for r in self.results:
            for baseline_name, baseline_time in baseline_times.items():
                if baseline_name.replace("串行", "").replace("原始", "") in r['name'] and r['name'] != baseline_name:
                    speedup = baseline_time / r['time_ms'] if r['time_ms'] > 0 else 0
                    print(f"  {baseline_name} → {r['name']}: 加速 {speedup:.2f}x")


async def main():
    bench = PerformanceBenchmark()
    await bench.setup()
    
    pool = DatabasePool()
    service_old = GDELTService()
    service_new = GDELTServiceOptimized()
    
    start_date, end_date = "2024-01-01", "2024-01-31"
    
    print("开始性能测试...")
    print(f"测试日期范围: {start_date} 至 {end_date}")
    print("-"*80)
    
    # ========== 测试 1: 串行 vs 并行查询 ==========
    
    @bench.benchmark("1a. 串行执行 4 个统计查询 (原始)")
    async def test_serial_queries():
        results = []
        results.append(await service_old.analyze_events_by_date(start_date, end_date))
        results.append(await service_old.analyze_top_actors(start_date, end_date))
        results.append(await service_old.analyze_conflict_cooperation_trend(start_date, end_date))
        # 再加一个自定义查询
        query = f"SELECT SQLDATE, COUNT(*) FROM events_table WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}' GROUP BY SQLDATE"
        results.append(await service_old.execute_sql(query))
        return results
    
    @bench.benchmark("1b. 并行执行 4 个统计查询 (优化)")
    async def test_parallel_queries():
        return await service_new.get_dashboard_data(start_date, end_date)
    
    await test_serial_queries()
    await test_parallel_queries()
    
    # ========== 测试 2: 缓存效果 ==========
    
    query = f"SELECT * FROM events_table WHERE SQLDATE BETWEEN '{start_date}' AND '{start_date}' LIMIT 50"
    
    @bench.benchmark("2a. 首次查询 (无缓存)")
    async def test_cache_miss():
        await query_cache.clear()
        return await service_new.execute_sql_cached(query, cache_ttl=60)
    
    @bench.benchmark("2b. 缓存命中查询")
    async def test_cache_hit():
        return await service_new.execute_sql_cached(query, cache_ttl=60)
    
    await test_cache_miss()
    await test_cache_hit()
    
    # ========== 测试 3: 数据库端聚合 vs Python 端 ==========
    
    @bench.benchmark("3a. Python 端分组聚合 (原始)")
    async def test_python_aggregate():
        # 原始方式：取出所有数据，Python 分组
        rows = await pool.fetchall(
            f"SELECT SQLDATE, GoldsteinScale FROM events_table "
            f"WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}' LIMIT 1000"
        )
        # Python 端聚合
        from collections import defaultdict
        result = defaultdict(lambda: {"count": 0, "sum": 0})
        for row in rows:
            date = row['SQLDATE']
            result[date]["count"] += 1
            result[date]["sum"] += row['GoldsteinScale'] or 0
        return list(result.items())
    
    @bench.benchmark("3b. 数据库端聚合 (优化)")
    async def test_db_aggregate():
        return await service_new.analyze_time_series_advanced(
            start_date, end_date, granularity="day"
        )
    
    await test_python_aggregate()
    await test_db_aggregate()
    
    # ========== 测试 4: 批量查询 vs 单条查询 ==========
    
    @bench.benchmark("4a. 串行单条查询 10 次")
    async def test_single_queries():
        results = []
        for i in range(10):
            row = await pool.fetchone(
                "SELECT * FROM events_table WHERE SQLDATE = %s LIMIT 1",
                (f"2024-01-{i+1:02d}",)
            )
            results.append(row)
        return results
    
    @bench.benchmark("4b. 批量查询 10 条")
    async def test_batch_query():
        ids = list(range(1000, 1010))  # 示例 ID
        return await service_new.batch_fetch_by_ids(ids)
    
    await test_single_queries()
    await test_batch_query()
    
    # 打印结果
    bench.print_results()
    
    # 缓存统计
    print("\n📦 缓存统计:")
    stats = query_cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    await DatabasePool.close()


if __name__ == "__main__":
    asyncio.run(main())
