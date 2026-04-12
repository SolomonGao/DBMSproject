"""
优化版 GDELT MCP Tools

整合缓存、流式、并行等优化技术。
包含所有原始工具 + 优化版新工具。
"""

import json
from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field

from app.services.gdelt_optimized import GDELTServiceOptimized, get_optimized_service
from app.cache import query_cache


# ==================== Schema Guide 文本（静态内容）====================

def _get_schema_guide_text() -> str:
    """GDELT 数据库使用指南"""
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

---
*此文档为静态内容，由优化版工具提供*
"""


# ==================== 文本清理工具 ====================

def sanitize_text(text: Any) -> str:
    """清理文本中的非法 UTF-8 字符"""
    if text is None:
        return "N/A"
    text = str(text)
    # 移除 surrogate pairs
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # 替换控制字符
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    # 移除 null bytes
    text = text.replace('\x00', '')
    return text


# ==================== 输入模型 ====================

class SQLQueryInput(BaseModel):
    """SQL 查询输入"""
    query: str = Field(..., description="SQL SELECT 查询语句")


class TableSchemaInput(BaseModel):
    """表结构查询输入"""
    table_name: str = Field(default="events_table", description="要查询的表名")


class TimeRangeQueryInput(BaseModel):
    """时间范围查询输入"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    limit: int = Field(default=100, ge=1, le=1000, description="返回结果数量限制")


class ActorQueryInput(BaseModel):
    """参与方查询输入"""
    actor_name: str = Field(..., description="参与方名称关键词，如 'Virginia', 'China'")
    start_date: Optional[str] = Field(default=None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")
    limit: int = Field(default=50, ge=1, le=500, description="返回结果数量限制")


class GeoQueryInput(BaseModel):
    """地理范围查询输入"""
    lat: float = Field(..., description="中心纬度", ge=-90, le=90)
    lon: float = Field(..., description="中心经度", ge=-180, le=180)
    radius_km: float = Field(default=100, description="搜索半径（公里）", ge=1, le=1000)
    limit: int = Field(default=50, ge=1, le=500, description="返回结果数量限制")


class EventAnalysisInput(BaseModel):
    """事件分析输入"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")


class VisualizationInput(BaseModel):
    """数据可视化输入"""
    query: str = Field(..., description="生成图表的 SQL 查询")
    chart_type: str = Field(default="line", description="图表类型: line/bar/pie/scatter")
    title: str = Field(default="GDELT 数据分析", description="图表标题")


class DashboardInput(BaseModel):
    """仪表盘数据查询"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")


class TimeSeriesInput(BaseModel):
    """时间序列分析"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    granularity: str = Field(default="day", description="粒度: day/week/month")


class GeoHeatmapInput(BaseModel):
    """地理热力图"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    precision: int = Field(default=2, description="坐标精度 (1-3)", ge=1, le=3)


class StreamQueryInput(BaseModel):
    """流式查询"""
    actor_name: str = Field(..., description="参与方名称（模糊匹配）")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    max_results: int = Field(default=100, description="最大返回数量", le=1000)

# ▼▼▼ 在這裡新增以下這段 ▼▼▼
class NewsSearchInput(BaseModel):
    """新聞語義搜索輸入"""
    query: str = Field(
        ..., 
        description="英文語義搜索查詢詞，例如 'protesters demanding climate action', 'police response'"
    )
    n_results: int = Field(
        default=3,
        description="返回的相關新聞數量限制",
        ge=1,
        le=10
    )

# ==================== 工具注册 ====================

def create_optimized_tools(mcp):
    """创建所有优化版 GDELT 工具（全部支持缓存）"""
    
    # 只使用优化版服务（全部方法都带缓存）
    service = GDELTServiceOptimized()
    
    # ==================== 基础工具（全部带缓存）====================
    
    @mcp.tool()
    async def get_schema(params: TableSchemaInput) -> str:
        """获取数据库表结构"""
        # Schema 不经常变化，缓存 1 小时
        query = f"DESCRIBE `{params.table_name}`"
        rows = await service.execute_sql_cached(query, cache_ttl=3600)
        
        if not rows:
            return f"表 '{params.table_name}' 不存在或没有字段信息"
        
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
        """获取 GDELT 数据库使用指南"""
        # 静态内容，直接返回
        return _get_schema_guide_text()
    
    
    @mcp.tool()
    async def execute_sql(params: SQLQueryInput) -> str:
        """
        执行自定义 SQL 查询（带缓存）
        
        查询结果会自动缓存 5 分钟，相同查询会直接返回缓存结果。
        """
        rows = await service.execute_sql_cached(params.query, cache_ttl=300)
        
        if not rows:
            return "查询成功，但未找到符合条件的资料记录。"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def query_by_time_range(params: TimeRangeQueryInput) -> str:
        """按时间范围查询事件（带缓存）"""
        return await service.query_by_time_range_cached(
            params.start_date, params.end_date, params.limit, cache_ttl=300
        )
    
    
    @mcp.tool()
    async def query_by_actor(params: ActorQueryInput) -> str:
        """
        按参与方查询事件（带缓存）
        
        使用缓存加速重复查询。相同演员、相同日期范围会命中缓存。
        """
        return await service.query_by_actor_cached(
            params.actor_name, params.start_date, params.end_date, params.limit, cache_ttl=300
        )
    
    
    @mcp.tool()
    async def query_by_location(params: GeoQueryInput) -> str:
        """按地理位置查询事件（带缓存）"""
        # 地理查询也支持缓存（位置数据不常变化）
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
            return f"未找到距离 ({params.lat}, {params.lon}) {params.radius_km}km 内的事件"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def analyze_conflict_cooperation(params: EventAnalysisInput) -> str:
        """分析冲突/合作趋势（带缓存）"""
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
            return "未找到数据"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def generate_chart(params: VisualizationInput) -> str:
        """生成数据可视化"""
        # 先执行查询（带缓存）
        rows = await service.execute_sql_cached(params.query, cache_ttl=300)
        
        if not rows:
            return "查询成功，但未找到数据"
        
        chart_desc = {
            "line": "折线图 - 适合展示时间趋势",
            "bar": "柱状图 - 适合比较不同类别的数值",
            "pie": "饼图 - 适合展示比例分布",
            "scatter": "散点图 - 适合展示相关性"
        }
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows[:20]]
        table = service._format_markdown(columns, row_tuples)
        
        return f"""## 图表配置

**图表类型**: {chart_desc.get(params.chart_type, params.chart_type)}
**标题**: {params.title}

**数据预览**:
{table}

*共 {len(rows)} 行数据，显示前 20 行*

**ECharts 配置提示**:
```javascript
{{
    title: {{ text: '{params.title}' }},
    xAxis: {{ type: 'category' }},
    yAxis: {{ type: 'value' }},
    series: [{{ type: '{params.chart_type}', data: [...] }}]
}}
```
"""
    
    
    # ==================== 优化版新工具 ====================
    
    @mcp.tool()
    async def get_dashboard(params: DashboardInput) -> str:
        """
        【优化】仪表盘数据 - 并发获取多维度统计
        
        同时返回：每日趋势、Top 参与方、地理分布、事件类型分布、综合统计
        比串行查询快 3-5 倍。
        """
        try:
            dashboard = await service.get_dashboard_data(
                params.start_date, params.end_date
            )
            
            lines = ["# 📊 仪表盘数据\n"]
            
            summary = dashboard.get("summary_stats", {})
            if "data" in summary and summary["data"]:
                s = summary["data"][0]
                lines.append(f"**统计周期**: {params.start_date} 至 {params.end_date}")
                lines.append(f"- 总事件数: {s.get('total_events', 0):,}")
                lines.append(f"- 独特参与方: {s.get('unique_actors', 0):,}")
                lines.append(f"- 平均 Goldstein: {s.get('avg_goldstein', 0):.2f}")
                lines.append("")
            
            daily = dashboard.get("daily_trend", {})
            if "data" in daily:
                lines.append("## 📈 每日趋势（前 7 天）")
                for row in daily["data"][:7]:
                    lines.append(f"- {row.get('SQLDATE')}: {row.get('cnt')} 事件")
                lines.append("")
            
            actors = dashboard.get("top_actors", {})
            if "data" in actors:
                lines.append("## 🎭 Top 5 参与方")
                for i, row in enumerate(actors["data"][:5], 1):
                    lines.append(f"{i}. {row.get('Actor1Name')}: {row.get('cnt')} 事件")
                lines.append("")
            
            total_time = sum(v.get("elapsed_ms", 0) for v in dashboard.values() if isinstance(v, dict))
            lines.append(f"\n*查询耗时: {total_time:.0f}ms (并行优化)*")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def analyze_time_series(params: TimeSeriesInput) -> str:
        """【优化】高级时间序列分析 - 数据库端聚合"""
        try:
            results = await service.analyze_time_series_advanced(
                params.start_date, params.end_date, params.granularity
            )
            
            if not results:
                return "未找到数据"
            
            lines = [f"# 📈 时间序列分析 ({params.granularity})\n"]
            
            for row in results:
                period = row.get("period")
                lines.append(f"### {period}")
                lines.append(f"- 事件数: {row.get('event_count', 0):,}")
                lines.append(f"- 冲突比例: {row.get('conflict_pct', 0)}%")
                lines.append(f"- 合作比例: {row.get('cooperation_pct', 0)}%")
                lines.append(f"- 平均 Goldstein: {row.get('avg_goldstein', 0)}")
                lines.append("")
            
            lines.append(f"*共 {len(results)} 个时间周期*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 分析失败: {str(e)}"
    
    
    @mcp.tool()
    async def get_geo_heatmap(params: GeoHeatmapInput) -> str:
        """【优化】地理热力图数据 - 网格聚合"""
        try:
            results = await service.get_geo_heatmap(
                params.start_date, params.end_date, params.precision
            )
            
            if not results:
                return "未找到地理数据"
            
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
            
            return f"""# 🗺️ 地理热力图数据

**时间范围**: {params.start_date} 至 {params.end_date}
**精度**: {params.precision} 位小数
**热点数量**: {len(heatmap_data)}

```json
{json.dumps(heatmap_data[:10], indent=2, ensure_ascii=False)}
```

*完整数据共 {len(heatmap_data)} 条*
"""
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def stream_query_events(params: StreamQueryInput) -> str:
        """【优化】流式查询 - 处理大量数据"""
        try:
            lines = [f"# 🔍 流式查询结果: {params.actor_name}\n"]
            lines.append("| 日期 | Actor1 | Actor2 | Goldstein | Tone | 位置 |")
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
                    lines.append("| ... | (更多结果截断) | ... | ... | ... | ... |")
                    break
            
            lines.append(f"\n*共返回 {count} 条结果 (流式读取)*")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ 流式查询失败: {str(e)}"
    
    
    @mcp.tool()
    async def get_cache_stats() -> str:
        """【诊断】查看查询缓存统计信息"""
        stats = query_cache.get_stats()
        
        hit_rate_str = stats['hit_rate'].rstrip('%')
        try:
            hit_rate = float(hit_rate_str)
            if hit_rate >= 80:
                evaluation = "✅ 命中率优秀 (≥80%)"
            elif hit_rate >= 50:
                evaluation = "⚠️ 命中率一般 (50-80%)"
            else:
                evaluation = "❌ 命中率较低 (<50%)"
        except:
            evaluation = "🤷 暂无足够数据"
        
        return f"""# 📊 查询缓存统计

| 指标 | 值 |
|------|-----|
| 缓存条目数 | {stats['size']} / {stats['maxsize']} |
| 命中次数 | {stats['hits']:,} |
| 未命中次数 | {stats['misses']:,} |
| 命中率 | {stats['hit_rate']} |
| LRU 淘汰次数 | {stats['evictions']:,} |

**评估**: {evaluation}
"""
    
    
    @mcp.tool()
    async def clear_cache() -> str:
        """清除所有查询缓存"""
        count = await query_cache.clear()
        return f"✅ 已清除 {count} 个缓存条目"
    
    @mcp.tool()
    async def search_news_context(params: NewsSearchInput) -> str:
        """
        【RAG 右腦】新聞語義搜索引擎
        
        當你需要了解事件的具體起因、人群具體訴求、警方回應或詳細新聞背景時調用此工具。
        請輸入英文自然語言查詢本地向量知識庫中真實的新聞文本片段。
        """
        # 呼叫我們在 GDELTServiceOptimized 中新增的檢索方法
        return await service.search_news_context(params.query, params.n_results)   
