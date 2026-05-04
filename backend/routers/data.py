"""
Data Routes — Dashboard API

All endpoints return structured JSON for direct frontend chart rendering.
Delegates to MCP tools (core_tools_v2) via DataService.
"""

import time
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.dependencies import get_data_service
from backend.services.data_service import DataService
from backend.schemas.responses import (
    DashboardResponse,
    TimeSeriesResponse,
    GeoHeatmapResponse,
    ForecastResponse,
    EventSearchResponse,
    HealthResponse,
    EventItem,
    TimeSeriesPoint,
    GeoPoint,
)

router = APIRouter(prefix="/data", tags=["data"])


def _json_safe(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    region: Optional[str] = Query(None, description="Optional region, country, or actor focus"),
    focus_type: str = Query("location", description="location | actor"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    service: DataService = Depends(get_data_service),
):
    """
    Get comprehensive dashboard data via MCP get_dashboard tool (format=json).
    """
    start_time = time.time()
    try:
        result = await service.get_dashboard(start, end, region, event_type, focus_type)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        
        return DashboardResponse(
            data=result,
            start_date=start,
            end_date=end,
            elapsed_ms=elapsed_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dashboard query failed: {e}")


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("day", description="day | week | month"),
    region: Optional[str] = Query(None, description="Optional region, country, or actor focus"),
    focus_type: str = Query("location", description="location | actor"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    service: DataService = Depends(get_data_service),
):
    """
    Get time series data via MCP analyze_time_series tool (format=json).
    """
    try:
        rows = await service.get_time_series(start, end, granularity, region, event_type, focus_type)
        data = [TimeSeriesPoint(**row) for row in rows]
        return TimeSeriesResponse(
            data=data,
            granularity=granularity,
            start_date=start,
            end_date=end,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Time series query failed: {e}")


@router.get("/geo", response_model=GeoHeatmapResponse)
async def get_geo_heatmap(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    precision: int = Query(2, ge=1, le=4, description="Grid precision (1-4 decimal places)"),
    region: Optional[str] = Query(None, description="Optional region, country, or actor focus"),
    focus_type: str = Query("location", description="location | actor"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    service: DataService = Depends(get_data_service),
):
    """
    Get geo heatmap grid data via MCP get_geo_heatmap tool (format=json).
    """
    try:
        rows = await service.get_geo_heatmap(start, end, precision, region, event_type, focus_type)
        data = [GeoPoint(**row) for row in rows]
        return GeoHeatmapResponse(
            data=data,
            precision=precision,
            start_date=start,
            end_date=end,
            total_points=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Geo query failed: {e}")


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    start: str = Query(..., description="Historical input start date (YYYY-MM-DD)"),
    end: str = Query(..., description="Historical input end date (YYYY-MM-DD)"),
    region: Optional[str] = Query(None, description="Optional country, region, or country pair"),
    actor: Optional[str] = Query(None, description="Optional actor keyword"),
    event_type: str = Query("all", description="all | conflict | cooperation | protest"),
    forecast_days: int = Query(7, ge=1, le=60),
    service: DataService = Depends(get_data_service),
):
    """Forecast event intensity with the Transformer Hawkes service."""
    try:
        data = await service.forecast_event_risk(
            start_date=start,
            end_date=end,
            region=region,
            actor=actor,
            event_type=event_type,
            forecast_days=forecast_days,
        )
        return ForecastResponse(
            ok=bool(data.get("ok", True)),
            error=data.get("error"),
            data=_json_safe(data),
            start_date=start,
            end_date=end,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Forecast query failed: {e}")


@router.get("/events", response_model=EventSearchResponse)
async def search_events(
    query: str = Query(..., description="Search query text"),
    time_hint: Optional[str] = Query(None, description="e.g. 2024-01, this_month"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    location_hint: Optional[str] = Query(None, description="Location keyword"),
    lat: Optional[float] = Query(None, description="Latitude for hotspot drilldown"),
    lng: Optional[float] = Query(None, description="Longitude for hotspot drilldown"),
    precision: int = Query(2, ge=1, le=4, description="Coordinate grid precision"),
    focus_type: str = Query("location", description="location | actor"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    limit: int = Query(20, ge=1, le=50),
    service: DataService = Depends(get_data_service),
):
    """
    Structured event search via MCP search_events tool (format=json).
    """
    try:
        rows = await service.search_events(
            query_text=query,
            time_hint=time_hint,
            location_hint=location_hint,
            event_type=event_type,
            max_results=limit,
            start_date=start,
            end_date=end,
            lat=lat,
            lng=lng,
            precision=precision,
            focus_type=focus_type,
        )
        data = [EventItem(**_json_safe(row)) for row in rows]
        return EventSearchResponse(
            data=data,
            query=query,
            total=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Event search failed: {e}")


@router.get("/events/{fingerprint}")
async def get_event_detail(
    fingerprint: str,
    service: DataService = Depends(get_data_service),
):
    """Get a single event detail by fingerprint or EVT-* generated id."""
    try:
        row = await service.get_event_detail(fingerprint)
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"ok": True, "data": _json_safe(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Event detail failed: {e}")


@router.get("/top-events")
async def get_top_events(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    region: Optional[str] = Query(None, description="Optional region keyword"),
    focus_type: str = Query("location", description="location | actor"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    limit: int = Query(10, ge=1, le=50),
    service: DataService = Depends(get_data_service),
):
    """Get high-impact events for an event detail drawer or report export."""
    try:
        rows = await service.get_top_events(start, end, region, event_type, limit, focus_type)
        return {"ok": True, "data": _json_safe(rows), "total": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Top events query failed: {e}")


@router.get("/compare")
async def compare_entities(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    left: str = Query(..., description="First country, actor, or keyword"),
    right: str = Query(..., description="Second country, actor, or keyword"),
    event_type: str = Query("any", description="any | conflict | cooperation | protest"),
    focus_type: str = Query("location", description="location | actor"),
    service: DataService = Depends(get_data_service),
):
    """Compare two countries, actors, or keywords over time."""
    try:
        data = await service.compare_entities(start, end, left, right, event_type, focus_type)
        return {"ok": True, "data": _json_safe(data)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Compare query failed: {e}")


@router.get("/country-pair")
async def get_country_pair_trends(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    country_a: str = Query(..., description="First country name or code"),
    country_b: str = Query(..., description="Second country name or code"),
    service: DataService = Depends(get_data_service),
):
    """Get true bilateral trends using Actor1CountryCode/Actor2CountryCode."""
    try:
        data = await service.get_country_pair_trends(start, end, country_a, country_b)
        return {"ok": True, "data": _json_safe(data)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Country-pair query failed: {e}")


@router.get("/health", response_model=HealthResponse)
async def health_check(
    service: DataService = Depends(get_data_service),
):
    """
    Health check including MCP latency.
    """
    try:
        mcp_health = await service.health_check()
        cache_stats = service.get_cache_stats()
        return HealthResponse(
            db_status=mcp_health.get("status", "unknown"),
            db_latency_ms=mcp_health.get("latency_ms"),
            cache_stats=cache_stats,
            server_time=None,
        )
    except Exception as e:
        return HealthResponse(
            ok=False,
            db_status="unhealthy",
            error=str(e),
            cache_stats=service.get_cache_stats(),
        )
