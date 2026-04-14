"""
GDELT MCP Server - Input/Output Models

Defines input parameter models for all tools.
"""

from pydantic import BaseModel, Field


class SQLQueryInput(BaseModel):
    """SQL query input"""
    query: str = Field(
        ..., 
        description="SQL SELECT query statement for querying GDELT event data"
    )


class TableSchemaInput(BaseModel):
    """Table schema query input"""
    table_name: str = Field(
        default="events_table",
        description="Table name to query, default is events_table"
    )


class TimeRangeQueryInput(BaseModel):
    """Time range query input"""
    start_date: str = Field(
        ..., 
        description="Start date, format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ..., 
        description="End date, format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Limit on number of results to return"
    )


class ActorQueryInput(BaseModel):
    """Actor query input"""
    actor_name: str = Field(
        ..., 
        description="Actor name keyword, e.g., 'Trump', 'China'"
    )
    start_date: str = Field(
        default=None,
        description="Start date, optional, format: YYYY-MM-DD"
    )
    end_date: str = Field(
        default=None,
        description="End date, optional, format: YYYY-MM-DD"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Limit on number of results to return"
    )


class GeoQueryInput(BaseModel):
    """Geographic range query input"""
    lat: float = Field(
        ..., 
        description="Center latitude",
        ge=-90,
        le=90
    )
    lon: float = Field(
        ..., 
        description="Center longitude",
        ge=-180,
        le=180
    )
    radius_km: float = Field(
        default=100,
        description="Search radius (kilometers)",
        ge=1,
        le=1000
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Limit on number of results to return"
    )


class EventAnalysisInput(BaseModel):
    """Event analysis input"""
    start_date: str = Field(
        ..., 
        description="Start date, format: YYYY-MM-DD"
    )
    end_date: str = Field(
        ..., 
        description="End date, format: YYYY-MM-DD"
    )
    actor1: str = Field(
        default=None,
        description="Actor 1, optional"
    )
    actor2: str = Field(
        default=None,
        description="Actor 2, optional"
    )


class VisualizationInput(BaseModel):
    """Data visualization input"""
    query: str = Field(
        ..., 
        description="SQL query to generate chart (should return data suitable for plotting)"
    )
    chart_type: str = Field(
        default="line",
        description="Chart type: line, bar, pie, scatter",
        pattern=r"^(line|bar|pie|scatter)$"
    )
    title: str = Field(
        default="GDELT Data Analysis",
        description="Chart title"
    )


class NewsSearchInput(BaseModel):
    """News semantic search input"""
    query: str = Field(
        ..., 
        description="English semantic search query, e.g., 'protesters demanding climate action', 'police response'"
    )
    n_results: int = Field(
        default=3,
        description="Limit on number of related news to return",
        ge=1,
        le=10
    )
