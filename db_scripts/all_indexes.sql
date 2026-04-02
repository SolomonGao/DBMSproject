-- ============================================
-- GDELT 数据库完整索引方案
-- 针对 1500万+ 数据量优化
-- ============================================

-- 基础索引（时间、参与方、地理、指标）
-- 这些索引对基本查询性能至关重要

-- 1. 日期索引（最重要！几乎所有查询都有时间范围）
ALTER TABLE events_table 
ADD INDEX idx_sqldate (SQLDATE);

-- 2. 参与方索引（模糊搜索和统计）
ALTER TABLE events_table 
ADD INDEX idx_actor1 (Actor1Name(20));

ALTER TABLE events_table 
ADD INDEX idx_actor2 (Actor2Name(20));

-- 3. 冲突强度索引（分类查询）
ALTER TABLE events_table 
ADD INDEX idx_goldstein (GoldsteinScale);

-- 4. 地理坐标索引（基础地理查询）
ALTER TABLE events_table 
ADD INDEX idx_lat (ActionGeo_Lat);

ALTER TABLE events_table 
ADD INDEX idx_long (ActionGeo_Long);

-- ============================================
-- 复合索引（大数据量优化）
-- ============================================

-- 5. 地理+日期复合索引（优化热力图、地理范围+时间查询）
-- 使用场景：查询某时间段+某地理范围的事件
ALTER TABLE events_table 
ADD INDEX idx_geo_date (ActionGeo_Lat, ActionGeo_Long, SQLDATE);

-- 6. 日期+地理复合索引（优化时间为主、地理为辅的查询）
-- 使用场景：先按时间筛选，再按地理筛选
ALTER TABLE events_table 
ADD INDEX idx_date_geo (SQLDATE, ActionGeo_Lat, ActionGeo_Long);

-- 7. 日期+参与方复合索引（优化时间+Actor组合查询）
-- 使用场景：查询某时间段内某参与方的事件
ALTER TABLE events_table 
ADD INDEX idx_date_actor (SQLDATE, Actor1Name(20));

-- ============================================
-- 可选：空间索引（如果需要精确地理计算）
-- ============================================
-- ALTER TABLE events_table 
-- ADD SPATIAL INDEX idx_geo_point (ActionGeo_Point);

-- ============================================
-- 验证索引创建
-- ============================================
SHOW INDEX FROM events_table;

-- 查看表大小（数据+索引）
SELECT 
    table_name,
    round((data_length / 1024 / 1024 / 1024), 2) AS data_size_gb,
    round((index_length / 1024 / 1024 / 1024), 2) AS index_size_gb,
    round(((data_length + index_length) / 1024 / 1024 / 1024), 2) AS total_size_gb,
    table_rows
FROM information_schema.TABLES
WHERE table_schema = 'gdelt' 
  AND table_name = 'events_table';

-- ============================================
-- 索引使用建议
-- ============================================
-- 
-- 1. 简单时间查询: 使用 idx_sqldate
--    WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31'
--
-- 2. 按演员查询: 使用 idx_actor1
--    WHERE Actor1Name LIKE '%Virginia%'
--
-- 3. 地理+时间查询: 使用 idx_geo_date 或 idx_date_geo
--    WHERE SQLDATE BETWEEN ... AND ActionGeo_Lat BETWEEN ...
--
-- 4. 热力图聚合: 使用 idx_geo_date
--    先按日期过滤，再按地理聚合
--
-- 5. Dashboard 并行查询: 多个索引同时使用
