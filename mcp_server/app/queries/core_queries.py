"""
Core Queries — Shared SQL layer for MCP tools and FastAPI DataService.

All data-fetching logic lives here. Callers (core_tools_v2, DataService) handle
formatting only (markdown for LLM, JSON for Dashboard).
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .query_utils import parse_time_hint, parse_region_input, sanitize_text

DEFAULT_TABLE = "events_table"


# ============================================================================
# Dashboard (parallel 5-query)
# ============================================================================

async def query_dashboard(pool, start_date: str, end_date: str) -> Dict[str, Any]:
    """Return raw dashboard data: daily_trend, top_actors, geo_distribution, event_types, summary_stats."""
    # firsttryuseprecomputetabledaily_summary
    ds_rows = await pool.fetchall(
        "SELECT CAST(date AS CHAR) as date, total_events, conflict_events, "
        "avg_goldstein, avg_tone, top_actors, top_locations, event_type_distribution "
        "FROM daily_summary WHERE date BETWEEN %s AND %s ORDER BY date",
        (start_date, end_date)
    )
    if ds_rows and len(ds_rows) >= 10:
        import json
        daily_trend = []
        all_actors = {}
        all_countries = {}
        all_event_types = {}
        total_events = 0
        total_articles = 0
        goldstein_sum = 0
        tone_sum = 0
        unique_actors_set = set()
        for r in ds_rows:
            daily_trend.append({
                'SQLDATE': r['date'],
                'cnt': r['total_events'],
                'goldstein': r['avg_goldstein'],
                'conflict': r['conflict_events'],
            })
            total_events += r['total_events']
            goldstein_sum += (r['avg_goldstein'] or 0) * r['total_events']
            tone_sum += (r['avg_tone'] or 0) * r['total_events']
            # mergeactors
            for a in json.loads(r['top_actors'] or '[]'):
                all_actors[a['name']] = all_actors.get(a['name'], 0) + a['count']
                unique_actors_set.add(a['name'])
            # mergecountries
            for loc in json.loads(r['top_locations'] or '[]'):
                all_countries[loc['name']] = all_countries.get(loc['name'], 0) + loc['count']
            # mergeeventtypes
            for et, ec in json.loads(r['event_type_distribution'] or '{}').items():
                all_event_types[et] = all_event_types.get(et, 0) + ec
        top_actors = sorted([{'actor': k, 'event_count': v} for k, v in all_actors.items()], key=lambda x: x['event_count'], reverse=True)[:10]
        geo_distribution = sorted([{'country_code': k, 'event_count': v} for k, v in all_countries.items()], key=lambda x: x['event_count'], reverse=True)[:10]
        event_types = sorted([{'event_type': k, 'event_count': v} for k, v in all_event_types.items()], key=lambda x: x['event_count'], reverse=True)
        # extraquerytotal_articles（daily_summaryNo.storethisfield）
        articles_result = await pool.fetchone(
            f"SELECT SUM(NumArticles) as total_articles FROM {DEFAULT_TABLE} WHERE SQLDATE BETWEEN %s AND %s",
            (start_date, end_date)
        )
        total_articles = articles_result['total_articles'] if articles_result else None
        return {
            'daily_trend': {'data': daily_trend},
            'top_actors': {'data': top_actors},
            'geo_distribution': {'data': geo_distribution},
            'event_types': {'data': event_types},
            'summary_stats': {'data': [{
                'total_events': total_events,
                'unique_actors': len(unique_actors_set),
                'avg_goldstein': round(goldstein_sum / total_events, 2) if total_events else 0,
                'avg_tone': round(tone_sum / total_events, 2) if total_events else 0,
                'total_articles': total_articles,
            }]}
        }

    # fallbackto originalparallelquery
    queries = [
        ("daily_trend", f"""
            SELECT CAST(SQLDATE AS CHAR) as SQLDATE, COUNT(*) as cnt,
                   AVG(GoldsteinScale) as goldstein,
                   SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict
            FROM {DEFAULT_TABLE}
            WHERE SQLDATE BETWEEN %s AND %s
            GROUP BY SQLDATE ORDER BY SQLDATE
        """, (start_date, end_date)),

        ("top_actors", f"""
            SELECT Actor1Name as actor, COUNT(*) as event_count
            FROM {DEFAULT_TABLE}
            WHERE SQLDATE BETWEEN %s AND %s AND Actor1Name IS NOT NULL
            GROUP BY Actor1Name ORDER BY event_count DESC LIMIT 10
        """, (start_date, end_date)),

        ("geo_distribution", f"""
            SELECT ActionGeo_CountryCode as country_code, COUNT(*) as event_count
            FROM {DEFAULT_TABLE}
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
            FROM {DEFAULT_TABLE}
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
            FROM {DEFAULT_TABLE}
            WHERE SQLDATE BETWEEN %s AND %s
        """, (start_date, end_date)),
    ]

    async def _run_one(name: str, sql: str, params: tuple):
        import time
        t0 = time.time()
        rows = await pool.fetchall(sql, params)
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        return name, {"data": rows, "count": len(rows), "elapsed_ms": elapsed_ms}

    results = await asyncio.gather(*[_run_one(n, s, p) for n, s, p in queries])
    return {name: data for name, data in results}


# ============================================================================
# Time Series
# ============================================================================

async def query_time_series(pool, start_date: str, end_date: str, granularity: str = "day") -> List[Dict[str, Any]]:
    # firsttryuseprecomputetabledaily_summary（ifETLalreadyran）
    ds_rows = await pool.fetchall(
        "SELECT CAST(date AS CHAR) as period, total_events as event_count, conflict_events, cooperation_events, "
        "avg_goldstein, avg_tone FROM daily_summary WHERE date BETWEEN %s AND %s ORDER BY date",
        (start_date, end_date)
    )
    if ds_rows and len(ds_rows) >= 20:
        result = []
        for r in ds_rows:
            total = r['event_count'] or 1
            result.append({
                'period': r['period'],
                'event_count': r['event_count'],
                'conflict_pct': round(r['conflict_events'] * 100.0 / total, 2) if r['conflict_events'] else 0,
                'cooperation_pct': round(r['cooperation_events'] * 100.0 / total, 2) if r['cooperation_events'] else 0,
                'avg_goldstein': r['avg_goldstein'],
                'std_goldstein': None,
                'avg_tone': r['avg_tone'],
                'std_tone': None,
                'top_actors_json': None,
            })
        return result

    # fallbackto originalSQL（forweek/monthorlackdaily_summary）
    if granularity == "week":
        period_expr = "STR_TO_DATE(CONCAT(YEARWEEK(SQLDATE), ' Sunday'), '%%X%%V %%W')"
    elif granularity == "month":
        period_expr = "DATE_FORMAT(SQLDATE, '%%Y-%%m-01')"
    else:
        period_expr = "SQLDATE"

    sql = f"""
    SELECT
        CAST({period_expr} AS CHAR) as period,
        COUNT(*) as event_count,
        ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
        ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
        ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
        ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
        ROUND(AVG(AvgTone), 2) as avg_tone,
        ROUND(STDDEV(AvgTone), 2) as std_tone,
        NULL as top_actors_json
    FROM {DEFAULT_TABLE}
    WHERE SQLDATE BETWEEN %s AND %s
    GROUP BY {period_expr}
    ORDER BY {period_expr}
    """
    return await pool.fetchall(sql, (start_date, end_date))


# ============================================================================
# Geo Heatmap
# ============================================================================

async def query_geo_heatmap(pool, start_date: str, end_date: str, precision: int = 2) -> List[Dict[str, Any]]:
    precision = max(1, min(4, int(precision)))
    # firsttryuseprecomputetablegeo_heatmap_grid
    gh_rows = await pool.fetchall(
        f"SELECT ROUND(lat_grid, {precision}) as lat, ROUND(lng_grid, {precision}) as lng, "
        f"SUM(event_count) as intensity, AVG(avg_goldstein) as avg_conflict "
        f"FROM geo_heatmap_grid WHERE date BETWEEN %s AND %s "
        f"GROUP BY ROUND(lat_grid, {precision}), ROUND(lng_grid, {precision}) "
        f"HAVING intensity >= 5 ORDER BY intensity DESC LIMIT 1000",
        (start_date, end_date)
    )
    if gh_rows and len(gh_rows) >= 10:
        return [{**r, 'sample_location': None} for r in gh_rows]

    # fallbackto originalSQL
    sql = f"""
    SELECT
        ROUND(ActionGeo_Lat, {precision}) as lat,
        ROUND(ActionGeo_Long, {precision}) as lng,
        COUNT(*) as intensity,
        AVG(GoldsteinScale) as avg_conflict,
        ANY_VALUE(ActionGeo_FullName) as sample_location
    FROM {DEFAULT_TABLE}
    WHERE SQLDATE BETWEEN %s AND %s
      AND ActionGeo_Lat IS NOT NULL
      AND ActionGeo_Long IS NOT NULL
    GROUP BY ROUND(ActionGeo_Lat, {precision}), ROUND(ActionGeo_Long, {precision})
    HAVING intensity >= 5
    ORDER BY intensity DESC
    LIMIT 1000
    """
    return await pool.fetchall(sql, (start_date, end_date))


# ============================================================================
# Event Search
# ============================================================================

async def query_search_events(
    pool,
    query_text: str,
    time_hint: Optional[str] = None,
    location_hint: Optional[str] = None,
    event_type: Optional[str] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    if time_hint:
        date_start, date_end = parse_time_hint(time_hint)
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
    FROM {DEFAULT_TABLE} e
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

    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Event Detail
# ============================================================================

async def query_event_detail(pool, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Return raw event detail data or None if not found."""
    if fingerprint.startswith('EVT-'):
        parts = fingerprint.split('-')
        if len(parts) >= 4:
            try:
                gid = int(parts[-1])
            except ValueError:
                return None
        else:
            return None

        row = await pool.fetchone(f"SELECT * FROM {DEFAULT_TABLE} WHERE GlobalEventID = %s", (gid,))
        if row:
            return dict(row)
        return None
    else:
        row = await pool.fetchone("""
            SELECT global_event_id, fingerprint, headline, summary,
                   key_actors, event_type_label, severity_score,
                   location_name, location_country
            FROM event_fingerprints
            WHERE fingerprint = %s
        """, (fingerprint,))
        if not row:
            return None

        gid = int(row[0]) if row[0] else None
        if not gid:
            return None

        event_row = await pool.fetchone(f"SELECT * FROM {DEFAULT_TABLE} WHERE GlobalEventID = %s", (gid,))
        return {
            "fingerprint": row[1],
            "headline": row[2],
            "summary": row[3],
            "key_actors": row[4],
            "event_type_label": row[5],
            "severity_score": row[6],
            "location_name": row[7],
            "location_country": row[8],
            "event_data": dict(event_row) if event_row else {},
        }


# ============================================================================
# Regional Overview
# ============================================================================

async def query_regional_overview(
    pool, region: str, time_range: str = "week"
) -> Dict[str, Any]:
    end_date = datetime.now().date()
    days_map = {'day': 1, 'week': 7, 'month': 30, 'quarter': 90, 'year': 365}
    start_date = end_date - timedelta(days=days_map.get(time_range, 7))

    # Try pre-computed stats first
    stats_rows = await pool.fetchall("""
        SELECT * FROM region_daily_stats
        WHERE region_code = %s AND date BETWEEN %s AND %s
        ORDER BY date DESC LIMIT 7
    """, (region.upper(), start_date, end_date))

    if stats_rows:
        return {"source": "precomputed", "rows": [dict(r) for r in stats_rows], "region": region, "start": str(start_date), "end": str(end_date)}

    # Fallback: real-time query
    row = await pool.fetchone(f"""
        SELECT
            COUNT(*) as total,
            AVG(GoldsteinScale) as avg_goldstein,
            AVG(AvgTone) as avg_tone,
            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflicts,
            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
    """, (start_date, end_date, region.upper(), f'%{region}%'))

    hot_events = await pool.fetchall(f"""
        SELECT Actor1Name, Actor2Name, EventCode, GoldsteinScale,
               NumArticles, ActionGeo_FullName, SQLDATE
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
        LIMIT 5
    """, (start_date, end_date, region.upper(), f'%{region}%'))

    return {
        "source": "realtime",
        "summary": dict(row) if row else {},
        "hot_events": [dict(r) for r in hot_events],
        "region": region,
        "start": str(start_date),
        "end": str(end_date),
    }


# ============================================================================
# Hot Events
# ============================================================================

async def query_hot_events(
    pool, query_date: Optional[str] = None, region_filter: Optional[str] = None, top_n: int = 5
) -> List[Dict[str, Any]]:
    query_date = query_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    # Try pre-computed
    result = await pool.fetchone("""
        SELECT hot_event_fingerprints, top_actors, top_locations
        FROM daily_summary
        WHERE date = %s
    """, (query_date,))

    if result and result[0]:
        import json
        hot_fingerprints = json.loads(result[0]) if isinstance(result[0], str) else result[0]
        events = []
        for fp in hot_fingerprints[:top_n]:
            row = await pool.fetchone("""
                SELECT f.fingerprint, f.headline, f.summary, f.severity_score,
                       f.location_name, e.SQLDATE, e.GoldsteinScale, e.NumArticles,
                       e.GlobalEventID, 'standard' as fp_type
                FROM event_fingerprints f
                JOIN events_table e ON f.global_event_id = e.GlobalEventID
                WHERE f.fingerprint = %s
            """, (fp,))
            if row:
                events.append(dict(row))
        return events

    # Fallback: real-time query
    region_condition = ""
    params = [query_date]
    if region_filter:
        region_condition = "AND (e.ActionGeo_CountryCode = %s OR e.ActionGeo_FullName LIKE %s)"
        params.extend([region_filter.upper(), f'%{region_filter}%'])

    sql = f"""
        SELECT
            COALESCE(f.fingerprint, CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR))) as fingerprint,
            COALESCE(f.headline, CONCAT(COALESCE(NULLIF(e.Actor1Name, ''), '一方'), ' vs ', COALESCE(NULLIF(e.Actor2Name, ''), '另一方'))) as headline,
            COALESCE(f.summary, e.ActionGeo_FullName) as summary,
            COALESCE(f.severity_score, ABS(e.GoldsteinScale)) as severity_score,
            COALESCE(f.location_name, e.ActionGeo_FullName) as location_name,
            CAST(e.SQLDATE AS CHAR) as date,
            e.GoldsteinScale,
            e.NumArticles,
            e.GlobalEventID,
            CASE WHEN f.fingerprint IS NOT NULL THEN 'standard' ELSE 'temp' END as fp_type
        FROM {DEFAULT_TABLE} e
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        WHERE e.SQLDATE = %s {region_condition}
        ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT %s
    """
    params.append(top_n)
    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Top Events
# ============================================================================

async def query_top_events(
    pool, start_date: str, end_date: str,
    region_filter: Optional[str] = None, event_type: Optional[str] = None, top_n: int = 10
) -> List[Dict[str, Any]]:
    conditions = ["SQLDATE BETWEEN %s AND %s"]
    params = [start_date, end_date]

    if region_filter:
        parsed = parse_region_input(region_filter)
        region_conds = []
        for term in parsed:
            region_conds.append("ActionGeo_FullName LIKE %s")
            params.append(f'{term}%')
            region_conds.append("ActionGeo_FullName LIKE %s")
            params.append(f'%, {term}%')
            if len(term) <= 3 and term.isalpha():
                region_conds.append("ActionGeo_CountryCode = %s")
                params.append(term.upper()[:3])
        if region_conds:
            conditions.append(f"({' OR '.join(region_conds)})")

    if event_type == 'conflict':
        conditions.append("GoldsteinScale < -5")
    elif event_type == 'cooperation':
        conditions.append("GoldsteinScale > 5")
    elif event_type == 'protest':
        conditions.append("EventRootCode = '14'")

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            GlobalEventID, SQLDATE, Actor1Name, Actor2Name,
            ActionGeo_FullName, ActionGeo_CountryCode,
            EventRootCode, GoldsteinScale, NumArticles,
            NumSources, AvgTone, SOURCEURL
        FROM {DEFAULT_TABLE}
        WHERE {where_clause}
        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
        LIMIT %s
    """
    params.append(top_n)
    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Daily Brief
# ============================================================================

async def query_daily_brief(pool, query_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    query_date = query_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    brief = await pool.fetchone("SELECT * FROM daily_summary WHERE date = %s", (query_date,))
    if brief:
        return dict(brief)

    row = await pool.fetchone(f"""
        SELECT
            COUNT(*) as total_events,
            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation_events,
            AVG(GoldsteinScale) as avg_goldstein,
            AVG(AvgTone) as avg_tone
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE = %s
    """, (query_date,))

    return dict(row) if row else None


# ============================================================================
# Stream Events
# ============================================================================

async def query_stream_events(
    pool, actor_name: str,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    max_results: int = 100
):
    """Generator-friendly streaming query."""
    from ..database.streaming import StreamingQuery

    streaming = StreamingQuery(pool, chunk_size=50)
    date_filter = ""
    params = [f"%{actor_name}%", f"%{actor_name}%"]

    if start_date and end_date:
        date_filter = "AND SQLDATE BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    params.append(max_results)

    sql = f"""
        SELECT CAST(SQLDATE AS CHAR) as SQLDATE, Actor1Name, Actor2Name, EventCode,
               GoldsteinScale, AvgTone, ActionGeo_FullName,
               ActionGeo_Lat, ActionGeo_Long
        FROM {DEFAULT_TABLE}
        WHERE (Actor1Name LIKE %s OR Actor2Name LIKE %s)
        {date_filter}
        ORDER BY SQLDATE DESC
        LIMIT %s
    """

    async for row in streaming.stream(sql, tuple(params)):
        yield dict(row)
