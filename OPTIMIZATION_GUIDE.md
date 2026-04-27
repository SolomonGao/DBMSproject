# 🚀 GDELT MCP 查询优化指南

> 代码层面的前沿优化方案，无需修改部署架构

---

## 📊 优化效果概览

| 优化技术 | 适用场景 | 预期提升 | 代码位置 |
|---------|---------|---------|---------|
| **并行查询** | 多个独立统计 | 3-5x | `core_queries.py` |
| **查询缓存** | 重复查询 | 10-100x | `cache.py` |
| **流式查询** | 大数据量读取 | 内存 ↓ 90% | `streaming.py` |
| **数据库聚合** | GROUP BY 统计 | 5-10x | `core_queries.py` |
| **预编译批量** | 批量 ID 查询 | 10x | `core_queries.py` |

---

## 🛠️ 快速接入

### 1. 安装依赖

```bash
pip install orjson  # 可选，但强烈推荐（比 json 快 10x）
```

### 2. 替换服务层

```python
# 数据服务层直接调用共享查询
from mcp_server.app.queries import core_queries
from mcp_server.app.database.pool import DatabasePool

pool = await DatabasePool.initialize()
dashboard = await core_queries.get_dashboard_data("2024-01-01", "2024-01-31", pool)
```

### 3. 使用并行查询

```python
# 原来：串行 4 个查询 ≈ 2s
result1 = await service.analyze_events_by_date(d1, d2)
result2 = await service.analyze_top_actors(d1, d2)
result3 = await service.analyze_conflict_cooperation_trend(d1, d2)

# 优化后：并行 ≈ 0.5s
dashboard = await service.get_dashboard_data(d1, d2)
# 返回包含以上所有结果
```

---

## 📖 详细优化方案

### 方案 1: 查询结果缓存 (cache.py)

**问题**: 相同查询重复执行浪费资源

**解决**: LRU + TTL 双机制缓存

```python
from app.cache import query_cache

# 自动缓存
rows = await query_cache.get_or_fetch(
    query="SELECT ...",
    params=(start_date, end_date),
    fetch_func=lambda: pool.fetchall(query, params),
    ttl=300  # 5分钟过期
)

# 装饰器方式
@query_cache.cached(ttl=600)
async def get_daily_stats(date: str):
    return await db.fetchall("SELECT ...")
```

**适用**:
- ✅ 统计数据（变化少）
- ✅ 热点查询
- ❌ 实时性要求高的数据

---

### 方案 2: 并行查询 (streaming.py)

**问题**: 串行执行 N 个查询需要 N 倍时间

**解决**: `asyncio.gather` 并发执行

```python
from app.database.streaming import parallel_queries

# 并发执行多个查询
results = await parallel_queries([
    ("SELECT COUNT(*) FROM events WHERE date='2024-01-01'", None, "jan1"),
    ("SELECT COUNT(*) FROM events WHERE date='2024-01-02'", None, "jan2"),
    ("SELECT COUNT(*) FROM events WHERE date='2024-01-03'", None, "jan3"),
], max_concurrent=5)

# 总耗时 = 最慢的那个查询，而不是总和
```

**适用**:
- ✅ 仪表盘多维度统计
- ✅ 独立查询之间无依赖

---

### 方案 3: 流式查询 (streaming.py)

**问题**: `fetchall()` 大数据量内存爆炸

**解决**: 生成器逐行读取

```python
from app.database.streaming import stream_query

# 内存占用稳定，无论数据量多大
async for row in stream_query(
    "SELECT * FROM events WHERE Actor1Name LIKE '%China%'",
    chunk_size=100  # 每批读取 100 行
):
    process(row)  # 处理单行
```

**适用**:
- ✅ 导出大量数据
- ✅ 逐行处理场景
- ✅ 数据量 > 10,000 行

---

### 方案 4: 数据库端聚合

**问题**: Python 端聚合需要传输大量数据

**解决**: SQL 中完成 GROUP BY、AVG、SUM

```python
# ❌ 低效：传输所有数据到 Python
rows = await pool.fetchall("SELECT * FROM events ...")  # 10万行
result = {}
for row in rows:
    result[row['date']] = result.get(row['date'], 0) + 1

# ✅ 高效：只传输聚合结果
rows = await pool.fetchall("""
    SELECT SQLDATE, COUNT(*) as cnt, AVG(GoldsteinScale)
    FROM events 
    GROUP BY SQLDATE
""")  # 只有 30 行
```

**进阶技巧**:

```sql
-- 数据库端计算冲突/合作比例
SELECT 
    SQLDATE,
    ROUND(
        SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) as conflict_pct
FROM events
GROUP BY SQLDATE
```

---

### 方案 5: 批量查询优化

**问题**: N 次单条查询 = N 次网络往返

**解决**: 预编译 + IN 语句批量查询

```python
# ❌ 低效：10 次查询
for id in ids:
    row = await pool.fetchone("SELECT * FROM events WHERE id = %s", (id,))

# ✅ 高效：1 次查询
placeholders = ', '.join(['%s'] * len(ids))
rows = await pool.fetchall(
    f"SELECT * FROM events WHERE GlobalEventID IN ({placeholders})",
    tuple(ids)
)
```

---

## 🧪 性能测试

运行对比测试：

```bash
python run_backend.py
# API 文档: http://localhost:8000/docs
```

预期输出：

```
📊 性能测试报告
================================================================================
测试项目                       耗时(ms)     内存(KB)     结果数
--------------------------------------------------------------------------------
1a. 串行执行 4 个统计查询 (原始)  1850.32      5120.50      4
1b. 并行执行 4 个统计查询 (优化)   420.15       2048.20      4
2a. 首次查询 (无缓存)            125.40       1024.00      50
2b. 缓存命中查询                  0.05         0.50         50
3a. Python 端分组聚合 (原始)      850.60       8192.00      1000
3b. 数据库端聚合 (优化)           120.30       512.00       30
================================================================================

🚀 优化效果：
  串行 4 个统计查询 → 并行 4 个统计查询: 加速 4.40x
  首次查询 → 缓存命中: 加速 2508x
  Python 聚合 → 数据库聚合: 加速 7.07x
```

---

## 🔧 MySQL 索引优化

配合代码优化，确保数据库索引到位：

```sql
-- 1. 日期索引（最关键）
ALTER TABLE events_table ADD INDEX idx_sqldate (SQLDATE);

-- 2. 复合索引（时间 + 参与方）
ALTER TABLE events_table ADD INDEX idx_date_actor (SQLDATE, Actor1Name(20));

-- 3. 覆盖索引（常用查询字段）
ALTER TABLE events_table ADD INDEX idx_cover (
    SQLDATE, 
    GoldsteinScale, 
    AvgTone,
    Actor1Name(20)
);

-- 4. 空间索引（地理查询）
ALTER TABLE events_table ADD SPATIAL INDEX idx_geo (ActionGeo_Point);
```

---

## 📈 监控指标

### 查看缓存命中率

```python
from app.cache import query_cache
print(query_cache.get_stats())
# {'hits': 150, 'misses': 20, 'hit_rate': '88.24%'}
```

### 查看查询耗时

```python
# 所有优化查询都返回耗时信息
dashboard = await service.get_dashboard_data(d1, d2)
for name, data in dashboard.items():
    print(f"{name}: {data['elapsed_ms']}ms")
```

---

## 🎯 优化选择指南

| 你的场景 | 推荐优化 | 代码示例 |
|---------|---------|---------|
| 仪表盘多图表 | 并行查询 | `get_dashboard_data()` |
| 用户重复查询相同数据 | 查询缓存 | `@query_cache.cached()` |
| 导出/处理大量数据 | 流式查询 | `stream_events_by_actor()` |
| 统计报表 | 数据库聚合 | `analyze_time_series_advanced()` |
| 根据 ID 列表查详情 | 批量查询 | `batch_fetch_by_ids()` |
| 启动慢 | 连接预热 | `warmup_connections(5)` |

---

## 🐳 Docker 环境特别优化

### 连接池配置

```python
# pool.py 中的优化配置
DEFAULT_CONFIG = {
    "minsize": 2,        # 最小连接数（保持热连接）
    "maxsize": 20,       # 最大连接数（根据容器 CPU 调整）
    "pool_recycle": 300, # 5 分钟回收（防止 Docker 网络超时）
    "connect_timeout": 10,
}
```

### 启动时预热

```python
# backend/main.py 启动时
from backend.services.data_service import DataService

@asynccontextmanager
async def lifespan(app: FastAPI):
    await data_service.initialize()  # 预热连接池
    yield
    await data_service.close()
```

---

## ⚠️ 注意事项

1. **缓存一致性**: 数据更新后记得清缓存 `await query_cache.clear()`

2. **并发限制**: 并行查询用 `Semaphore` 控制，避免压垮数据库

3. **流式连接**: 流式查询使用 SSCursor，占用连接时间较长

4. **内存监控**: 缓存设置 `maxsize`，防止无限增长

---

## 📚 参考

- [orjson 文档](https://github.com/ijl/orjson) - 高性能 JSON 库
- [aiomysql 文档](https://github.com/aio-libs/aiomysql) - 异步 MySQL
- MySQL `EXPLAIN` 分析慢查询
