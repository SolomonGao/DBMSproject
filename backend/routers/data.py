"""
Data Routes — Dashboard API

All endpoints return structured JSON for direct frontend chart rendering.
No LLM involved. Low latency (< 300ms) via caching and parallel queries.
"""

import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.dependencies import get_data_service
from backend.services.data_service import DataService
from backend.schemas.responses import (
    DashboardResponse,
    TimeSeriesResponse,
    GeoHeatmapResponse,
    EventSearchResponse,
    HealthResponse,
    EventItem,
    TimeSeriesPoint,
    GeoPoint,
)

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    service: DataService = Depends(get_data_service),
):
    """
    Get comprehensive dashboard data:
    - Daily trend (event count, goldstein avg, conflict count)
    - Top 10 actors
    - Geographic distribution (top 10 countries)
    - Event type breakdown
    - Summary statistics
    """
    start_time = time.time()
    try:
        result = await service.get_dashboard(start, end)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        
        return DashboardResponse(
            data=result,
            start_date=start,
            end_date=end,
            elapsed_ms=elapsed_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard query failed: {e}")


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("day", description="day | week | month"),
    service: DataService = Depends(get_data_service),
):
    """
    Get time series data with conflict/cooperation breakdown.
    Aggregated entirely in the database for minimal network transfer.
    """
    try:
        rows = await service.get_time_series(start, end, granularity)
        # Normalize keys
        data = [TimeSeriesPoint(**row) for row in rows]
        return TimeSeriesResponse(
            data=data,
            granularity=granularity,
            start_date=start,
            end_date=end,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Time series query failed: {e}")


@router.get("/geo", response_model=GeoHeatmapResponse)
async def get_geo_heatmap(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    precision: int = Query(2, ge=1, le=4, description="Grid precision (1-4 decimal places)"),
    service: DataService = Depends(get_data_service),
):
    """
    Get geo heatmap grid data.
    Filters sparse points (intensity < 5) to reduce frontend rendering load.
    """
    try:
        rows = await service.get_geo_heatmap(start, end, precision)
        data = [GeoPoint(**row) for row in rows]
        return GeoHeatmapResponse(
            data=data,
            precision=precision,
            start_date=start,
            end_date=end,
            total_points=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geo query failed: {e}")


@router.get("/events", response_model=EventSearchResponse)
async def search_events(
    query: str = Query(..., description="Search query text"),
    time_hint: Optional[str] = Query(None, description="e.g. 2024-01, this_month"),
    location_hint: Optional[str] = Query(None, description="Location keyword"),
    event_type: Optional[str] = Query(None, description="conflict | cooperation | protest"),
    limit: int = Query(20, ge=1, le=50),
    service: DataService = Depends(get_data_service),
):
    """
    Structured event search with optional filters.
    Returns full event records including fingerprint and headline when available.
    """
    try:
        rows = await service.search_events(
            query_text=query,
            time_hint=time_hint,
            location_hint=location_hint,
            event_type=event_type,
            max_results=limit,
        )
        data = [EventItem(**row) for row in rows]
        return EventSearchResponse(
            data=data,
            query=query,
            total=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event search failed: {e}")


@router.get("/health", response_model=HealthResponse)
async def health_check(
    service: DataService = Depends(get_data_service),
):
    """
    Health check including DB latency and cache statistics.
    """
    try:
        db_health = await service.health_check()
        cache_stats = service.get_cache_stats()
        return HealthResponse(
            db_status=db_health.get("status", "unknown"),
            db_latency_ms=db_health.get("latency_ms"),
            cache_stats=cache_stats,
            server_time=db_health.get("server_time"),
        )
    except Exception as e:
        return HealthResponse(
            ok=False,
            db_status="unhealthy",
            error=str(e),
            cache_stats=service.get_cache_stats(),
        )
