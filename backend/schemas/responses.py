"""
Pydantic schemas for API request/response validation.

All Dashboard endpoints return structured JSON for direct chart rendering.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import date


# ============================================================================
# Base Response
# ============================================================================

class BaseResponse(BaseModel):
    ok: bool = True
    error: Optional[str] = None


# ============================================================================
# Dashboard Data
# ============================================================================

class DailyTrendPoint(BaseModel):
    sql_date: str = Field(..., alias="SQLDATE")
    event_count: int
    goldstein: Optional[float]
    conflict: int

    class Config:
        populate_by_name = True


class TopActorItem(BaseModel):
    actor: str = Field(..., alias="Actor1Name")
    event_count: int

    class Config:
        populate_by_name = True


class GeoDistributionItem(BaseModel):
    country_code: str = Field(..., alias="ActionGeo_CountryCode")
    event_count: int

    class Config:
        populate_by_name = True


class EventTypeItem(BaseModel):
    event_type: str
    event_count: int


class SummaryStats(BaseModel):
    total_events: int
    unique_actors: int
    avg_goldstein: Optional[float]
    avg_tone: Optional[float]
    total_articles: int


class DashboardData(BaseModel):
    daily_trend: Dict[str, Any]  # { data: [...], count, elapsed_ms }
    top_actors: Dict[str, Any]
    geo_distribution: Dict[str, Any]
    event_types: Dict[str, Any]
    summary_stats: Dict[str, Any]


class DashboardResponse(BaseResponse):
    data: Optional[DashboardData] = None
    start_date: str
    end_date: str
    elapsed_ms: Optional[float] = None


# ============================================================================
# Time Series Data
# ============================================================================

class TimeSeriesPoint(BaseModel):
    period: str
    event_count: int
    conflict_pct: Optional[float]
    cooperation_pct: Optional[float]
    avg_goldstein: Optional[float]
    std_goldstein: Optional[float]
    avg_tone: Optional[float]
    std_tone: Optional[float]
    top_actors_json: Optional[str] = None


class TimeSeriesResponse(BaseResponse):
    data: List[TimeSeriesPoint]
    granularity: str
    start_date: str
    end_date: str


# ============================================================================
# Geo Heatmap Data
# ============================================================================

class GeoPoint(BaseModel):
    lat: float
    lng: float
    intensity: int
    avg_conflict: Optional[float]
    sample_location: Optional[str]


class GeoHeatmapResponse(BaseResponse):
    data: List[GeoPoint]
    precision: int
    start_date: str
    end_date: str
    total_points: int


# ============================================================================
# Event Search Data
# ============================================================================

class EventItem(BaseModel):
    global_event_id: int = Field(..., alias="GlobalEventID")
    sql_date: str = Field(..., alias="SQLDATE")
    actor1_name: Optional[str] = Field(None, alias="Actor1Name")
    actor2_name: Optional[str] = Field(None, alias="Actor2Name")
    event_code: Optional[str] = Field(None, alias="EventCode")
    goldstein_scale: Optional[float] = Field(None, alias="GoldsteinScale")
    avg_tone: Optional[float] = Field(None, alias="AvgTone")
    num_articles: Optional[int] = Field(None, alias="NumArticles")
    action_geo_full_name: Optional[str] = Field(None, alias="ActionGeo_FullName")
    action_geo_country_code: Optional[str] = Field(None, alias="ActionGeo_CountryCode")
    action_geo_lat: Optional[float] = Field(None, alias="ActionGeo_Lat")
    action_geo_long: Optional[float] = Field(None, alias="ActionGeo_Long")
    fingerprint: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    event_type_label: Optional[str] = None
    severity_score: Optional[float] = None

    class Config:
        populate_by_name = True


class EventSearchResponse(BaseResponse):
    data: List[EventItem]
    query: str
    total: int


# ============================================================================
# News / RAG Data
# ============================================================================

class NewsResult(BaseModel):
    event_id: str
    date: str
    source_url: str
    snippet: str


class NewsSearchResponse(BaseResponse):
    data: List[NewsResult]
    query: str


# ============================================================================
# Health
# ============================================================================

class HealthResponse(BaseResponse):
    db_status: str
    db_latency_ms: Optional[float]
    cache_stats: Dict[str, Any]
    server_time: Optional[str]


# ============================================================================
# Agent Chat
# ============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[Dict[str, str]] = Field(default_factory=list)
    session_id: Optional[str] = None


class ThinkingStep(BaseModel):
    type: str
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ChatResponse(BaseResponse):
    reply: str
    session_id: str
    thinking_steps: List[ThinkingStep] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)


class ToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ToolsResponse(BaseResponse):
    tools: List[ToolInfo]


# ============================================================================
# Help / Documentation
# ============================================================================

class HelpItem(BaseModel):
    command: str
    description: str
    example: Optional[str] = None


class HelpsResponse(BaseResponse):
    helps: List[HelpItem]
    system_prompt_summary: str = "GDELT Analyst — conversational intelligence for geopolitical events"
    tips: List[str] = Field(default_factory=list)
