"""
optimized version GDELT MCP Tools

integratecache、streaming、androwetc.optimization technology。
include所has原始tool + optimized version新tool。
"""

import json
from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field

from app.services.gdelt_optimized import GDELTServiceOptimized, get_optimized_service
from app.cache import query_cache


# ==================== Schema Guide 文this（静态内容）====================

def _get_schema_guide_text() -> str:
    """GDELT databaseuse指南"""
    return """## GDELT databaseuse指南

### 主wantfield说明

| field名 | type | 说明 |
|--------|------|------|
| `GlobalEventID` | BIGINT | eventunique identifier |
| `SQLDATE` | DATE | eventdate (YYYY-MM-DD) |
| `MonthYear` | INT | 年月 (YYYYMM) |
| `Actor1Name` | VARCHAR | 主want参and方名称 |
| `Actor1CountryCode` | CHAR(3) | 参and方1国家code |
| `Actor2Name` | VARCHAR | 次want参and方名称 |
| `Actor2CountryCode` | CHAR(3) | 参and方2国家code |
| `EventCode` | VARCHAR | CAMEO eventtypecode |
| `EventRootCode` | VARCHAR | CAMEO 根eventcode |
| `GoldsteinScale` | FLOAT | conflict/合作强度 (-10 to +10) |
| `AvgTone` | FLOAT | news语调 (-100 to +100) |
| `NumArticles` | INT | report文章number |
| `NumMentions` | INT | 提and次number |
| `ActionGeo_Lat` | DECIMAL | eventoccur地纬度 |
| `ActionGeo_Long` | DECIMAL | eventoccur地经度 |
| `ActionGeo_FullName` | TEXT | geographic locationfull name |
| `SOURCEURL` | TEXT | news来源 URL |

### 常用queryExample

```sql
-- 1. query某天所hasevent
SELECT * FROM events_table WHERE SQLDATE = '2024-01-01' LIMIT 50;

-- 2. query涉and中国conflictevent
SELECT SQLDATE, Actor1Name, Actor2Name, GoldsteinScale, AvgTone
FROM events_table 
WHERE (Actor1Name LIKE '%China%' OR Actor2Name LIKE '%China%')
  AND GoldsteinScale < 0
ORDER BY SQLDATE DESC
LIMIT 100;

-- 3. statistics某月每日eventquantity
SELECT SQLDATE, COUNT(*) as count 
FROM events_table 
WHERE SQLDATE BETWEEN '2024-01-01' AND '2024-01-31'
GROUP BY SQLDATE;

-- 4. query高conflictevent（GoldsteinScale < -5）
SELECT SQLDATE, Actor1Name, Actor2Name, GoldsteinScale, SOURCEURL
FROM events_table
WHERE GoldsteinScale < -5
ORDER BY GoldsteinScale
LIMIT 20;
```

### GoldsteinScale 参考

- **-10 to -5**: criticalconflict（战争、暴力袭击）
- **-5 to 0**: 轻度conflict（抗议、谴责）
- **0 to +5**: 轻度合作（will谈、贸易）
- **+5 to +10**: 积极合作（援助、协议、友好访问）

### CAMEO Event Code 参考

- **01-09**: 公开声明 (Make public statement)
- **10-19**: 屈服 (Yield)
- **20-29**: 调查 (Investigate)
- **30-39**: want求 (Demand)
- **40-49**: 不赞成 (Disapprove)
- **50-59**: rejected (Reject)
- **60-69**: 威胁 (Threaten)
- **70-79**: 抗议 (Protest)
- **80-89**: 展示武力 (Exhibit force)
- **90-99**: upgradeconflict (Escalate conflict)
- **100-109**: use武力 (Use force)
- **110-129**: 诉诸暴力 (Engage in violence)
- **130-149**: use大规模暴力 (Use mass violence)
- **150-169**: 表达合作意愿 (Express intent to cooperate)
- **170-199**: 合作 (Cooperate)
- **200-229**: Provides援助 (Provide aid)
- **230-249**: 屈服 (Yield)
- **250-259**: resolve争端 (Settle dispute)

---
*此文档for静态内容，由optimized versiontoolProvides*
"""


# ==================== 文thiscleanuptool ====================

def sanitize_text(text: Any) -> str:
    """cleanup文this中非法 UTF-8 字符"""
    if text is None:
        return "N/A"
    text = str(text)
    # 移除 surrogate pairs
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # replace控制字符
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    # 移除 null bytes
    text = text.replace('\x00', '')
    return text


# ==================== inputmodel ====================

class SQLQueryInput(BaseModel):
    """SQL queryinput"""
    query: str = Field(..., description="SQL SELECT querystatement")


class TableSchemaInput(BaseModel):
    """表结构queryinput"""
    table_name: str = Field(default="events_table", description="wantquery表名")


class TimeRangeQueryInput(BaseModel):
    """when间rangequeryinput"""
    start_date: str = Field(..., description="开始date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    limit: int = Field(default=100, ge=1, le=1000, description="Returns结果quantity限制")


class ActorQueryInput(BaseModel):
    """参and方queryinput"""
    actor_name: str = Field(..., description="参and方名称关key词，如 'Virginia', 'China'")
    start_date: Optional[str] = Field(default=None, description="开始date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="结束date (YYYY-MM-DD)")
    limit: int = Field(default=50, ge=1, le=500, description="Returns结果quantity限制")


class GeoQueryInput(BaseModel):
    """地理rangequeryinput"""
    lat: float = Field(..., description="中心纬度", ge=-90, le=90)
    lon: float = Field(..., description="中心经度", ge=-180, le=180)
    radius_km: float = Field(default=100, description="search半径（公里）", ge=1, le=1000)
    limit: int = Field(default=50, ge=1, le=500, description="Returns结果quantity限制")


class EventAnalysisInput(BaseModel):
    """event分析input"""
    start_date: str = Field(..., description="开始date (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束date (YYYY-MM-DD)")


class VisualizationInput(BaseModel):
    """data可视化input"""
    query: str = Field(..., description="generategraph表 SQL query")
    chart_type: str = Field(default="line", description="graph表type: line/bar/pie/scatter")
    title: str = Field(default="GDELT data分析", description="graph表标题")


class DashboardInput(BaseModel):
    """仪表盘dataquery"""
    start_date: str = Field(..., description="开始date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束date (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")


class TimeSeriesInput(BaseModel):
    """when间序column分析"""
    start_date: str = Field(..., description="开始date (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束date (YYYY-MM-DD)")
    granularity: str = Field(default="day", description="granularity度: day/week/month")


class GeoHeatmapInput(BaseModel):
    """地理heatgraph"""
    start_date: str = Field(..., description="开始date (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束date (YYYY-MM-DD)")
    precision: int = Field(default=2, description="坐标精度 (1-3)", ge=1, le=3)


class StreamQueryInput(BaseModel):
    """streamingquery"""
    actor_name: str = Field(..., description="参and方名称（模糊match）")
    start_date: Optional[str] = Field(None, description="开始date")
    end_date: Optional[str] = Field(None, description="结束date")
    max_results: int = Field(default=100, description="最大Returnsquantity", le=1000)

# ▼▼▼ inAdd the following section here ▼▼▼
class NewsSearchInput(BaseModel):
    """新聞語義search輸入"""
    query: str = Field(
        ..., 
        description="English語義search查詢詞，例如 'protesters demanding climate action', 'police response'"
    )
    n_results: int = Field(
        default=3,
        description="ReturnsRelated news quantity limit",
        ge=1,
        le=10
    )

# ==================== toolRegister ====================

def create_optimized_tools(mcp):
    """创建所hasoptimized version GDELT tool（全部Supportscache）"""
    
    # 只useoptimized version服务（全部method都带cache）
    service = GDELTServiceOptimized()
    
    # ==================== 基础tool（全部带cache）====================
    
    @mcp.tool()
    async def get_schema(params: TableSchemaInput) -> str:
        """Getdatabase表结构"""
        # Schema 不经常变化，cache 1 小when
        query = f"DESCRIBE `{params.table_name}`"
        rows = await service.execute_sql_cached(query, cache_ttl=3600)
        
        if not rows:
            return f"表 '{params.table_name}' does not existor没hasfieldinfo"
        
        columns = ["Field", "Type", "Null", "Key", "Default", "Extra"]
        row_tuples = [
            (
                row.get("Field", ""),
                row.get("Type", ""),
                row.get("Null", ""),
                row.get("Key", ""),
                str(row.get("Default", "")) if row.get("Default") is not None else "NULL",
                row.get("Extra", "")
            )
            for row in rows
        ]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def get_schema_guide() -> str:
        """Get GDELT databaseuse指南"""
        # 静态内容，directReturns
        return _get_schema_guide_text()
    
    
    @mcp.tool()
    async def execute_sql(params: SQLQueryInput) -> str:
        """
        执row自Defines SQL query（带cache）
        
        query结果will自动cache 5 分钟，samequerywilldirectReturnscache结果。
        """
        rows = await service.execute_sql_cached(params.query, cache_ttl=300)
        
        if not rows:
            return "querysuccess，butnot foundmeetconditionmaterialrecord。"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def query_by_time_range(params: TimeRangeQueryInput) -> str:
        """按when间rangequeryevent（带cache）"""
        return await service.query_by_time_range_cached(
            params.start_date, params.end_date, params.limit, cache_ttl=300
        )
    
    
    @mcp.tool()
    async def query_by_actor(params: ActorQueryInput) -> str:
        """
        按参and方queryevent（带cache）
        
        usecache加速duplicatequery。same演员、samedaterangewillhitcache。
        """
        return await service.query_by_actor_cached(
            params.actor_name, params.start_date, params.end_date, params.limit, cache_ttl=300
        )
    
    
    @mcp.tool()
    async def query_by_location(params: GeoQueryInput) -> str:
        """按geographic locationqueryevent（带cache）"""
        # 地理query也Supportscache（位置data不常变化）
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
               ActionGeo_Lat, ActionGeo_Long,
               GoldsteinScale, AvgTone, SOURCEURL,
               ST_Distance_Sphere(
                   ActionGeo_Point, 
                   POINT(%s, %s)
               ) / 1000 AS distance_km
        FROM {service.DEFAULT_TABLE}
        WHERE ActionGeo_Lat IS NOT NULL 
          AND ActionGeo_Long IS NOT NULL
          AND ST_Distance_Sphere(
              ActionGeo_Point, 
              POINT(%s, %s)
          ) <= %s
        ORDER BY distance_km
        LIMIT %s
        """
        params = (params.lon, params.lat, params.lon, params.lat, 
                  params.radius_km * 1000, params.limit)
        
        rows = await service.execute_sql_cached(query, params, cache_ttl=600)
        
        if not rows:
            return f"not found距离 ({params.lat}, {params.lon}) {params.radius_km}km 内event"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def analyze_conflict_cooperation(params: EventAnalysisInput) -> str:
        """分析conflict/合作trends（带cache）"""
        query = f"""
        SELECT 
            SQLDATE,
            COUNT(*) as total_events,
            SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) as cooperation_events,
            AVG(GoldsteinScale) as avg_scale
        FROM {service.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
        GROUP BY SQLDATE
        ORDER BY SQLDATE
        """
        
        rows = await service.execute_sql_cached(query, (params.start_date, params.end_date), cache_ttl=600)
        
        if not rows:
            return "not founddata"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def generate_chart(params: VisualizationInput) -> str:
        """generatedata可视化"""
        # 先执rowquery（带cache）
        rows = await service.execute_sql_cached(params.query, cache_ttl=300)
        
        if not rows:
            return "querysuccess，butnot founddata"
        
        chart_desc = {
            "line": "折线graph - Suitable for showing time trends",
            "bar": "柱状graph - suitablecomparedifferentclass别numbervalue",
            "pie": "饼graph - Suitable for showing ratio distribution",
            "scatter": "散点graph - Suitable for showing correlations"
        }
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows[:20]]
        table = service._format_markdown(columns, row_tuples)
        
        return f"""## graph表config

**graph表type**: {chart_desc.get(params.chart_type, params.chart_type)}
**标题**: {params.title}

**datapre览**:
{table}

*共 {len(rows)} rowdata，显示before 20 row*

**ECharts configHint**:
```javascript
{{
    title: {{ text: '{params.title}' }},
    xAxis: {{ type: 'category' }},
    yAxis: {{ type: 'value' }},
    series: [{{ type: '{params.chart_type}', data: [...] }}]
}}
```
"""
    
    
    # ==================== optimized version新tool ====================
    
    @mcp.tool()
    async def get_dashboard(params: DashboardInput) -> str:
        """
        【优化】仪表盘data - and发Getmultidimensionstatistics
        
        同whenReturns：每日trends、Top 参and方、地理distribution、eventtypedistribution、综合statistics
        比串rowquery快 3-5 倍。
        """
        try:
            dashboard = await service.get_dashboard_data(
                params.start_date, params.end_date
            )
            
            lines = ["# 📊 仪表盘data\n"]
            
            summary = dashboard.get("summary_stats", {})
            if "data" in summary and summary["data"]:
                s = summary["data"][0]
                lines.append(f"**statisticsweek期**: {params.start_date} 至 {params.end_date}")
                lines.append(f"- 总eventnumber: {s.get('total_events', 0):,}")
                lines.append(f"- 独特参and方: {s.get('unique_actors', 0):,}")
                lines.append(f"- average Goldstein: {s.get('avg_goldstein', 0):.2f}")
                lines.append("")
            
            daily = dashboard.get("daily_trend", {})
            if "data" in daily:
                lines.append("## 📈 每日trends（before 7 天）")
                for row in daily["data"][:7]:
                    lines.append(f"- {row.get('SQLDATE')}: {row.get('cnt')} event")
                lines.append("")
            
            actors = dashboard.get("top_actors", {})
            if "data" in actors:
                lines.append("## 🎭 Top 5 参and方")
                for i, row in enumerate(actors["data"][:5], 1):
                    lines.append(f"{i}. {row.get('Actor1Name')}: {row.get('cnt')} event")
                lines.append("")
            
            total_time = sum(v.get("elapsed_ms", 0) for v in dashboard.values() if isinstance(v, dict))
            lines.append(f"\n*query耗when: {total_time:.0f}ms (androw优化)*")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ queryfailed: {str(e)}"
    
    
    @mcp.tool()
    async def analyze_time_series(params: TimeSeriesInput) -> str:
        """【优化】advancedwhen间序column分析 - database端aggregate"""
        try:
            results = await service.analyze_time_series_advanced(
                params.start_date, params.end_date, params.granularity
            )
            
            if not results:
                return "not founddata"
            
            lines = [f"# 📈 when间序column分析 ({params.granularity})\n"]
            
            for row in results:
                period = row.get("period")
                lines.append(f"### {period}")
                lines.append(f"- eventnumber: {row.get('event_count', 0):,}")
                lines.append(f"- conflict比例: {row.get('conflict_pct', 0)}%")
                lines.append(f"- 合作比例: {row.get('cooperation_pct', 0)}%")
                lines.append(f"- average Goldstein: {row.get('avg_goldstein', 0)}")
                lines.append("")
            
            lines.append(f"*共 {len(results)} 个when间week期*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 分析failed: {str(e)}"
    
    
    @mcp.tool()
    async def get_geo_heatmap(params: GeoHeatmapInput) -> str:
        """【优化】地理heatgraphdata - gridaggregate"""
        try:
            results = await service.get_geo_heatmap(
                params.start_date, params.end_date, params.precision
            )
            
            if not results:
                return "not found地理data"
            
            heatmap_data = [
                {
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "intensity": int(row["intensity"]),
                    "avg_conflict": float(row["avg_conflict"]) if row["avg_conflict"] else None,
                    "location": row["sample_location"]
                }
                for row in results[:100]
            ]
            
            return f"""# 🗺️ 地理heatgraphdata

**when间range**: {params.start_date} 至 {params.end_date}
**精度**: {params.precision} 位小number
**hotquantity**: {len(heatmap_data)}

```json
{json.dumps(heatmap_data[:10], indent=2, ensure_ascii=False)}
```

*完integer据共 {len(heatmap_data)} 条*
"""
        except Exception as e:
            return f"❌ queryfailed: {str(e)}"
    
    
    @mcp.tool()
    async def stream_query_events(params: StreamQueryInput) -> str:
        """【优化】streamingquery - process large amountsdata"""
        try:
            lines = [f"# 🔍 streamingquery结果: {params.actor_name}\n"]
            lines.append("| date | Actor1 | Actor2 | Goldstein | Tone | 位置 |")
            lines.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in service.stream_events_by_actor(
                params.actor_name, params.start_date, params.end_date
            ):
                lines.append(
                    f"| {sanitize_text(row.get('SQLDATE'))} | "
                    f"{sanitize_text(row.get('Actor1Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('Actor2Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('GoldsteinScale', 'N/A'))} | "
                    f"{sanitize_text(row.get('AvgTone', 'N/A'))} | "
                    f"{sanitize_text(row.get('ActionGeo_FullName', 'N/A'))[:20]} |"
                )
                
                count += 1
                if count >= params.max_results:
                    lines.append("| ... | (更multi结果截断) | ... | ... | ... | ... |")
                    break
            
            lines.append(f"\n*共Returns {count} results (streaming读取)*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ streamingqueryfailed: {str(e)}"
    
    
    @mcp.tool()
    async def get_cache_stats() -> str:
        """【诊断】查看querycachestatisticsinfo"""
        stats = query_cache.get_stats()
        
        hit_rate_str = stats['hit_rate'].rstrip('%')
        try:
            hit_rate = float(hit_rate_str)
            if hit_rate >= 80:
                evaluation = "✅ hit率优秀 (≥80%)"
            elif hit_rate >= 50:
                evaluation = "⚠️ hit率一般 (50-80%)"
            else:
                evaluation = "❌ hit率较低 (<50%)"
        except:
            evaluation = "🤷 暂无足够data"
        
        return f"""# 📊 querycachestatistics

| 指标 | value |
|------|-----|
| cache条目number | {stats['size']} / {stats['maxsize']} |
| hit次number | {stats['hits']:,} |
| 未hit次number | {stats['misses']:,} |
| hit率 | {stats['hit_rate']} |
| LRU eviction次number | {stats['evictions']:,} |

**评估**: {evaluation}
"""
    
    
    @mcp.tool()
    async def clear_cache() -> str:
        """清除所hasquerycache"""
        count = await query_cache.clear()
        return f"✅ already清除 {count} 个cache条目"
    
    @mcp.tool()
    async def search_news_context(params: NewsSearchInput) -> str:
        """
        【RAG 右腦】新聞語義搜index擎
        
        當你need解event具體起因、crowd具體訴求、警方回應orCall this when detailed news background is neededtool。
        請輸入EnglishNatural language query localvectorReal news text snippets in knowledge base。
        """
        # 呼叫我們in GDELTServiceOptimized 中新增檢索method
        return await service.search_news_context(params.query, params.n_results)   
