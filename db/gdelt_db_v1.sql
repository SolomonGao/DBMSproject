-- 创建数据库
CREATE DATABASE IF NOT EXISTS gdelt_db;
USE gdelt_db;

-- 创建事件表
CREATE TABLE events_table (
    GlobalEventID BIGINT PRIMARY KEY,
    SQLDATE DATE NOT NULL,
    MonthYear INT,
    DATEADDED DATETIME,
    Actor1Name VARCHAR(255),
    Actor1CountryCode CHAR(3),
    Actor1Type1Code VARCHAR(10),
    Actor2Name VARCHAR(255),
    Actor2CountryCode CHAR(3),
    Actor2Type1Code VARCHAR(10),
    EventCode VARCHAR(10),
    EventRootCode VARCHAR(10),
    QuadClass INT,
    GoldsteinScale FLOAT,
    AvgTone FLOAT,
    NumArticles INT,
    NumMentions INT,
    NumSources INT,
    ActionGeo_Type INT,
    ActionGeo_FullName TEXT,
    ActionGeo_CountryCode CHAR(2),
    ActionGeo_Lat DECIMAL(10, 7),
    ActionGeo_Long DECIMAL(10, 7),
    SOURCEURL TEXT,


    ActionGeo_Point POINT NOT NULL SRID 4326 
) ENGINE=InnoDB;


-- Insert data first after create and then run those below

-- ALTER TABLE events_table ADD INDEX idx_sqldate (SQLDATE);
-- ALTER TABLE events_table ADD SPATIAL INDEX idx_geo_point (ActionGeo_Point);
-- ALTER TABLE events_table ADD INDEX idx_actor1 (Actor1Name(20));
-- ALTER TABLE events_table ADD INDEX idx_actor2 (Actor2Name(20));