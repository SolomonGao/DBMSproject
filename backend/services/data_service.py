"""
Data Service — Direct database access for Dashboard APIs.

Wraps GDELTServiceOptimized to return structured JSON instead of markdown text.
Runs independently from MCP Server with its own DB connection pool.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from mcp_server.app.database.pool import DatabasePool
from mcp_server.app.cache import QueryCache


class DataService:
    """
    High-performance data service for Dashboard queries.
    
    Features:
    - Independent DB pool (no conflict with MCP Server)
    - LRU+TTL query caching
    - Parallel multi-query execution
    - Structured JSON output for chart libraries
    """
    
    DEFAULT_TABLE = "events_table"
    MAX_ROWS = 100
    
    def __init__(self):
        self._pool: Optional[DatabasePool] = None
        self._cache = QueryCache(maxsize=512, default_ttl=300)
        self._initialized = False
    
    async def initialize(self):
        """Initialize DB pool on FastAPI startup."""
        if not self._initialized:
            self._pool = await DatabasePool.initialize()
            self._initialized = True
    
    async def close(self):
        """Close DB pool on FastAPI shutdown."""
        if self._initialized and self._pool:
            await DatabasePool.close()
            self._pool = None
            self._initialized = False
    
    async def _fetch_cached(
        self,
        query: str,
        params: Optional[tuple] = None,
        ttl: int = 300
    ) -> List[Dict[str, Any]]:
        """Execute query with cache."""
        if not self._pool:
            raise RuntimeError("DataService not initialized")
        
        return await self._cache.get_or_fetch(
            query=query,
            params=params,
            fetch_func=lambda: self._pool.fetchall(query, params),
            ttl=ttl
        )
    
    # ========================================================================
    # Dashboard
    # ========================================================================
    
    async def get_dashboard(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Return 5-dimension dashboard data in parallel.
        
        Returns:
            dict with keys: daily_trend, top_actors, geo_distribution, event_types, summary_stats
        """
        start_time = time.time()
        
        queries = [
            ("daily_trend", f"""
                SELECT SQLDATE, COUNT(*) as event_count,
                       AVG(GoldsteinScale) as goldstein,
                       SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                GROUP BY SQLDATE ORDER BY SQLDATE
            """, (start_date, end_date)),
            
            ("top_actors", f"""
                SELECT Actor1Name as actor, COUNT(*) as event_count
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s AND Actor1Name IS NOT NULL
                GROUP BY Actor1Name ORDER BY event_count DESC LIMIT 10
            """, (start_date, end_date)),
            
            ("geo_distribution", f"""
                SELECT ActionGeo_CountryCode as country_code, COUNT(*) as event_count
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                  AND ActionGeo_CountryCode IS NOT NULL
                GROUP BY ActionGeo_CountryCode ORDER BY event_count DESC LIMIT 10
            """, (start_date, end_date)),
            
            ("event_types", f"""
                SELECT 
                    CASE 
                        WHEN EventRootCode BETWEEN 1 AND 9 THEN 'Public Statement'
                        WHEN EventRootCode BETWEEN 10 AND 19 THEN 'Yield'
                        WHEN EventRootCode BETWEEN 20 AND 29 THEN 'Investigate'
                        WHEN EventRootCode BETWEEN 30 AND 39 THEN 'Demand'
                        WHEN EventRootCode BETWEEN 40 AND 49 THEN 'Disapprove'
                        WHEN EventRootCode BETWEEN 50 AND 59 THEN 'Reject'
                        WHEN EventRootCode BETWEEN 60 AND 69 THEN 'Threaten'
                        WHEN EventRootCode BETWEEN 70 AND 79 THEN 'Protest'
                        ELSE 'Other'
                    END as event_type,
                    COUNT(*) as event_count
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                GROUP BY event_type ORDER BY event_count DESC
            """, (start_date, end_date)),
            
            ("summary_stats", f"""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT Actor1Name) as unique_actors,
                    AVG(GoldsteinScale) as avg_goldstein,
                    AVG(AvgTone) as avg_tone,
                    SUM(NumArticles) as total_articles
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
            """, (start_date, end_date)),
        ]
        
        # Execute in parallel
        results = await asyncio.gather(*[
            self._execute_named(name, query, params)
            for name, query, params in queries
        ], return_exceptions=True)
        
        dashboard = {}
        for (name, _, _), result in zip(queries, results):
            if isinstance(result, Exception):
                dashboard[name] = {"error": str(result), "data": []}
            else:
                dashboard[name] = result
        
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            **dashboard,
            "_meta": {"elapsed_ms": elapsed_ms, "start_date": start_date, "end_date": end_date}
        }
    
    async def _execute_named(
        self,
        name: str,
        query: str,
        params: tuple
    ) -> Dict[str, Any]:
        """Execute a single named query with timing."""
        start = time.time()
        rows = await self._fetch_cached(query, params, ttl=300)
        elapsed_ms = round((time.time() - start) * 1000, 2)
        return {
            "data": rows,
            "count": len(rows),
            "elapsed_ms": elapsed_ms
        }
    
    # ========================================================================
    # Time Series
    # ========================================================================
    
    async def get_time_series(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        """
        Advanced time series analysis with DB-side aggregation.
        
        Args:
            granularity: "day", "week", or "month"
        """
        if granularity == "week":
            period_expr = "STR_TO_DATE(CONCAT(YEARWEEK(SQLDATE), ' Sunday'), '%%X%%V %%W')"
        elif granularity == "month":
            period_expr = "DATE_FORMAT(SQLDATE, '%%Y-%%m-01')"
        else:  # day
            period_expr = "SQLDATE"
        
        query = f"""
        WITH stats AS (
            SELECT 
                {period_expr} as period,
                COUNT(*) as event_count,
                ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
                ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
                ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
                ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
                ROUND(AVG(AvgTone), 2) as avg_tone,
                ROUND(STDDEV(AvgTone), 2) as std_tone
            FROM {self.DEFAULT_TABLE}
            WHERE SQLDATE BETWEEN %s AND %s
            GROUP BY {period_expr}
        ),
        actors AS (
            SELECT 
                {period_expr} as period,
                JSON_ARRAYAGG(JSON_OBJECT('actor', Actor1Name, 'count', cnt)) as top_actors_json
            FROM (
                SELECT {period_expr}, Actor1Name, COUNT(*) as cnt,
                       ROW_NUMBER() OVER (PARTITION BY {period_expr} ORDER BY COUNT(*) DESC) as rn
                FROM {self.DEFAULT_TABLE}
                WHERE SQLDATE BETWEEN %s AND %s
                GROUP BY {period_expr}, Actor1Name
            ) ranked
            WHERE rn <= 3
            GROUP BY {period_expr}
        )
        SELECT s.*, a.top_actors_json
        FROM stats s
        LEFT JOIN actors a ON s.period = a.period
        ORDER BY s.period
        """
        
        return await self._fetch_cached(
            query, (start_date, end_date, start_date, end_date), ttl=1800
        )
    
    # ========================================================================
    # Geo Heatmap
    # ========================================================================
    
    async def get_geo_heatmap(
        self,
        start_date: str,
        end_date: str,
        precision: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Geo heatmap data with grid aggregation.
        
        Args:
            precision: Decimal places for lat/lng rounding (1-4)
        """
        precision = max(1, min(4, int(precision)))
        
        query = f"""
        SELECT 
            ROUND(ActionGeo_Lat, {precision}) as lat,
            ROUND(ActionGeo_Long, {precision}) as lng,
            COUNT(*) as intensity,
            AVG(GoldsteinScale) as avg_conflict,
            ANY_VALUE(ActionGeo_FullName) as sample_location
        FROM {self.DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND ActionGeo_Lat IS NOT NULL 
          AND ActionGeo_Long IS NOT NULL
        GROUP BY ROUND(ActionGeo_Lat, {precision}), ROUND(ActionGeo_Long, {precision})
        HAVING intensity >= 5
        ORDER BY intensity DESC
        LIMIT 1000
        """
        
        return await self._fetch_cached(query, (start_date, end_date), ttl=600)
    
    # ========================================================================
    # Event Search
    # ========================================================================
    
    async def search_events(
        self,
        query_text: str,
        time_hint: Optional[str] = None,
        location_hint: Optional[str] = None,
        event_type: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Structured event search with optional filters.
        """
        # Default date range: last 30 days if no hint
        if time_hint:
            date_start, date_end = self._parse_time_hint(time_hint)
        else:
            end = datetime.now().date()
            start = end - timedelta(days=30)
            date_start = start.strftime("%Y-%m-%d")
            date_end = end.strftime("%Y-%m-%d")
        
        sql = f"""
        SELECT 
            e.GlobalEventID, e.SQLDATE, e.Actor1Name, e.Actor2Name,
            e.EventCode, e.GoldsteinScale, e.AvgTone, e.NumArticles,
            e.ActionGeo_FullName, e.ActionGeo_CountryCode,
            e.ActionGeo_Lat, e.ActionGeo_Long,
            f.fingerprint, f.headline, f.summary, f.event_type_label, f.severity_score
        FROM {self.DEFAULT_TABLE} e
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        WHERE e.SQLDATE BETWEEN %s AND %s
        """
        params = [date_start, date_end]
        
        if location_hint:
            sql += " AND (e.ActionGeo_FullName LIKE %s OR e.ActionGeo_CountryCode = %s)"
            params.extend([f"%{location_hint}%", location_hint.upper()[:3]])
        
        if event_type and event_type != "any":
            type_conditions = {
                "conflict": "e.GoldsteinScale < -5",
                "cooperation": "e.GoldsteinScale > 5",
                "protest": "e.EventRootCode = '14'",
            }
            if event_type in type_conditions:
                sql += f" AND {type_conditions[event_type]}"
        
        sql += """
        ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT %s
        """
        params.append(min(max_results, 50))
        
        return await self._fetch_cached(sql, tuple(params), ttl=120)
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    @staticmethod
    def _parse_time_hint(time_hint: str) -> tuple[str, str]:
        """Parse time hint into date range."""
        today = datetime.now().date()
        
        if time_hint in ("today",):
            return (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        if time_hint in ("yesterday",):
            y = today - timedelta(days=1)
            return (y.strftime("%Y-%m-%d"), y.strftime("%Y-%m-%d"))
        if time_hint in ("this_week",):
            start = today - timedelta(days=today.weekday())
            return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        if time_hint in ("this_month",):
            start = today.replace(day=1)
            return (start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        
        # YYYY-MM
        if re.match(r'^\d{4}-\d{2}$', time_hint):
            y, m = int(time_hint[:4]), int(time_hint[5:7])
            from calendar import monthrange
            last_day = monthrange(y, m)[1]
            return (f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last_day}")
        
        # YYYY
        if re.match(r'^\d{4}$', time_hint):
            return (f"{time_hint}-01-01", f"{time_hint}-12-31")
        
        # Default fallback
        end = today
        start = end - timedelta(days=30)
        return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return self._cache.get_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        if not self._pool:
            return {"status": "unhealthy", "error": "Pool not initialized"}
        return await self._pool.health_check()


# Singleton instance
data_service = DataService()
