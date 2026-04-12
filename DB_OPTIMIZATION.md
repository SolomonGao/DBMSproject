# 数据库优化记录

> 针对 1500万+ 数据量的 MySQL 优化方案

---

## 数据规模

| 指标 | 数值 |
|------|------|
| 总行数 | 15,731,577 条 |
| CSV 文件数 | 100 个 |
| 时间范围 | 2024年北美事件 |
| 表大小 | ~15GB |

---

## 索引清单

### 已有索引

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| PRIMARY | GlobalEventID | BTREE | 主键，唯一约束 |
| idx_sqldate | SQLDATE | BTREE | 时间范围查询 |
| idx_actor1 | Actor1Name(20) | BTREE | 参与方查询 |
| idx_actor2 | Actor2Name(20) | BTREE | 参与方查询 |
| idx_goldstein | GoldsteinScale | BTREE | 冲突强度查询 |
| idx_lat | ActionGeo_Lat | BTREE | 地理纬度查询 |
| idx_long | ActionGeo_Long | BTREE | 地理经度查询 |
| idx_geo_point | ActionGeo_Point | SPATIAL | 空间查询 |

### 新增优化索引（2024-04-02）

```sql
-- 复合索引1：地理+日期（优化地理热力图）
ALTER TABLE events_table 
ADD INDEX idx_geo_date (ActionGeo_Lat, ActionGeo_Long, SQLDATE);

-- 复合索引2：日期+地理（优化时间+地理组合查询）
ALTER TABLE events_table 
ADD INDEX idx_date_geo (SQLDATE, ActionGeo_Lat, ActionGeo_Long);

-- 复合索引3：日期+Actor（优化时间+参与方组合查询）
ALTER TABLE events_table 
ADD INDEX idx_date_actor (SQLDATE, Actor1Name(20));
```

### 索引创建命令汇总

```sql
-- 基础索引（已有）
ALTER TABLE events_table ADD INDEX idx_sqldate (SQLDATE);
ALTER TABLE events_table ADD INDEX idx_actor1 (Actor1Name(20));
ALTER TABLE events_table ADD INDEX idx_actor2 (Actor2Name(20));
ALTER TABLE events_table ADD INDEX idx_goldstein (GoldsteinScale);
ALTER TABLE events_table ADD INDEX idx_lat (ActionGeo_Lat);
ALTER TABLE events_table ADD INDEX idx_long (ActionGeo_Long);

-- 复合索引（优化大数据量查询）
ALTER TABLE events_table ADD INDEX idx_geo_date (ActionGeo_Lat, ActionGeo_Long, SQLDATE);
ALTER TABLE events_table ADD INDEX idx_date_geo (SQLDATE, ActionGeo_Lat, ActionGeo_Long);
ALTER TABLE events_table ADD INDEX idx_date_actor (SQLDATE, Actor1Name(20));

-- 空间索引（可选）
ALTER TABLE events_table ADD SPATIAL INDEX idx_geo_point (ActionGeo_Point);
```

---

## 查询优化记录

### 优化1：地理热力图查询

**问题**：查询 2024-01-01 至 2024-01-31 的热力图需要 62 秒

**原因**：对整个 1500万 条数据表进行 GROUP BY，没有有效过滤

**解决方案**：
```python
# 优化前：全表 GROUP BY
query = """
SELECT 
    ROUND(ActionGeo_Lat, 2) as lat,
    ROUND(ActionGeo_Long, 2) as lng,
    COUNT(*) as intensity
FROM events_table
WHERE SQLDATE BETWEEN %s AND %s
GROUP BY ROUND(ActionGeo_Lat, 2), ROUND(ActionGeo_Long, 2)
"""

# 优化后：子查询先过滤 + 限制数据量
query = """
SELECT 
    ROUND(lat, 2) as lat,
    ROUND(lng, 2) as lng,
    COUNT(*) as intensity
FROM (
    SELECT 
        ActionGeo_Lat as lat,
        ActionGeo_Long as lng
    FROM events_table
    WHERE SQLDATE BETWEEN %s AND %s
      AND ActionGeo_Lat != 0          -- 过滤无效坐标
      AND ActionGeo_Long != 0
    LIMIT 100000                      -- 限制处理数据量
) filtered
GROUP BY ROUND(lat, 2), ROUND(lng, 2)
"""
```

**效果**：62秒 → 5-10秒

---

### 优化2：地理位置查询

**问题**：查询半径 100km 内的事件需要 129 秒

**原因**：使用 ST_Distance_Sphere 对每个点计算距离，无法使用索引

**解决方案**：
```python
# 优化前：对每个点计算距离
query = """
SELECT ...
WHERE ST_Distance_Sphere(ActionGeo_Point, POINT(lat, lon)) <= %s
"""

# 优化后：边界框预过滤 + Haversine 公式
# 1. 先用边界框快速过滤（利用 idx_geo_date 索引）
lat_delta = radius_km / 111.0
lon_delta = radius_km / (111.0 * cos(lat))

query = """
SELECT ...,
    (6371 * acos(...)) AS distance_km  -- Haversine 公式
FROM events_table
WHERE ActionGeo_Lat BETWEEN %s AND %s   -- 使用索引！
  AND ActionGeo_Long BETWEEN %s AND %s
HAVING distance_km <= %s
"""
```

**效果**：129秒 → 2-5秒

---

## 性能对比

| 查询类型 | 优化前 | 优化后 | 提升 |
|----------|--------|--------|------|
| 地理热力图 | 62秒 | 5-10秒 | 6-12x |
| 地理位置查询 | 129秒 | 2-5秒 | 25-60x |
| 按演员查询 | ~2秒 | ~0.5秒 | 4x |
| 并行仪表盘 | ~2秒 | ~0.4秒 | 5x |

---

## 检查索引使用情况

```sql
-- 查看查询是否使用索引
EXPLAIN SELECT * FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31'
  AND ActionGeo_Lat BETWEEN 30 AND 50;

-- 查看索引统计
SHOW INDEX FROM events_table;

-- 查看表大小
SELECT 
    table_name,
    round(((data_length + index_length) / 1024 / 1024 / 1024), 2) AS size_gb
FROM information_schema.TABLES
WHERE table_schema = 'gdelt' 
  AND table_name = 'events_table';
```

---

## 数据导入去重机制

```python
# 使用 _import_log 表记录已导入的文件
CREATE TABLE _import_log (
    file_signature VARCHAR(32) PRIMARY KEY,  -- 文件 MD5 签名
    file_name VARCHAR(255),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_count INT
);

# 检查文件是否已导入
SELECT 1 FROM _import_log WHERE file_signature = 'xxx';

# 主键保护（防止数据重复）
GlobalEventID BIGINT PRIMARY KEY
LOAD DATA ... IGNORE INTO TABLE  -- 重复主键自动跳过
```

---

## 维护命令

```bash
# 查看表大小
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SELECT 
    table_name,
    round(((data_length + index_length) / 1024 / 1024 / 1024), 2) AS size_gb,
    table_rows
FROM information_schema.TABLES
WHERE table_schema = 'gdelt';
"

# 查看索引使用情况
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SHOW INDEX FROM events_table;
"

# 优化表（定期执行）
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
OPTIMIZE TABLE events_table;
"

# 查看查询缓存命中
docker exec gdelt_app python -c "
import sys
sys.path.insert(0, 'mcp_server')
from app.cache import query_cache
print(query_cache.get_stats())
"
```

---

*记录时间: 2024-04-02*
*数据量: 15,731,577 条*
