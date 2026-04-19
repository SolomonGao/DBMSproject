"""
Data Service — Thin wrapper around shared core_queries.

No SQL is written here. All queries go through mcp_server.app.queries.core_queries,
ensuring a single source of truth for data logic.

Dashboard calls these directly (fast, < 300ms).
Chat Agent calls them via MCP tools (standard protocol).
"""

import time
from typing import List, Dict, Any, Optional

from mcp_server.app.database.pool import DatabasePool, get_db_pool
from mcp_server.app.queries.core_queries import (
    query_dashboard,
    query_time_series,
    query_geo_heatmap,
    query_search_events,
    query_event_detail,
    query_regional_overview,
    query_hot_events,
    query_top_events,
    query_daily_brief,
)


class DataService:
    """High-performance data service for Dashboard APIs."""

    def __init__(self):
        self._pool: Optional[DatabasePool] = None
        self._initialized = False

    async def initialize(self):
        if not self._initialized:
            self._pool = await get_db_pool()
            self._initialized = True

    async def close(self):
        from mcp_server.app.database.pool import close_db_pool
        await close_db_pool()
        self._pool = None
        self._initialized = False

    async def get_dashboard(self, start_date: str, end_date: str) -> Dict[str, Any]:
        start = time.time()
        result = await query_dashboard(self._pool, start_date, end_date)
        result["_meta"] = {
            "elapsed_ms": round((time.time() - start) * 1000, 2),
            "start_date": start_date,
            "end_date": end_date,
        }
        return result

    async def get_time_series(
        self, start_date: str, end_date: str, granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        return await query_time_series(self._pool, start_date, end_date, granularity)

    async def get_geo_heatmap(
        self, start_date: str, end_date: str, precision: int = 2
    ) -> List[Dict[str, Any]]:
        return await query_geo_heatmap(self._pool, start_date, end_date, precision)

    async def search_events(
        self, query_text: str, time_hint: Optional[str] = None,
        location_hint: Optional[str] = None, event_type: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        return await query_search_events(
            self._pool, query_text, time_hint, location_hint, event_type, max_results
        )

    async def get_event_detail(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        return await query_event_detail(self._pool, fingerprint)

    async def get_regional_overview(self, region: str, time_range: str = "week") -> Dict[str, Any]:
        return await query_regional_overview(self._pool, region, time_range)

    async def get_hot_events(
        self, query_date: Optional[str] = None, region_filter: Optional[str] = None, top_n: int = 5
    ) -> List[Dict[str, Any]]:
        return await query_hot_events(self._pool, query_date, region_filter, top_n)

    async def get_top_events(
        self, start_date: str, end_date: str,
        region_filter: Optional[str] = None, event_type: Optional[str] = None, top_n: int = 10
    ) -> List[Dict[str, Any]]:
        return await query_top_events(self._pool, start_date, end_date, region_filter, event_type, top_n)

    async def get_daily_brief(self, query_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return await query_daily_brief(self._pool, query_date)

    def get_cache_stats(self) -> Dict[str, Any]:
        return {"mode": "shared_queries", "note": "Queries handled by core_queries"}

    async def health_check(self) -> Dict[str, Any]:
        try:
            import time as _time
            t0 = _time.time()
            await self._pool.fetchone("SELECT 1 as test, NOW() as server_time")
            latency_ms = round((_time.time() - t0) * 1000, 2)
            return {"status": "healthy", "latency_ms": latency_ms}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
data_service = DataService()
