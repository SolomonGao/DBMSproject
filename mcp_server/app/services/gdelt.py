"""
GDELT 数据库服务

专门针对 GDELT 事件数据库的查询、分析和可视化服务。
支持：
- 智能 SQL 查询（带安全检查）
- 按时间范围查询
- 按参与方查询
- 按地理位置查询
- 事件统计分析
- 数据可视化
"""

import re
import json
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter

from app.database import get_db_pool


# SQL 安全：只允许 SELECT
_FORBIDDEN_KEYWORDS = [
    'DROP', 'DELETE', 'UPDATE', 'INSERT',
    'ALTER', 'TRUNCATE', 'GRANT', 'REVOKE',
    'CREATE', 'REPLACE', 'LOAD', 'CALL'
]


class GDELTService:
    """
    GDELT 数据库专用服务
    
    提供针对 GDELT events_table 表的完整查询和分析能力。
    """
    
    DEFAULT_TABLE = "events_table"
    MAX_ROWS = 100
    MAX_CELL_WIDTH = 100
    
    def __init__(self):
        self._table_cache = {}
    
    # ==================== SQL 安全工具 ====================
    
    @staticmethod
    def sanitize_query(query: str) -> Tuple[bool, str]:
        """安全检查 SQL 查询"""
        sql_upper = query.upper().strip()
        
        if not sql_upper.startswith("SELECT"):
            return False, "安全攔截：僅允許 SELECT 查詢語句"
        
        for keyword in _FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                return False, f"安全攔截：禁止使用的關鍵字 '{keyword}'"
        
        return True, ""
    
    def add_limit(self, query: str, max_rows: int = None) -> str:
        """智能添加 LIMIT"""
        limit = max_rows or self.MAX_ROWS
        if "LIMIT" in query.upper():
            return query
        query = query.rstrip(";").strip()
        return f"{query} LIMIT {limit};"
    
    # ==================== 格式化工具 ====================
    
    def format_markdown(self, columns: List[str], rows: List[tuple]) -> str:
        """格式化为 Markdown 表格"""
        if not rows:
            return "查詢成功，但未找到符合條件的資料紀錄。"
        
        def truncate(text: str) -> str:
            text = str(text) if text is not None else "NULL"
            return text[:self.MAX_CELL_WIDTH-3] + "..." if len(text) > self.MAX_CELL_WIDTH else text
        
        header = "| " + " | ".join(columns) + " |"
        separator = "|" + "|".join([" --- " for _ in columns]) + "|"
        data_rows = ["| " + " | ".join([truncate(cell) for cell in row]) + " |" for row in rows]
        
        return "\n".join([header, separator] + data_rows) + f"\n\n*共返回 {len(rows)} 行数据*"
    
    def format_error(self, error: str, query: str) -> str:
        """格式化错误信息"""
        return f"""SQL 執行錯誤: {error}

請檢查:
1. SQL 語法是否符合 MySQL 8.0 規範
2. 表名和欄位名是否正確（可使用 `get_schema` 工具確認）
3. 條件語句是否正確

原始查詢:
```sql
{query}
```"""
    
    # ==================== 核心查询接口 ====================
    
    async def execute_sql(self, query: str) -> str:
        """
        执行安全的 SQL 查询
        
        自动检查安全性、添加 LIMIT、格式化结果。
        """
        passed, error_msg = self.sanitize_query(query)
        if not passed:
            return error_msg
        
        query = self.add_limit(query)
        
        try:
            pool = await get_db_pool()
            rows = await pool.fetchall(query)
            
            if not rows:
                return "查詢成功，但未找到符合條件的資料紀錄。"
            
            columns = list(rows[0].keys())
            row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
            
            return self.format_markdown(columns, row_tuples)
            
        except Exception as e:
            return self.format_error(str(e), query)
    
    async def get_schema(self, table_name: str = "events_table") -> str:
        """获取表结构"""
        try:
            pool = await get_db_pool()
            schema_data = await pool.get_schema(table_name)
            
            if not schema_data:
                return f"表 '{table_name}' 不存在或沒有欄位資訊"
            
            columns = ["Field", "Type", "Null", "Key", "Default", "Extra"]
            rows = [
                (
                    row.get("Field", ""),
                    row.get("Type", ""),
                    row.get("Null", ""),
                    row.get("Key", ""),
                    str(row.get("Default", "")) if row.get("Default") is not None else "NULL",
                    row.get("Extra", "")
                )
                for row in schema_data
            ]
            
            return self.format_markdown(columns, rows)
            
        except ValueError as e:
            return f"錯誤：{str(e)}"
        except Exception as e:
            return f"獲取表結構失敗: {str(e)}"
    
    # ==================== 便捷查询接口 ====================
    
    async def query_by_time_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100
    ) -> str:
        """按时间范围查询事件"""
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode, 
               GoldsteinScale, AvgTone, NumArticles, SOURCEURL
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY SQLDATE DESC
        """
        return await self.execute_sql(query)
    
    async def query_by_actor(
        self,
        actor_name: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 50
    ) -> str:
        """按参与方查询事件"""
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND SQLDATE BETWEEN '{start_date}' AND '{end_date}'"
        
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor1CountryCode, 
               Actor2Name, Actor2CountryCode, EventCode,
               GoldsteinScale, AvgTone, SOURCEURL
        FROM {self.DEFAULT_TABLE}
        WHERE (Actor1Name LIKE '%{actor_name}%' OR Actor2Name LIKE '%{actor_name}%')
        {date_filter}
        ORDER BY SQLDATE DESC
        LIMIT {limit}
        """
        return await self.execute_sql(query)
    
    async def query_by_location(
        self,
        lat: float,
        lon: float,
        radius_km: float = 100,
        limit: int = 50
    ) -> str:
        """按地理位置查询事件（使用 Haversine 公式）"""
        # 使用 ST_Distance_Sphere 计算球面距离（MySQL 8.0+）
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
               ActionGeo_Lat, ActionGeo_Long,
               GoldsteinScale, AvgTone, SOURCEURL,
               ST_Distance_Sphere(
                   ActionGeo_Point, 
                   POINT({lon}, {lat})
               ) / 1000 AS distance_km
        FROM {self.DEFAULT_TABLE}
        WHERE ActionGeo_Lat IS NOT NULL 
          AND ActionGeo_Long IS NOT NULL
          AND ST_Distance_Sphere(
              ActionGeo_Point, 
              POINT({lon}, {lat})
          ) <= {radius_km * 1000}
        ORDER BY distance_km
        LIMIT {limit}
        """
        return await self.execute_sql(query)
    
    # ==================== 统计分析接口 ====================
    
    async def analyze_events_by_date(
        self,
        start_date: str,
        end_date: str
    ) -> str:
        """按日期统计事件数量"""
        query = f"""
        SELECT SQLDATE, 
               COUNT(*) as event_count,
               AVG(GoldsteinScale) as avg_goldstein,
               AVG(AvgTone) as avg_tone
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY SQLDATE
        ORDER BY SQLDATE
        """
        return await self.execute_sql(query)
    
    async def analyze_top_actors(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 10
    ) -> str:
        """统计最活跃的参与方"""
        query = f"""
        SELECT Actor1Name as actor, COUNT(*) as event_count
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}'
          AND Actor1Name IS NOT NULL
          AND Actor1Name != ''
        GROUP BY Actor1Name
        ORDER BY event_count DESC
        LIMIT {top_n}
        """
        return await self.execute_sql(query)
    
    async def analyze_conflict_cooperation_trend(
        self,
        start_date: str,
        end_date: str
    ) -> str:
        """分析冲突/合作趋势（基于 GoldsteinScale）"""
        query = f"""
        SELECT 
            SQLDATE,
            COUNT(*) as total_events,
            SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) as cooperation_events,
            AVG(GoldsteinScale) as avg_scale
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY SQLDATE
        ORDER BY SQLDATE
        """
        return await self.execute_sql(query)
    
    # ==================== 可视化接口 ====================
    
    async def generate_chart(
        self,
        query: str,
        chart_type: str = "line",
        title: str = "GDELT 数据分析"
    ) -> str:
        """
        生成数据可视化（返回 ECharts 配置 JSON）
        
        注意：此工具返回 ECharts 配置，需要前端支持渲染。
        如果是纯文本客户端，会返回表格格式。
        """
        # 执行查询获取数据
        result = await self.execute_sql(query)
        
        # 如果是错误信息，直接返回
        if result.startswith("SQL") or result.startswith("安全") or result.startswith("查詢成功"):
            return result
        
        # 解析 Markdown 表格数据（简化处理）
        # 实际实现应该返回 ECharts JSON 配置
        # 这里返回描述性文本说明如何可视化
        
        chart_desc = {
            "line": "折线图 - 适合展示时间趋势",
            "bar": "柱状图 - 适合比较不同类别的数值",
            "pie": "饼图 - 适合展示比例分布",
            "scatter": "散点图 - 适合展示相关性"
        }
        
        return f"""## 图表配置

**图表类型**: {chart_desc.get(chart_type, chart_type)}
**标题**: {title}

**数据预览**:
{result}

**ECharts 配置提示**:
```javascript
{{
    title: {{ text: '{title}' }},
    xAxis: {{ type: 'category' }},
    yAxis: {{ type: 'value' }},
    series: [{{ type: '{chart_type}', data: [...] }}]
}}
```

> 注意：完整图表需要前端 ECharts 支持渲染。
"""
    
    # ==================== Schema 提示生成 ====================
    
    async def get_schema_prompt(self) -> str:
        """生成 GDELT Schema 使用指南"""
        return """## GDELT 数据库使用指南

### 主要字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `GlobalEventID` | BIGINT | 事件唯一标识 |
| `SQLDATE` | DATE | 事件日期 (YYYY-MM-DD) |
| `MonthYear` | INT | 年月 (YYYYMM) |
| `Actor1Name` | VARCHAR | 主要参与方名称 |
| `Actor1CountryCode` | CHAR(3) | 参与方1国家代码 |
| `Actor2Name` | VARCHAR | 次要参与方名称 |
| `Actor2CountryCode` | CHAR(3) | 参与方2国家代码 |
| `EventCode` | VARCHAR | CAMEO 事件类型代码 |
| `EventRootCode` | VARCHAR | CAMEO 根事件代码 |
| `GoldsteinScale` | FLOAT | 冲突/合作强度 (-10 到 +10) |
| `AvgTone` | FLOAT | 新闻语调 (-100 到 +100) |
| `NumArticles` | INT | 报道文章数 |
| `NumMentions` | INT | 提及次数 |
| `ActionGeo_Lat` | DECIMAL | 事件发生地纬度 |
| `ActionGeo_Long` | DECIMAL | 事件发生地经度 |
| `ActionGeo_FullName` | TEXT | 地理位置全称 |
| `SOURCEURL` | TEXT | 新闻来源 URL |

### 常用查询示例

```sql
-- 1. 查询某天所有事件
SELECT * FROM events_table WHERE SQLDATE = '2024-01-01' LIMIT 50;

-- 2. 查询涉及中国的冲突事件
SELECT SQLDATE, Actor1Name, Actor2Name, GoldsteinScale, AvgTone
FROM events_table 
WHERE (Actor1Name LIKE '%China%' OR Actor2Name LIKE '%China%')
  AND GoldsteinScale < 0
ORDER BY SQLDATE DESC
LIMIT 100;

-- 3. 统计某月每日事件数量
SELECT SQLDATE, COUNT(*) as count 
FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31'
GROUP BY SQLDATE;

-- 4. 查询高冲突事件（GoldsteinScale < -5）
SELECT SQLDATE, Actor1Name, Actor2Name, GoldsteinScale, SOURCEURL
FROM events_table
WHERE GoldsteinScale < -5
ORDER BY GoldsteinScale
LIMIT 20;

-- 5. 按地理位置查询（需要空间索引支持）
SELECT SQLDATE, ActionGeo_FullName, Actor1Name, GoldsteinScale
FROM events_table
WHERE ActionGeo_Lat BETWEEN 39.0 AND 42.0
  AND ActionGeo_Long BETWEEN 115.0 AND 118.0
LIMIT 50;
```

### GoldsteinScale 参考

- **-10 到 -5**: 严重冲突（战争、暴力袭击）
- **-5 到 0**: 轻度冲突（抗议、谴责）
- **0 到 +5**: 轻度合作（会谈、贸易）
- **+5 到 +10**: 积极合作（援助、协议、友好访问）

### CAMEO Event Code 参考

- **01-09**: 公开声明 (Make public statement)
- **10-19**: 屈服 (Yield)
- **20-29**: 调查 (Investigate)
- **30-39**: 要求 (Demand)
- **40-49**: 不赞成 (Disapprove)
- **50-59**: 拒绝 (Reject)
- **60-69**: 威胁 (Threaten)
- **70-79**: 抗议 (Protest)
- **80-89**: 展示武力 (Exhibit force)
- **90-99**: 升级冲突 (Escalate conflict)
- **100-109**: 使用武力 (Use force)
- **110-129**: 诉诸暴力 (Engage in violence)
- **130-149**: 使用大规模暴力 (Use mass violence)
- **150-169**: 表达合作意愿 (Express intent to cooperate)
- **170-199**: 合作 (Cooperate)
- **200-229**: 提供援助 (Provide aid)
- **230-249**: 屈服 (Yield)
- **250-259**: 解决争端 (Settle dispute)
"""
