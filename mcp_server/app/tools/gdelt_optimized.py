"""
优化版 GDELT MCP Tools

整合缓存、流式、并行等优化技术。
包含所有原始工具 + 优化版新工具。
"""

import json
import math
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
| `Actor1Name` | VARCHAR | 主要参与方名称 |
| `Actor2Name` | VARCHAR | 次要参与方名称 |
| `GoldsteinScale` | FLOAT | 冲突/合作强度 (-10 到 +10) |
| `AvgTone` | FLOAT | 新闻语调 (-100 到 +100) |
| `ActionGeo_Lat` | DECIMAL | 事件发生地纬度 |
| `ActionGeo_Long` | DECIMAL | 事件发生地经度 |

### 查询建议

- 时间+地理组合查询：使用 query_by_location_and_time（最高效）
- 纯时间查询：使用 query_by_time_range
- 纯地理查询：使用 query_by_location
"""


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


class LocationTimeQueryInput(BaseModel):
    """
    地理+时间组合查询输入
    
    这是最高效的查询方式，先按时间过滤，再按地理筛选。
    适用于：查询某时间段内某地点附近的事件
    """
    lat: float = Field(..., description="中心纬度", ge=-90, le=90)
    lon: float = Field(..., description="中心经度", ge=-180, le=180)
    radius_km: float = Field(default=100, description="搜索半径（公里）", ge=1, le=1000)
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
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


# ==================== 文本清理工具 ====================

def sanitize_text(text: Any) -> str:
    """清理文本中的非法 UTF-8 字符"""
    if text is None:
        return "N/A"
    text = str(text)
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    return text.replace('\x00', '')


# ==================== 工具注册 ====================

def create_optimized_tools(mcp):
    """创建所有优化版 GDELT 工具（全部支持缓存）"""
    
    service = GDELTServiceOptimized()
    
    # ==================== 基础工具 ====================
    
    @mcp.tool()
    async def get_schema(params: TableSchemaInput) -> str:
        """获取数据库表结构"""
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
        return _get_schema_guide_text()
    
    
    @mcp.tool()
    async def execute_sql(params: SQLQueryInput) -> str:
        """执行自定义 SQL 查询（带缓存）"""
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
        """按参与方查询事件（带缓存）"""
        return await service.query_by_actor_cached(
            params.actor_name, params.start_date, params.end_date, params.limit, cache_ttl=300
        )
    
    
    @mcp.tool()
    async def query_by_location(params: GeoQueryInput) -> str:
        """按地理位置查询事件（带缓存）"""
        # 计算边界框（用于索引预过滤）
        lat_delta = params.radius_km / 111.0
        cos_lat = math.cos(math.radians(params.lat))
        lon_delta = params.radius_km / (111.0 * max(cos_lat, 0.01))
        
        lat_min, lat_max = params.lat - lat_delta, params.lat + lat_delta
        lon_min, lon_max = params.lon - lon_delta, params.lon + lon_delta
        
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
               ActionGeo_Lat, ActionGeo_Long,
               GoldsteinScale, AvgTone, SOURCEURL,
               (6371 * acos(
                   cos(radians(%s)) * cos(radians(ActionGeo_Lat)) * 
                   cos(radians(ActionGeo_Long) - radians(%s)) + 
                   sin(radians(%s)) * sin(radians(ActionGeo_Lat))
               )) AS distance_km
        FROM {service.DEFAULT_TABLE}
        WHERE ActionGeo_Lat BETWEEN %s AND %s
          AND ActionGeo_Long BETWEEN %s AND %s
          AND ActionGeo_Lat != 0
          AND ActionGeo_Long != 0
        HAVING distance_km <= %s
        ORDER BY distance_km
        LIMIT %s
        """
        
        sql_params = (
            params.lat, params.lon, params.lat,
            lat_min, lat_max, lon_min, lon_max,
            params.radius_km,
            params.limit
        )
        
        rows = await service.execute_sql_cached(query, sql_params, cache_ttl=600)
        
        if not rows:
            return f"未找到距离 ({params.lat}, {params.lon}) {params.radius_km}km 内的事件"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def query_by_location_and_time(params: LocationTimeQueryInput) -> str:
        """
        【推荐】按地理位置+时间范围组合查询
        
        这是最高效的地理时间组合查询，先按时间过滤，再按地理筛选。
        适用于：查询某时间段内某地点附近的事件（如"1月份DC附近的新闻"）
        
        性能：比分别执行 query_by_time_range + query_by_location 快 10-50 倍
        """
        # 计算边界框
        lat_delta = params.radius_km / 111.0
        cos_lat = math.cos(math.radians(params.lat))
        lon_delta = params.radius_km / (111.0 * max(cos_lat, 0.01))
        
        lat_min, lat_max = params.lat - lat_delta, params.lat + lat_delta
        lon_min, lon_max = params.lon - lon_delta, params.lon + lon_delta
        
        query = f"""
        SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
               ActionGeo_Lat, ActionGeo_Long,
               GoldsteinScale, AvgTone, SOURCEURL,
               (6371 * acos(
                   cos(radians(%s)) * cos(radians(ActionGeo_Lat)) * 
                   cos(radians(ActionGeo_Long) - radians(%s)) + 
                   sin(radians(%s)) * sin(radians(ActionGeo_Lat))
               )) AS distance_km
        FROM {service.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s          -- 先用时间索引过滤！
          AND ActionGeo_Lat BETWEEN %s AND %s    -- 再用地理索引过滤！
          AND ActionGeo_Long BETWEEN %s AND %s
          AND ActionGeo_Lat != 0
          AND ActionGeo_Long != 0
        HAVING distance_km <= %s
        ORDER BY 
            CASE WHEN GoldsteinScale < 0 THEN ABS(GoldsteinScale) ELSE 0 END DESC,
            distance_km
        LIMIT %s
        """
        
        sql_params = (
            params.lat, params.lon, params.lat,      # Haversine 参数
            params.start_date, params.end_date,       # 时间范围
            lat_min, lat_max, lon_min, lon_max,       # 地理边界
            params.radius_km,                         # 精确距离
            params.limit                              # 限制
        )
        
        rows = await service.execute_sql_cached(query, sql_params, cache_ttl=300)
        
        if not rows:
            return f"未找到 {params.start_date} 至 {params.end_date} 期间，距离 ({params.lat}, {params.lon}) {params.radius_km}km 内的事件"
        
        columns = list(rows[0].keys())
        row_tuples = [tuple(row.get(col) for col in columns) for row in rows]
        return service._format_markdown(columns, row_tuples)
    
    
    @mcp.tool()
    async def analyze_daily_events(params: EventAnalysisInput) -> str:
        """按日期统计事件数量（带缓存）"""
        return await service.analyze_daily_events_cached(
            params.start_date, params.end_date, cache_ttl=600
        )
    
    
    @mcp.tool()
    async def analyze_top_actors(params: EventAnalysisInput) -> str:
        """统计最活跃的参与方（带缓存）"""
        return await service.analyze_top_actors_cached(
            params.start_date, params.end_date, top_n=10, cache_ttl=600
        )
    
    
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
    async def get_dashboard(params: DashboardInput) -> str:
        """【优化】仪表盘数据 - 并发获取多维度统计"""
        try:
            dashboard = await service.get_dashboard_data(params.start_date, params.end_date)
            
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
    async def get_cache_stats() -> str:
        """查看查询缓存统计信息"""
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
