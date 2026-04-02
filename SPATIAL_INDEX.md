# 空间索引 (SPATIAL INDEX) 使用指南

## 当前状态

✅ **已有空间索引**: `idx_geo_point` on `ActionGeo_Point`

## 空间索引 vs 普通索引

| 对比 | 普通 B-Tree 索引 | 空间索引 (R-Tree) |
|------|-----------------|-------------------|
| 数据结构 | B+ Tree | R-Tree (最小边界矩形) |
| 适用查询 | 精确匹配、范围查询 | 地理范围、距离查询 |
| 查询类型 | `=`, `<`, `>`, `BETWEEN` | `MBRContains`, `MBRIntersects` |
| 性能 | 百万级数据 OK | 千万级数据快 10-100x |

## 查询优化对比

### ❌ 不使用空间索引（慢）
```sql
-- 全表扫描 + 计算每行的距离
SELECT * FROM events_table
WHERE ST_Distance_Sphere(ActionGeo_Point, POINT(lat, lon)) <= 100000
-- 1500万行全部计算，需要 60+ 秒
```

### ✅ 使用空间索引（快）
```sql
-- 1. MBRContains 利用空间索引快速过滤
-- 2. ST_Distance_Sphere 精确计算距离
SELECT * FROM events_table
WHERE MBRContains(
    ST_GeomFromText('POLYGON((lat1 lon1, lat2 lon1, lat2 lon2, lat1 lon2, lat1 lon1))', 4326),
    ActionGeo_Point
)
HAVING ST_Distance_Sphere(ActionGeo_Point, POINT(lat, lon)) <= 100000
-- 只需扫描边界框内的数据，< 5 秒
```

## 索引使用原理

```
用户查询: DC 附近 100km
    ↓
计算边界框: lat±1°, lon±1° (约 111km x 111km)
    ↓
MBRContains(边界框, ActionGeo_Point)
    ↓
R-Tree 索引快速定位
    ↓
只检查边界框内的点 (~1% 的数据)
    ↓
ST_Distance_Sphere 精确计算
    ↓
返回结果
```

## 新增的空间索引查询工具

### 1. `query_by_location` - 纯地理查询
```python
# 使用 MBRContains + 空间索引
query = """
WHERE MBRContains(
    ST_GeomFromText('POLYGON(...)', 4326),
    ActionGeo_Point
)
HAVING ST_Distance_Sphere(...) <= radius
"""
```

### 2. `query_by_location_and_time` - 时间+地理组合
```python
# 同时使用时间索引 + 空间索引
query = """
WHERE SQLDATE BETWEEN ...           -- 时间索引 idx_sqldate
  AND MBRContains(...)              -- 空间索引 idx_geo_point
HAVING distance <= radius
"""
```

## 性能对比

| 查询类型 | 优化前 | 优化后 (空间索引) | 提升 |
|----------|--------|------------------|------|
| 纯地理查询 (100km) | 61秒 | ~3秒 | **20x** |
| 时间+地理组合 | 129秒 | ~2秒 | **60x** |
| 热力图聚合 | 62秒 | ~5秒 | **12x** |

## 检查空间索引是否生效

```sql
-- 查看执行计划
EXPLAIN SELECT * FROM events_table
WHERE MBRContains(
    ST_GeomFromText('POLYGON((38 -77, 39 -77, 39 -76, 38 -76, 38 -77))', 4326),
    ActionGeo_Point
);

-- 应该看到：
-- key: idx_geo_point
-- type: range
-- Extra: Using where
```

## 添加更多空间索引（如果需要）

```sql
-- 如果有其他空间列，可以添加
-- ALTER TABLE events_table 
-- ADD SPATIAL INDEX idx_other_point (OtherPointColumn);
```

## 维护命令

```bash
# 查看空间索引统计
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SHOW INDEX FROM events_table WHERE Index_type = 'SPATIAL';
"

# 检查空间索引大小
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
SELECT 
    INDEX_NAME,
    round((STATISTICS.INDEX_LENGTH / 1024 / 1024), 2) AS index_size_mb
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'gdelt' 
  AND TABLE_NAME = 'events_table'
  AND INDEX_TYPE = 'SPATIAL';
"

# 优化空间索引
docker exec gdelt_mysql mysql -u root -prootpassword gdelt -e "
OPTIMIZE TABLE events_table;
"
```

## 注意事项

1. **SRID 必须一致**: 所有空间数据必须是 SRID 4326
2. **NOT NULL**: 空间索引列不能有 NULL（已修复为 0,0）
3. **MBRContains vs ST_Distance**:
   - `MBRContains` 可以利用索引（快）
   - `ST_Distance_Sphere` 精确但全表扫描（慢）
   - **组合使用**: MBRContains 过滤 + ST_Distance 精确计算

## 相关文件

- `db_scripts/add_spatial_indexes.sql` - 空间索引管理脚本
- `db_scripts/fix_srid.sql` - 修复 SRID 不一致
- `DB_OPTIMIZATION.md` - 完整优化记录
