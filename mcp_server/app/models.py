"""
GDELT MCP Server - 输入输出模型

定义所有工具的输入参数模型。
"""

from pydantic import BaseModel, Field


class SQLQueryInput(BaseModel):
    """SQL 查询输入"""
    query: str = Field(
        ..., 
        description="SQL SELECT 查询语句，用于查询 GDELT 事件数据"
    )


class TableSchemaInput(BaseModel):
    """表结构查询输入"""
    table_name: str = Field(
        default="events_table",
        description="要查询的表名，默认为 events_table"
    )


class TimeRangeQueryInput(BaseModel):
    """时间范围查询输入"""
    start_date: str = Field(
        ..., 
        description="开始日期，格式: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ..., 
        description="结束日期，格式: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="返回结果数量限制"
    )


class ActorQueryInput(BaseModel):
    """参与方查询输入"""
    actor_name: str = Field(
        ..., 
        description="参与方名称关键词，如 'Trump', 'China'"
    )
    start_date: str = Field(
        default=None,
        description="开始日期，可选，格式: YYYY-MM-DD"
    )
    end_date: str = Field(
        default=None,
        description="结束日期，可选，格式: YYYY-MM-DD"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="返回结果数量限制"
    )


class GeoQueryInput(BaseModel):
    """地理范围查询输入"""
    lat: float = Field(
        ..., 
        description="中心纬度",
        ge=-90,
        le=90
    )
    lon: float = Field(
        ..., 
        description="中心经度",
        ge=-180,
        le=180
    )
    radius_km: float = Field(
        default=100,
        description="搜索半径（公里）",
        ge=1,
        le=1000
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="返回结果数量限制"
    )


class EventAnalysisInput(BaseModel):
    """事件分析输入"""
    start_date: str = Field(
        ..., 
        description="开始日期，格式: YYYY-MM-DD"
    )
    end_date: str = Field(
        ..., 
        description="结束日期，格式: YYYY-MM-DD"
    )
    actor1: str = Field(
        default=None,
        description="参与方1，可选"
    )
    actor2: str = Field(
        default=None,
        description="参与方2，可选"
    )


class VisualizationInput(BaseModel):
    """数据可视化输入"""
    query: str = Field(
        ..., 
        description="生成图表的 SQL 查询（应返回可用于绘图的数据）"
    )
    chart_type: str = Field(
        default="line",
        description="图表类型: line(折线), bar(柱状), pie(饼图), scatter(散点)",
        pattern=r"^(line|bar|pie|scatter)$"
    )
    title: str = Field(
        default="GDELT 数据分析",
        description="图表标题"
    )

class NewsSearchInput(BaseModel):
    """新闻语义搜索输入"""
    query: str = Field(
        ..., 
        description="英文语义搜索查询词，例如 'protesters demanding climate action', 'police response'"
    )
    n_results: int = Field(
        default=3,
        description="返回的相关新闻数量限制",
        ge=1,
        le=10
    )