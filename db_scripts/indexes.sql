-- ============================================================================
-- GDELT Database Indexes
-- ============================================================================
-- This file documents all indexes created for the events_table
-- 
-- Usage: docker exec -i gdelt_mysql mysql -u root -prootpassword gdelt < db_scripts/indexes.sql
-- 
-- Created: 2026-04-13
-- Table: events_table (15.89 million records)
-- ============================================================================

-- Primary Key (auto-created)
-- ALTER TABLE events_table ADD PRIMARY KEY (GlobalEventID);

-- 1. Date-based indexes for time range queries
CREATE INDEX idx_sqldate ON events_table(SQLDATE);
-- Usage: query_by_time_range, get_top_events, analyze_time_series

-- 2. Actor-based indexes for participant queries
CREATE INDEX idx_actor1 ON events_table(Actor1Name);
CREATE INDEX idx_actor2 ON events_table(Actor2Name);
-- Usage: query_by_actor, search_events with actor filter

-- 3. Geographic indexes for location-based queries
CREATE INDEX idx_lat ON events_table(ActionGeo_Lat);
CREATE INDEX idx_long ON events_table(ActionGeo_Long);

-- 3a. City/region name index (Added 2026-04-13)
-- This index significantly improves queries filtering by city or region names
-- Example: WHERE ActionGeo_FullName LIKE '%Washington%'
-- Status: ✅ CREATED (Cardinality: 358,335)
CREATE INDEX idx_geo_fullname ON events_table(ActionGeo_FullName(100));
-- Usage: query_by_location, get_geo_heatmap, get_top_events with region_filter

-- 4. Composite indexes for common query patterns
CREATE INDEX idx_date_actor ON events_table(SQLDATE, Actor1Name);
-- Usage: time range + actor combined queries

CREATE INDEX idx_date_geo ON events_table(SQLDATE, ActionGeo_Lat, ActionGeo_Long);
-- Usage: time range + location combined queries

CREATE INDEX idx_geo_date ON events_table(ActionGeo_Lat, ActionGeo_Long, SQLDATE);
-- Usage: location + time range combined queries (different order)

-- 5. Event severity index
CREATE INDEX idx_goldstein ON events_table(GoldsteinScale);
-- Usage: conflict/cooperation filtering, heat score calculation

-- 6. Spatial index for geometric queries
-- CREATE SPATIAL INDEX idx_geo_point ON events_table(ActionGeo_Point);
-- Note: Requires MySQL spatial extensions enabled
-- Usage: ST_Distance_Sphere queries, geographic heatmaps

-- ============================================================================
-- Index Usage Guide
-- ============================================================================
-- 
-- For time-based queries:
--   SELECT * FROM events_table WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31'
--   → Uses: idx_sqldate
--
-- For actor-based queries:
--   SELECT * FROM events_table WHERE Actor1Name LIKE '%USA%'
--   → Uses: idx_actor1
--
-- For location-based queries:
--   SELECT * FROM events_table WHERE ActionGeo_FullName LIKE '%Washington%'
--   → Uses: idx_geo_fullname
--
-- For combined queries:
--   SELECT * FROM events_table 
--   WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-12-31' 
--   AND Actor1Name = 'USA'
--   → Uses: idx_date_actor (composite index)

-- ============================================================================
-- Verify indexes
-- ============================================================================
-- SHOW INDEX FROM events_table;
