"""
Data Service — Thin wrapper around shared core_queries.

No SQL is written here. All queries go through mcp_server.app.queries.core_queries,
ensuring a single source of truth for data logic.

Dashboard calls these directly (fast, < 300ms).
Chat Agent calls them via MCP tools (standard protocol).
"""

import time
import copy
import os
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
    query_search_news_context,
    query_compare_entities,
    query_country_pair_trends,
    query_event_sequence,
)
from backend.services.thp_service import TransformerHawkesForecaster


class DataService:
    """High-performance data service for Dashboard APIs."""

    def __init__(self):
        self._pool: Optional[DatabasePool] = None
        self._initialized = False
        self._thp = TransformerHawkesForecaster()
        self._cache: Dict[Any, Any] = {}
        self._cache_ttl_seconds = int(os.getenv("API_CACHE_TTL_SECONDS", "300"))

    def _cache_get(self, key: Any) -> Optional[Any]:
        cached = self._cache.get(key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at < time.time():
            self._cache.pop(key, None)
            return None
        return copy.deepcopy(value)

    def _cache_set(self, key: Any, value: Any) -> Any:
        if self._cache_ttl_seconds <= 0:
            return value
        if len(self._cache) > 512:
            now = time.time()
            self._cache = {
                cache_key: cache_value
                for cache_key, cache_value in self._cache.items()
                if cache_value[0] >= now
            }
        self._cache[key] = (time.time() + self._cache_ttl_seconds, copy.deepcopy(value))
        return value

    async def initialize(self):
        if not self._initialized:
            self._pool = await get_db_pool()
            self._initialized = True

    async def close(self):
        from mcp_server.app.database.pool import close_db_pool
        await close_db_pool()
        self._pool = None
        self._initialized = False

    async def get_dashboard(
        self,
        start_date: str,
        end_date: str,
        region_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        focus_type: str = "location",
    ) -> Dict[str, Any]:
        cache_key = ("dashboard", start_date, end_date, region_filter or "", event_type or "", focus_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached.setdefault("_meta", {})
            cached["_meta"]["cache_hit"] = True
            return cached
        start = time.time()
        result = await query_dashboard(
            self._pool, start_date, end_date, region_filter, event_type, focus_type
        )
        result["_meta"] = {
            "elapsed_ms": round((time.time() - start) * 1000, 2),
            "start_date": start_date,
            "end_date": end_date,
            "region_filter": region_filter,
            "event_type": event_type,
            "focus_type": focus_type,
            "cache_hit": False,
        }
        return self._cache_set(cache_key, result)

    async def get_time_series(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "day",
        region_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        focus_type: str = "location",
    ) -> List[Dict[str, Any]]:
        cache_key = ("timeseries", start_date, end_date, granularity, region_filter or "", event_type or "", focus_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        rows = await query_time_series(
            self._pool, start_date, end_date, granularity, region_filter, event_type, focus_type
        )
        return self._cache_set(cache_key, rows)

    async def forecast_event_risk(
        self,
        start_date: str,
        end_date: str,
        region: Optional[str] = None,
        actor: Optional[str] = None,
        event_type: str = "all",
        forecast_days: int = 7,
    ) -> Dict[str, Any]:
        cache_key = ("forecast", start_date, end_date, region or "", actor or "", event_type, forecast_days)
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached.setdefault("_meta", {})
            cached["_meta"]["cache_hit"] = True
            return cached
        start = time.time()
        rows = await query_event_sequence(
            self._pool,
            start_date=start_date,
            end_date=end_date,
            region=region,
            actor=actor,
            event_type=event_type,
        )
        result = self._thp.forecast(
            rows=rows,
            start_date=start_date,
            end_date=end_date,
            forecast_days=forecast_days,
            region=region,
            actor=actor,
            event_type=event_type,
        )
        result["_meta"] = {
            "elapsed_ms": round((time.time() - start) * 1000, 2),
            "history_rows": len(rows),
            "source": "thp_service",
            "cache_hit": False,
        }
        return self._cache_set(cache_key, result)

    async def get_geo_heatmap(
        self,
        start_date: str,
        end_date: str,
        precision: int = 2,
        region_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        focus_type: str = "location",
    ) -> List[Dict[str, Any]]:
        cache_key = ("geo", start_date, end_date, precision, region_filter or "", event_type or "", focus_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        rows = await query_geo_heatmap(
            self._pool, start_date, end_date, precision, region_filter, event_type, focus_type
        )
        return self._cache_set(cache_key, rows)

    async def search_events(
        self, query_text: str, time_hint: Optional[str] = None,
        location_hint: Optional[str] = None, event_type: Optional[str] = None,
        max_results: int = 20, start_date: Optional[str] = None,
        end_date: Optional[str] = None, lat: Optional[float] = None,
        lng: Optional[float] = None, precision: int = 2,
        focus_type: str = "location",
    ) -> List[Dict[str, Any]]:
        return await query_search_events(
            self._pool,
            query_text,
            time_hint,
            location_hint,
            event_type,
            max_results,
            start_date,
            end_date,
            lat,
            lng,
            precision,
            focus_type,
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
        region_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        top_n: int = 10,
        focus_type: str = "location",
    ) -> List[Dict[str, Any]]:
        cache_key = ("top_events", start_date, end_date, region_filter or "", event_type or "", top_n, focus_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        rows = await query_top_events(
            self._pool, start_date, end_date, region_filter, event_type, top_n, focus_type
        )
        return self._cache_set(cache_key, rows)

    async def compare_entities(
        self,
        start_date: str,
        end_date: str,
        left: str,
        right: str,
        event_type: str = "any",
    ) -> Dict[str, Any]:
        cache_key = ("compare", start_date, end_date, left, right, event_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = await query_compare_entities(
            self._pool, start_date, end_date, left, right, event_type
        )
        return self._cache_set(cache_key, result)

    async def get_country_pair_trends(
        self,
        start_date: str,
        end_date: str,
        country_a: str,
        country_b: str,
    ) -> Dict[str, Any]:
        cache_key = ("country_pair", start_date, end_date, country_a, country_b)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = await query_country_pair_trends(
            self._pool, start_date, end_date, country_a, country_b
        )
        return self._cache_set(cache_key, result)

    async def get_daily_brief(self, query_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return await query_daily_brief(self._pool, query_date)

    async def search_news_context(
        self, query: str, n_results: int = 5
    ) -> Dict[str, Any]:
        """Search news article content via ChromaDB vector semantic search."""
        return await query_search_news_context(query, n_results)

    def get_cache_stats(self) -> Dict[str, Any]:
        checkpoint = getattr(self._thp, "neural_checkpoint", None)
        return {
            "mode": "shared_queries",
            "note": "Queries handled by core_queries",
            "thp_model": self._thp._model_name(),
            "thp_checkpoint_available": bool(getattr(checkpoint, "available", False)),
            "thp_checkpoint_error": getattr(checkpoint, "error", None),
        }

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
