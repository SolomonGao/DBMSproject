-- Optimized indexes for Dashboard Filter search
-- Run this against MySQL to speed up actor/location queries

-- Country code exact match (fast equality lookup)
CREATE INDEX IF NOT EXISTS idx_country_code ON events_table(ActionGeo_CountryCode);

-- Location name prefix match (helps with LIKE 'prefix%')
CREATE INDEX IF NOT EXISTS idx_location_prefix ON events_table(ActionGeo_FullName(50));

-- Event root code for protest/conflict filtering
CREATE INDEX IF NOT EXISTS idx_event_root ON events_table(EventRootCode);

-- Composite index for date + country (common filter combo)
CREATE INDEX IF NOT EXISTS idx_date_country ON events_table(SQLDATE, ActionGeo_CountryCode);
