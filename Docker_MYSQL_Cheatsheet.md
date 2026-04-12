# Docker MySQL SQL 操作指南

## 快速开始

### 1. 直接进入 MySQL 命令行

```bash
docker exec -it gdelt_mysql mysql -uroot -prootpassword gdelt
```

参数说明：
- `-it` : 交互式终端
- `gdelt_mysql` : 容器名
- `-u` : 用户名
- `-p` : 密码（注意：-p 和密码之间没有空格）
- `gdelt` : 数据库名

---

## 常用操作

### 连接数据库

```bash
# 连接指定数据库
docker exec -it gdelt_mysql mysql -uroot -prootpassword gdelt

# 不指定数据库（进入后选）
docker exec -it gdelt_mysql mysql -uroot -prootpassword
```

### 执行单条 SQL（不进入交互式）

```bash
# 查看所有表
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SHOW TABLES;"

# 查看记录数
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SELECT COUNT(*) FROM events_table;"

# 查询前5条
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SELECT * FROM events_table LIMIT 5;"
```

### 执行 SQL 文件

```bash
# 方法1：从本地文件执行
docker exec -i gdelt_mysql mysql -uroot -prootpassword gdelt < your_script.sql

# 方法2：先复制文件到容器，再执行
docker cp your_script.sql gdelt_mysql:/tmp/
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "source /tmp/your_script.sql"
```

---

## 交互式 SQL 示例

进入 MySQL 后可以使用所有标准 SQL：

```sql
-- 查看数据库
SHOW DATABASES;

-- 使用数据库
USE gdelt;

-- 查看所有表
SHOW TABLES;

-- 查看表结构
DESCRIBE events_table;
-- 或
SHOW COLUMNS FROM events_table;

-- 查看表详情
SHOW CREATE TABLE events_table;

-- 查询数据
SELECT * FROM events_table LIMIT 10;

-- 条件查询
SELECT SQLDATE, Actor1Name, EventCode 
FROM events_table 
WHERE ActionGeo_CountryCode = 'US' 
LIMIT 10;

-- 统计
SELECT 
    SQLDATE,
    COUNT(*) as event_count,
    AVG(GoldsteinScale) as avg_goldstein
FROM events_table 
GROUP BY SQLDATE 
ORDER BY SQLDATE 
LIMIT 10;

-- 退出
EXIT;
-- 或
QUIT;
```

---

## 数据导出/导入

### 导出数据（从容器到本地）

```bash
# 导出整个数据库
docker exec gdelt_mysql mysqldump -uroot -prootpassword gdelt > backup.sql

# 导出指定表
docker exec gdelt_mysql mysqldump -uroot -prootpassword gdelt events_table > events_backup.sql

# 只导出结构（不含数据）
docker exec gdelt_mysql mysqldump -uroot -prootpassword --no-data gdelt > schema.sql
```

### 导入数据（从本地到容器）

```bash
# 导入 SQL 文件
docker exec -i gdelt_mysql mysql -uroot -prootpassword gdelt < backup.sql

# 或先复制再导入
docker cp backup.sql gdelt_mysql:/tmp/
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "source /tmp/backup.sql"
```

---

## 常用查询模板

### 时间范围查询
```sql
SELECT * FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31' 
LIMIT 100;
```

### 地理位置查询
```sql
-- 计算距离（Haversine公式示例）
SELECT 
    GlobalEventID,
    ActionGeo_FullName,
    ActionGeo_Lat,
    ActionGeo_Long,
    (6371 * acos(
        cos(radians(40.7128)) * cos(radians(ActionGeo_Lat)) *
        cos(radians(ActionGeo_Long) - radians(-74.0060)) +
        sin(radians(40.7128)) * sin(radians(ActionGeo_Lat))
    )) AS distance_km
FROM events_table
HAVING distance_km < 100
LIMIT 10;
```

### 统计分析
```sql
-- 按国家统计事件数
SELECT 
    ActionGeo_CountryCode,
    COUNT(*) as event_count
FROM events_table
WHERE ActionGeo_CountryCode IS NOT NULL
GROUP BY ActionGeo_CountryCode
ORDER BY event_count DESC
LIMIT 10;

-- 每日事件趋势
SELECT 
    SQLDATE,
    COUNT(*) as events,
    AVG(GoldsteinScale) as avg_goldstein,
    AVG(AvgTone) as avg_tone
FROM events_table
GROUP BY SQLDATE
ORDER BY SQLDATE;
```

---

## 实用技巧

### 1. 表格形式显示结果
```bash
# 使用 -t 参数
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -t -e "SELECT * FROM events_table LIMIT 5;"
```

### 2. 以 CSV 格式导出
```bash
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SELECT * FROM events_table LIMIT 100" | tr '\t' ',' > output.csv
```

### 3. 后台执行长时间查询
```bash
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "YOUR_LONG_QUERY" > result.txt 2>&1 &
```

### 4. 查看当前连接
```bash
docker exec gdelt_mysql mysql -uroot -prootpassword -e "SHOW PROCESSLIST;"
```

### 5. 查看表大小
```bash
docker exec gdelt_mysql mysql -uroot -prootpassword -e "
SELECT 
    table_name,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'gdelt';
"
```

---

## 故障排查

### 连接失败
```bash
# 检查容器是否运行
docker ps | grep gdelt_mysql

# 检查 MySQL 服务是否正常
docker logs gdelt_mysql

# 进入容器检查
docker exec -it gdelt_mysql bash
mysql -uroot -prootpassword
```

### 权限问题
```sql
-- 查看当前用户
SELECT USER();
SELECT CURRENT_USER();

-- 查看权限
SHOW GRANTS;
```

---

## 快捷命令汇总

```bash
# 你的项目常用命令
cd "/Volumes/Mac Driver/capstone/DBMSproject"

# 进入 MySQL
docker exec -it gdelt_mysql mysql -uroot -prootpassword gdelt

# 查看记录数
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SELECT COUNT(*) FROM events_table;"

# 查看表结构
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "DESCRIBE events_table;"

# 查询样本数据
docker exec gdelt_mysql mysql -uroot -prootpassword gdelt -e "SELECT SQLDATE, Actor1Name, ActionGeo_FullName FROM events_table LIMIT 5;"
```
