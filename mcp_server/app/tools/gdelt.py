"""
GDELT 数据库工具模块

提供针对 GDELT 事件数据库的完整查询和分析工具。
"""

from app.services.gdelt import GDELTService
from app.models import (
    SQLQueryInput,
    TableSchemaInput,
    TimeRangeQueryInput,
    ActorQueryInput,
    GeoQueryInput,
    EventAnalysisInput,
    VisualizationInput,
)

# 服务实例
gdelt_service = GDELTService()


def create_gdelt_tools(mcp):
    """创建所有 GDELT 数据库工具（装饰器模式）"""
    
    # ==================== 基础查询工具 ====================
    
    @mcp.tool()
    async def get_schema(params: TableSchemaInput) -> str:
        """
        获取数据库表结构
        
        在编写查询前，先了解可用的字段和数据类型。
        """
        return await gdelt_service.get_schema(params.table_name)
    
    
    @mcp.tool()
    async def get_schema_guide() -> str:
        """
        获取 GDELT 数据库使用指南
        
        包含字段说明、查询示例、CAMEO 代码参考等完整文档。
        """
        return await gdelt_service.get_schema_prompt()
    
    
    @mcp.tool()
    async def execute_sql(params: SQLQueryInput) -> str:
        """
        执行自定义 SQL 查询
        
        安全限制：仅支持 SELECT 语句，自动添加 LIMIT 100。
        支持完整的 GDELT 表查询。
        """
        return await gdelt_service.execute_sql(params.query)
    
    
    # ==================== 便捷查询工具 ====================
    
    @mcp.tool()
    async def query_by_time_range(params: TimeRangeQueryInput) -> str:
        """
        按时间范围查询事件
        
        快速查询指定日期范围内的事件记录。
        """
        return await gdelt_service.query_by_time_range(
            start_date=params.start_date,
            end_date=params.end_date,
            limit=params.limit
        )
    
    
    @mcp.tool()
    async def query_by_actor(params: ActorQueryInput) -> str:
        """
        按参与方查询事件
        
        搜索涉及特定国家、组织或个人名称的事件。
        支持模糊匹配，如 'Trump' 会匹配 'Donald Trump'。
        """
        return await gdelt_service.query_by_actor(
            actor_name=params.actor_name,
            start_date=params.start_date,
            end_date=params.end_date,
            limit=params.limit
        )
    
    
    @mcp.tool()
    async def query_by_location(params: GeoQueryInput) -> str:
        """
        按地理位置查询事件
        
        基于 Haversine 公式计算球面距离，搜索指定坐标周围的事件。
        需要数据库支持空间索引（MySQL 8.0+）。
        """
        return await gdelt_service.query_by_location(
            lat=params.lat,
            lon=params.lon,
            radius_km=params.radius_km,
            limit=params.limit
        )
    
    
    # ==================== 统计分析工具 ====================
    
    @mcp.tool()
    async def analyze_daily_events(params: EventAnalysisInput) -> str:
        """
        按日期统计事件趋势
        
        返回每日事件数量、平均 GoldsteinScale、平均语调的统计结果。
        """
        return await gdelt_service.analyze_events_by_date(
            start_date=params.start_date,
            end_date=params.end_date
        )
    
    
    @mcp.tool()
    async def analyze_top_actors(params: EventAnalysisInput) -> str:
        """
        统计最活跃的参与方
        
        返回在指定时间段内事件数量最多的参与方排名。
        """
        return await gdelt_service.analyze_top_actors(
            start_date=params.start_date,
            end_date=params.end_date
        )
    
    
    @mcp.tool()
    async def analyze_conflict_cooperation(params: EventAnalysisInput) -> str:
        """
        分析冲突/合作趋势
        
        基于 GoldsteinScale 统计每日的冲突事件数、合作事件数和平均强度。
        """
        return await gdelt_service.analyze_conflict_cooperation_trend(
            start_date=params.start_date,
            end_date=params.end_date
        )
    
    
    # ==================== 可视化工具 ====================
    
    @mcp.tool()
    async def generate_chart(params: VisualizationInput) -> str:
        """
        生成数据可视化配置
        
        基于查询结果生成 ECharts 图表配置（JSON 格式）。
        需要前端支持 ECharts 渲染才能显示图表。
        """
        return await gdelt_service.generate_chart(
            query=params.query,
            chart_type=params.chart_type,
            title=params.title
        )
    
    
    return (
        get_schema,
        get_schema_guide,
        execute_sql,
        query_by_time_range,
        query_by_actor,
        query_by_location,
        analyze_daily_events,
        analyze_top_actors,
        analyze_conflict_cooperation,
        generate_chart,
    )
