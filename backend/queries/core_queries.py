"""
Core Queries — Shared SQL layer for FastAPI DataService and internal services.

All data-fetching logic lives here. Callers handle formatting only.
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .query_utils import parse_time_hint, parse_region_input, sanitize_text


# ============================================================================
# Location condition builder (uses parse_region_input for smart matching)
# ============================================================================

def _build_smart_location_condition(location_hint: Optional[str], location_exact: Optional[str]) -> tuple[str, list]:
    """Build location SQL using parse_region_input for alias support and prefix indexing."""
    if location_exact:
        if len(location_exact) <= 3 and location_exact.isalpha():
            return " AND ActionGeo_CountryCode = %s", [location_exact.upper()[:3]]
        return " AND ActionGeo_FullName = %s", [location_exact]
    
    if not location_hint:
        return "", []
    
    terms = parse_region_input(location_hint)
    conditions = []
    params = []
    
    for term in terms:
        if not term or len(term) < 2:
            continue
        # Prefix match on full location name (index-friendly)
        conditions.append("ActionGeo_FullName LIKE %s")
        params.append(f"{term}%")
        # Match city/state within comma-separated location
        conditions.append("ActionGeo_FullName LIKE %s")
        params.append(f"%, {term}%")
        # Country code exact match for short alpha terms
        if len(term) <= 3 and term.isalpha():
            conditions.append("ActionGeo_CountryCode = %s")
            params.append(term.upper()[:3])
    
    if not conditions:
        return "", []
    
    return f" AND ({' OR '.join(conditions)})", params


def _build_actor_condition(actor: Optional[str], actor_exact: Optional[str]) -> tuple[str, list]:
    """Build actor SQL condition. Exact match uses index; fuzzy uses LIKE."""
    if actor_exact:
        return " AND (Actor1Name = %s OR Actor2Name = %s)", [actor_exact, actor_exact]
    if actor:
        return " AND (Actor1Name LIKE %s OR Actor2Name LIKE %s)", [f"%{actor}%", f"%{actor}%"]
    return "", []


async def query_suggest_actors(pool, prefix: str, limit: int = 10) -> List[str]:
    """Return actor names matching prefix using indexed LIKE prefix search.
    Results ordered by frequency (hot actors first)."""
    prefix_up = prefix.upper()
    rows = await pool.fetchall(
        f"""SELECT Actor1Name as name, COUNT(*) as cnt FROM {DEFAULT_TABLE}
            WHERE Actor1Name LIKE %s
            GROUP BY name
            ORDER BY cnt DESC
            LIMIT %s""",
        (f"{prefix_up}%", limit)
    )
    return [r['name'] for r in rows if r['name']]


# State abbreviation / name -> canonical location mapping for fast suggestion
_us_state_suggestions: dict[str, str] = {
    # Abbreviations
    'AL': 'Alabama, United States', 'AK': 'Alaska, United States', 'AZ': 'Arizona, United States',
    'AR': 'Arkansas, United States', 'CA': 'California, United States', 'CO': 'Colorado, United States',
    'CT': 'Connecticut, United States', 'DE': 'Delaware, United States', 'FL': 'Florida, United States',
    'GA': 'Georgia, United States', 'HI': 'Hawaii, United States', 'ID': 'Idaho, United States',
    'IL': 'Illinois, United States', 'IN': 'Indiana, United States', 'IA': 'Iowa, United States',
    'KS': 'Kansas, United States', 'KY': 'Kentucky, United States', 'LA': 'Louisiana, United States',
    'ME': 'Maine, United States', 'MD': 'Maryland, United States', 'MA': 'Massachusetts, United States',
    'MI': 'Michigan, United States', 'MN': 'Minnesota, United States', 'MS': 'Mississippi, United States',
    'MO': 'Missouri, United States', 'MT': 'Montana, United States', 'NE': 'Nebraska, United States',
    'NV': 'Nevada, United States', 'NH': 'New Hampshire, United States', 'NJ': 'New Jersey, United States',
    'NM': 'New Mexico, United States', 'NY': 'New York, United States', 'NC': 'North Carolina, United States',
    'ND': 'North Dakota, United States', 'OH': 'Ohio, United States', 'OK': 'Oklahoma, United States',
    'OR': 'Oregon, United States', 'PA': 'Pennsylvania, United States', 'RI': 'Rhode Island, United States',
    'SC': 'South Carolina, United States', 'SD': 'South Dakota, United States', 'TN': 'Tennessee, United States',
    'TX': 'Texas, United States', 'UT': 'Utah, United States', 'VT': 'Vermont, United States',
    'VA': 'Virginia, United States', 'WA': 'Washington, United States', 'WV': 'West Virginia, United States',
    'WI': 'Wisconsin, United States', 'WY': 'Wyoming, United States', 'DC': 'Washington, District of Columbia, United States',
}

# Build reverse lookup by state name (lowercase) -> canonical location
_us_state_by_name: dict[str, str] = {}
for _abbr, _loc in _us_state_suggestions.items():
    # Extract state name from "State, United States"
    _state_name = _loc.split(',')[0].strip().lower()
    _us_state_by_name[_state_name] = _loc
    # Also add abbreviation
    _us_state_by_name[_abbr.lower()] = _loc

# Add multi-word states
_us_state_by_name.update({
    'new york': 'New York, United States',
    'north carolina': 'North Carolina, United States',
    'south carolina': 'South Carolina, United States',
    'north dakota': 'North Dakota, United States',
    'south dakota': 'South Dakota, United States',
    'west virginia': 'West Virginia, United States',
    'new hampshire': 'New Hampshire, United States',
    'new jersey': 'New Jersey, United States',
    'new mexico': 'New Mexico, United States',
    'rhode island': 'Rhode Island, United States',
    'district of columbia': 'Washington, District of Columbia, United States',
})


async def query_suggest_locations(pool, prefix: str, limit: int = 10) -> List[str]:
    """Return location names matching prefix or alias using indexed LIKE prefix search.
    
    Collects results from all parsed terms (e.g. TX -> Texas) so abbreviations
    show full-name matches in suggestions. State full names are prioritized first.
    """
    terms = parse_region_input(prefix)
    state_matches: list[str] = []
    other_results: set[str] = set()
    
    # Fast-path: state abbreviations OR full state names -> canonical location
    for term in terms:
        term_up = term.upper()
        if term_up in _us_state_suggestions:
            state_name = _us_state_suggestions[term_up]
            if state_name not in state_matches:
                state_matches.append(state_name)
        # Also check by full state name (e.g. "Texas" -> "Texas, United States")
        term_lower = term.strip().lower()
        if term_lower in _us_state_by_name:
            state_name = _us_state_by_name[term_lower]
            if state_name not in state_matches:
                state_matches.append(state_name)
    
    for term in terms:
        if not term or len(term) < 2:
            continue
        rows = await pool.fetchall(
            f"""SELECT DISTINCT ActionGeo_FullName as name FROM {DEFAULT_TABLE}
                WHERE ActionGeo_FullName LIKE %s
                LIMIT %s""",
            (f"{term}%", limit)
        )
        for r in rows:
            name = r['name']
            if name and name not in state_matches:
                other_results.add(name)
    
    # State names first, then others sorted alphabetically
    combined = state_matches + sorted(other_results)
    return combined[:limit]


# ============================================================================
# Optimized search SQL builder
# ============================================================================

def _build_optimized_search_sql(
    start_date: str,
    end_date: str,
    location_hint: Optional[str],
    location_exact: Optional[str],
    event_type: Optional[str],
    actor: Optional[str],
    actor_exact: Optional[str],
    max_results: int,
) -> tuple[str, list]:
    """Build optimized search SQL. Uses subquery + FORCE INDEX for exact matches."""
    
    loc_cond, loc_params = _build_smart_location_condition(location_hint, location_exact)
    act_cond, act_params = _build_actor_condition(actor, actor_exact)
    
    # Determine best index hint for the inner query
    force_index = ""
    if actor_exact and not location_exact:
        force_index = "FORCE INDEX (idx_date_actor)"
    elif location_exact and not actor_exact:
        force_index = "FORCE INDEX (idx_date_geo)"
    
    # Event type condition
    type_sql = ""
    if event_type and event_type != "any":
        type_conditions = {
            "conflict": "GoldsteinScale < -5",
            "cooperation": "GoldsteinScale > 5",
            "protest": "EventRootCode = '14'",
        }
        if event_type in type_conditions:
            type_sql = f" AND {type_conditions[event_type]}"
    
    # Build inner WHERE for subquery
    inner_where = f"SQLDATE BETWEEN %s AND %s"
    inner_params = [start_date, end_date]
    
    if actor_exact:
        inner_where += " AND Actor1Name = %s"
        inner_params.append(actor_exact)
    elif actor:
        inner_where += " AND (Actor1Name LIKE %s OR Actor2Name LIKE %s)"
        inner_params.extend([f"%{actor}%", f"%{actor}%"])
    
    if location_exact:
        if len(location_exact) <= 3 and location_exact.isalpha():
            inner_where += " AND ActionGeo_CountryCode = %s"
            inner_params.append(location_exact.upper()[:3])
        else:
            inner_where += " AND ActionGeo_FullName = %s"
            inner_params.append(location_exact)
    elif location_hint:
        # For inner query with hint, use simplified location condition
        hint_terms = parse_region_input(location_hint)
        loc_conds = []
        for term in hint_terms:
            if not term or len(term) < 2:
                continue
            loc_conds.append("ActionGeo_FullName LIKE %s")
            inner_params.append(f"{term}%")
            if len(term) <= 3 and term.isalpha():
                loc_conds.append("ActionGeo_CountryCode = %s")
                inner_params.append(term.upper()[:3])
        if loc_conds:
            inner_where += f" AND ({' OR '.join(loc_conds)})"
    
    inner_where += type_sql
    
    # Use subquery pattern for exact matches (much faster), regular query for fuzzy
    if actor_exact or location_exact:
        sql = f"""
        SELECT
            e.GlobalEventID, CAST(e.SQLDATE AS CHAR) as SQLDATE,
            e.Actor1Name, e.Actor2Name,
            e.EventCode, e.GoldsteinScale, e.AvgTone, e.NumArticles,
            e.ActionGeo_FullName, e.ActionGeo_CountryCode,
            e.ActionGeo_Lat, e.ActionGeo_Long,
            f.fingerprint, f.headline, f.summary, f.event_type_label, f.severity_score
        FROM (
            SELECT GlobalEventID FROM {DEFAULT_TABLE} {force_index}
            WHERE {inner_where}
            ORDER BY NumArticles DESC
            LIMIT %s
        ) ids
        JOIN {DEFAULT_TABLE} e ON e.GlobalEventID = ids.GlobalEventID
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        """
        params = inner_params + [max_results]
    else:
        # Fallback: regular query for fuzzy search (slower but flexible)
        sql = f"""
        SELECT
            e.GlobalEventID, CAST(e.SQLDATE AS CHAR) as SQLDATE,
            e.Actor1Name, e.Actor2Name,
            e.EventCode, e.GoldsteinScale, e.AvgTone, e.NumArticles,
            e.ActionGeo_FullName, e.ActionGeo_CountryCode,
            e.ActionGeo_Lat, e.ActionGeo_Long,
            f.fingerprint, f.headline, f.summary, f.event_type_label, f.severity_score
        FROM {DEFAULT_TABLE} e
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        WHERE e.SQLDATE BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        
        if location_hint:
            loc_sql, loc_p = _build_smart_location_condition(location_hint, None)
            sql += loc_sql.replace("ActionGeo", "e.ActionGeo")
            params.extend(loc_p)
        
        sql += type_sql.replace("GoldsteinScale", "e.GoldsteinScale").replace("EventRootCode", "e.EventRootCode")
        
        if actor:
            sql += " AND (e.Actor1Name LIKE %s OR e.Actor2Name LIKE %s)"
            params.extend([f"%{actor}%", f"%{actor}%"])
        
        sql += """
        ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT %s
        """
        params.append(max_results)
    
    return sql, params


async def query_search_events(
    pool,
    query_text: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    time_hint: Optional[str] = None,
    location_hint: Optional[str] = None,
    location_exact: Optional[str] = None,
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
    actor_exact: Optional[str] = None,
    max_results: int = 20,
) -> List[Dict[str, Any]]:
    if start_date and end_date:
        date_start, date_end = start_date, end_date
    elif time_hint:
        date_start, date_end = parse_time_hint(time_hint)
    else:
        end = datetime.now().date()
        start = end - timedelta(days=30)
        date_start = start.strftime("%Y-%m-%d")
        date_end = end.strftime("%Y-%m-%d")

    sql, params = _build_optimized_search_sql(
        date_start, date_end,
        location_hint, location_exact,
        event_type, actor, actor_exact,
        min(max_results, 50),
    )
    return await pool.fetchall(sql, tuple(params))


async def query_geo_events(
    pool,
    start_date: str,
    end_date: str,
    location_hint: Optional[str] = None,
    location_exact: Optional[str] = None,
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
    actor_exact: Optional[str] = None,
    max_results: int = 100,
) -> List[Dict[str, Any]]:
    """Return individual event points with coordinates for map display.
    
    NOTE: No JOIN with event_fingerprints for speed. Headline/summary not included.
    """
    loc_cond, loc_params = _build_smart_location_condition(location_hint, location_exact)
    act_cond, act_params = _build_actor_condition(actor, actor_exact)
    
    force_index = ""
    if actor_exact and not location_exact:
        force_index = "FORCE INDEX (idx_date_actor)"
    elif location_exact and not actor_exact:
        force_index = "FORCE INDEX (idx_date_geo)"
    
    type_sql = ""
    if event_type and event_type != "any":
        type_conditions = {
            "conflict": "GoldsteinScale < -5",
            "cooperation": "GoldsteinScale > 5",
            "protest": "EventRootCode = '14'",
        }
        if event_type in type_conditions:
            type_sql = f" AND {type_conditions[event_type]}"
    
    if actor_exact or location_exact:
        inner_where = f"SQLDATE BETWEEN %s AND %s"
        inner_params = [start_date, end_date]
        
        if actor_exact:
            inner_where += " AND Actor1Name = %s"
            inner_params.append(actor_exact)
        elif actor:
            inner_where += " AND (Actor1Name LIKE %s OR Actor2Name LIKE %s)"
            inner_params.extend([f"%{actor}%", f"%{actor}%"])
        
        if location_exact:
            if len(location_exact) <= 3 and location_exact.isalpha():
                inner_where += " AND ActionGeo_CountryCode = %s"
                inner_params.append(location_exact.upper()[:3])
            else:
                inner_where += " AND ActionGeo_FullName = %s"
                inner_params.append(location_exact)
        elif location_hint:
            hint_terms = parse_region_input(location_hint)
            loc_conds = []
            for term in hint_terms:
                if not term or len(term) < 2:
                    continue
                loc_conds.append("ActionGeo_FullName LIKE %s")
                inner_params.append(f"{term}%")
                if len(term) <= 3 and term.isalpha():
                    loc_conds.append("ActionGeo_CountryCode = %s")
                    inner_params.append(term.upper()[:3])
            if loc_conds:
                inner_where += f" AND ({' OR '.join(loc_conds)})"
        
        inner_where += type_sql
        
        sql = f"""
        SELECT
            e.GlobalEventID,
            CAST(e.SQLDATE AS CHAR) as SQLDATE,
            e.Actor1Name,
            e.Actor2Name,
            e.EventCode,
            e.GoldsteinScale,
            e.AvgTone,
            e.NumArticles,
            e.ActionGeo_FullName,
            e.ActionGeo_CountryCode,
            e.ActionGeo_Lat as lat,
            e.ActionGeo_Long as lng
        FROM (
            SELECT GlobalEventID FROM {DEFAULT_TABLE} {force_index}
            WHERE {inner_where}
              AND ActionGeo_Lat IS NOT NULL
              AND ActionGeo_Long IS NOT NULL
            ORDER BY NumArticles DESC
            LIMIT %s
        ) ids
        JOIN {DEFAULT_TABLE} e ON e.GlobalEventID = ids.GlobalEventID
        """
        params = inner_params + [min(max_results, 100)]
    else:
        sql = f"""
        SELECT
            e.GlobalEventID,
            CAST(e.SQLDATE AS CHAR) as SQLDATE,
            e.Actor1Name,
            e.Actor2Name,
            e.EventCode,
            e.GoldsteinScale,
            e.AvgTone,
            e.NumArticles,
            e.ActionGeo_FullName,
            e.ActionGeo_CountryCode,
            e.ActionGeo_Lat as lat,
            e.ActionGeo_Long as lng
        FROM {DEFAULT_TABLE} e
        WHERE e.SQLDATE BETWEEN %s AND %s
          AND e.ActionGeo_Lat IS NOT NULL
          AND e.ActionGeo_Long IS NOT NULL
        """
        params = [start_date, end_date]
        
        if location_hint:
            loc_sql, loc_p = _build_smart_location_condition(location_hint, None)
            sql += loc_sql.replace("ActionGeo", "e.ActionGeo")
            params.extend(loc_p)
        
        sql += type_sql.replace("GoldsteinScale", "e.GoldsteinScale").replace("EventRootCode", "e.EventRootCode")
        
        if actor:
            sql += " AND (e.Actor1Name LIKE %s OR e.Actor2Name LIKE %s)"
            params.extend([f"%{actor}%", f"%{actor}%"])
        
        sql += """
        ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT %s
        """
        params.append(min(max_results, 100))

    rows = await pool.fetchall(sql, tuple(params))
    result = []
    for r in rows:
        d = dict(r)
        d['lat'] = float(d['lat']) if d['lat'] is not None else None
        d['lng'] = float(d['lng']) if d['lng'] is not None else None
        result.append(d)
    return result

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

# ============================================================================
# Suggestion helpers
# ============================================================================

async def query_suggest_actors(pool, prefix: str, limit: int = 10) -> List[str]:
    """Return actor names matching prefix using indexed LIKE prefix search."""
    prefix_up = prefix.upper()
    rows = await pool.fetchall(
        f"""SELECT DISTINCT Actor1Name as name FROM {DEFAULT_TABLE}
            WHERE Actor1Name LIKE %s
            LIMIT %s""",
        (f"{prefix_up}%", limit)
    )
    return [r['name'] for r in rows if r['name']]



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
            result = dict(row)
            for k, v in list(result.items()):
                if isinstance(v, bytes):
                    result[k] = v.hex()
            return result
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

        gid = int(row['global_event_id']) if row['global_event_id'] else None
        if not gid:
            return None

        event_row = await pool.fetchone(f"SELECT * FROM {DEFAULT_TABLE} WHERE GlobalEventID = %s", (gid,))
        event_data = dict(event_row) if event_row else {}
        # Clean non-JSON-serializable values (e.g. MySQL POINT bytes)
        for k, v in list(event_data.items()):
            if isinstance(v, bytes):
                event_data[k] = v.hex()
        return {
            "fingerprint": row['fingerprint'],
            "headline": row['headline'],
            "summary": row['summary'],
            "key_actors": row['key_actors'],
            "event_type_label": row['event_type_label'],
            "severity_score": row['severity_score'],
            "location_name": row['location_name'],
            "location_country": row['location_country'],
            "event_data": event_data,
        }


# ============================================================================
# Regional Overview
# ============================================================================

async def query_regional_overview(
    pool, region: str, time_range: str = "week",
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> Dict[str, Any]:
    if start_date and end_date:
        start = start_date
        end = end_date
    else:
        end_dt = datetime.now().date()
        days_map = {'day': 1, 'week': 7, 'month': 30, 'quarter': 90, 'year': 365}
        start_dt = end_dt - timedelta(days=days_map.get(time_range, 7))
        start = start_dt.strftime('%Y-%m-%d')
        end = end_dt.strftime('%Y-%m-%d')

    # Try pre-computed stats first
    stats_rows = await pool.fetchall("""
        SELECT * FROM region_daily_stats
        WHERE region_code = %s AND date BETWEEN %s AND %s
        ORDER BY date DESC LIMIT 7
    """, (region.upper(), start, end))

    if stats_rows:
        return {"source": "precomputed", "rows": [dict(r) for r in stats_rows], "region": region, "start": start, "end": end}

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
    """, (start, end, region.upper(), f'%{region}%'))

    hot_events = await pool.fetchall(f"""
        SELECT Actor1Name, Actor2Name, EventCode, GoldsteinScale,
               NumArticles, ActionGeo_FullName, SQLDATE
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
        ORDER BY NumArticles DESC, ABS(GoldsteinScale) DESC
        LIMIT 5
    """, (start, end, region.upper(), f'%{region}%'))

    return {
        "source": "realtime",
        "summary": dict(row) if row else {},
        "hot_events": [dict(r) for r in hot_events],
        "region": region,
        "start": start,
        "end": end,
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

    if result and result['hot_event_fingerprints']:
        import json
        hot_fingerprints = json.loads(result['hot_event_fingerprints']) if isinstance(result['hot_event_fingerprints'], str) else result['hot_event_fingerprints']
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
        ORDER BY NumArticles DESC, ABS(GoldsteinScale) DESC
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


# ============================================================================# RAG / Vector Search (ChromaDB)
# ============================================================================

def get_chroma_db_path() -> str:
    """Get the ChromaDB persistent storage path."""
    # Navigate from backend/queries/ up to project root
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / 'chroma_db')


async def query_search_news_context(
    query: str,
    n_results: int = 5
) -> Dict[str, Any]:
    """
    Search news article content via ChromaDB vector semantic search.
    
    Args:
        query: Natural language search query
        n_results: Number of results to return (default 5, max 10)
    
    Returns:
        Dict with 'results' list and 'query' metadata
    """
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        
        db_path = get_chroma_db_path()
        if not os.path.exists(db_path):
            return {
                "error": "Vector database not found",
                "db_path": db_path,
                "message": "Please build the knowledge base first"
            }
        
        client = chromadb.PersistentClient(path=db_path)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        try:
            collection = client.get_collection(
                name="gdelt_news_collection",
                embedding_function=ef
            )
        except Exception:
            return {
                "error": "Collection not found",
                "message": "News collection 'gdelt_news_collection' not found. Please build the knowledge base first."
            }
        
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, 10)
        )
        
        if not results['documents'] or not results['documents'][0]:
            return {
                "query": query,
                "results": [],
                "message": f"No related news found for '{query}'"
            }
        
        # Format results
        formatted_results = []
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                "event_id": results['ids'][0][i],
                "date": results['metadatas'][0][i].get('date', 'Unknown'),
                "source_url": results['metadatas'][0][i].get('source_url', 'Unknown'),
                "content": results['documents'][0][i],
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        
    except ImportError:
        return {
            "error": "Missing dependencies",
            "message": "ChromaDB not installed. Run: pip install chromadb sentence-transformers"
        }
    except Exception as e:
        return {
            "error": "Search failed",
            "message": str(e)
        }
