"""
GDELT MCP Core Tools V2
Design Philosophy: From high-parameter queries to high-intent understanding

from:
  query_by_actor(actor="USA", date_start="2024-01-01", ...)
to:
  search_events(query="1monthWashington protests", max_results=10)

Tool count: 15 → 5
"""

import json
import logging
from typing import Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Import database connection
from ..database import get_db_pool
from ..cache import query_cache
from ..services.gdelt_optimized import GDELTServiceOptimized

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "events_table"


# ============================================================================
# Input Model Definitions
# ============================================================================

class SearchEventsInput(BaseModel):
    """Search events - supports natural language queries"""
    query: str = Field(
        ...,
        description="Natural language query，e.g.'1monthWashington protests'、'in东最近conflict'"
    )
    time_hint: Optional[str] = Field(
        None,
        description="Time hint: 'today', 'yesterday', 'this_week', 'this_month', '2024-01'"
    )
    location_hint: Optional[str] = Field(
        None,
        description="Location hint，e.g.'Washington', 'China', 'Middle East'"
    )
    event_type: Optional[Literal[
        'conflict', 'cooperation', 'protest', 'diplomacy', 
        'military', 'economic', 'any'
    ]] = Field(
        'any',
        description="Event type filter"
    )
    severity: Optional[Literal['low', 'medium', 'high', 'critical', 'any']] = Field(
        'any',
        description="Severity filter"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return（Default10item(s)）"
    )


class GetEventDetailInput(BaseModel):
    """Get event details - by fingerprint ID"""
    fingerprint: str = Field(
        ...,
        description="Event fingerprint ID，e.g.'US-20240115-WDC-PROTEST-001'"
    )
    include_causes: bool = Field(
        default=True,
        description="Whether to include cause analysis"
    )
    include_effects: bool = Field(
        default=True,
        description="Whether to include effect analysis"
    )
    include_related: bool = Field(
        default=True,
        description="Whether to include related events"
    )


class GetRegionalOverviewInput(BaseModel):
    """Get regional situation overview"""
    region: str = Field(
        ...,
        description="Region name or code，e.g.'China', 'Middle East', 'US-CA'"
    )
    time_range: Literal['day', 'week', 'month', 'quarter', 'year'] = Field(
        default='week',
        description="Time range"
    )
    include_trend: bool = Field(
        default=True,
        description="Whether to include trend analysis"
    )
    include_risks: bool = Field(
        default=True,
        description="Whether to include risk assessment"
    )


class GetHotEventsInput(BaseModel):
    """Get hot event recommendations"""
    date: Optional[str] = Field(
        None,
        description="Date, e.g.,'2024-01-15'，Default to yesterday"
    )
    region_filter: Optional[str] = Field(
        None,
        description="Region filter，e.g.'Asia', 'Europe'"
    )
    top_n: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of hot events to return"
    )


class GetTopEventsInput(BaseModel):
    """Get highest heat events in time period"""
    start_date: str = Field(
        ...,
        description="Start date，e.g.'2024-01-01'"
    )
    end_date: str = Field(
        ...,
        description="End date，e.g.'2024-12-31'"
    )
    region_filter: Optional[str] = Field(
        None,
        description="Region filter，e.g.'USA', 'China', 'Middle East'"
    )
    event_type: Optional[Literal['conflict', 'cooperation', 'protest', 'any']] = Field(
        'any',
        description="Event type filter"
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number to return（Default10item(s)）"
    )


class GetDailyBriefInput(BaseModel):
    """Get daily brief"""
    date: Optional[str] = Field(
        None,
        description="Date, default is yesterday"
    )
    region_focus: Optional[str] = Field(
        None,
        description="Region focus，e.g.'global', 'asia', 'us'"
    )
    format: Literal['summary', 'detailed', 'executive'] = Field(
        default='summary',
        description="Brief format"
    )


class NewsSearchInput(BaseModel):
    """News semantic search - RAG vector retrieval"""
    query: str = Field(
        ...,
        description="English semantic search query，e.g. 'protesters demanding climate action', 'police response to protests'"
    )
    n_results: int = Field(
        default=3,
        description="Number of related news to return",
        ge=1,
        le=10
    )


class StreamQueryInput(BaseModel):
    """Stream query input"""
    actor_name: str = Field(
        ...,
        description="Actor name keyword, supports fuzzy matching"
    )
    start_date: Optional[str] = Field(
        None,
        description="Start date (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        None,
        description="End date (YYYY-MM-DD)"
    )
    max_results: int = Field(
        default=100,
        description="Maximum number to return",
        ge=1,
        le=1000
    )


class DashboardInput(BaseModel):
    """DashboardData输入"""
    start_date: str = Field(
        ...,
        description="Start date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )


class TimeSeriesInput(BaseModel):
    """Timeseriesanalysis输入"""
    start_date: str = Field(
        ...,
        description="Start date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    granularity: Literal['day', 'week', 'month'] = Field(
        default='day',
        description="Time粒degree: day(day), week(周), month(month)"
    )


class GeoHeatmapInput(BaseModel):
    """placeheatmapmap输入"""
    start_date: str = Field(
        ...,
        description="Start date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date，Format: YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    precision: int = Field(
        default=2,
        ge=1,
        le=4,
        description="坐standardPrecision(小data位data)，越大Precision越高"
    )


# ============================================================================
# toolNote册函data
# ============================================================================

def register_core_tools(mcp: FastMCP):
    """Note册核心toolV2toMCP服务器"""
    
    @mcp.tool()
    async def search_events(params: SearchEventsInput) -> str:
        """
        Intelligent event search - core entry tool
        
        Example:
        - "1monthWashington protests" → time_hint=2024-01, location_hint=Washington, event_type=protest
        - "in东militaryconflict" → location_hint=Middle East, event_type=conflict
        - "inUSeconomic往来" → query="China US economic"
        """
        # parseTimeHint（e.g.果没有provide，tryfrom query 提取）
        time_hint = params.time_hint
        if not time_hint and params.query:
            # Extract time keywords from query
            import re
            query_lower = params.query.lower()
            
            # match "2024year" or "2024"
            year_match = re.search(r'(\d{4})\s*year?', query_lower)
            if year_match:
                year = year_match.group(1)
                # Check if month is present
                month_match = re.search(r'(\d{1,2})\s*month', query_lower)
                if month_match:
                    month = month_match.group(1).zfill(2)
                    time_hint = f"{year}-{month}"
                else:
                    time_hint = year  # Full year
            
            # match "1month"、"onemonth" etc.（Current year）
            elif re.search(r'(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|tenone|tentwo)\s*month', query_lower):
                month_map = {'one': '01', 'two': '02', 'three': '03', 'four': '04', 'five': '05', 'six': '06',
                            'seven': '07', 'eight': '08', 'nine': '09', 'ten': '10', 'tenone': '11', 'tentwo': '12'}
                month_match = re.search(r'(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|tenone|tentwo)\s*month', query_lower)
                if month_match:
                    month = month_match.group(1)
                    if month in month_map:
                        month = month_map[month]
                    else:
                        month = month.zfill(2)
                    time_hint = f"2024-{month}"  # Default to 2024
        
        date_start, date_end = _parse_time_hint(time_hint)
        
        # Build query (JOIN event_fingerprints to get fingerprints)
        query = f"""
        SELECT 
            e.GlobalEventID,
            e.SQLDATE,
            e.Actor1Name,
            e.Actor2Name,
            e.EventCode,
            e.EventRootCode,
            e.GoldsteinScale,
            e.NumArticles,
            e.AvgTone,
            e.ActionGeo_FullName,
            e.ActionGeo_CountryCode,
            e.ActionGeo_Lat,
            e.ActionGeo_Long,
            f.fingerprint,
            f.headline,
            f.summary,
            f.event_type_label,
            f.severity_score
        FROM {DEFAULT_TABLE} e
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        WHERE 1=1
        """
        
        conditions = []
        query_params = []
        
        # Time conditions
        conditions.append("e.SQLDATE BETWEEN %s AND %s")
        query_params.extend([date_start, date_end])
        
        # Location conditions (using index-optimized prefix matching)
        if params.location_hint:
            # Parse location input, get all possible variants
            location_terms = _parse_region_input(params.location_hint)
            
            # Build index-friendly matching conditions (prefix matching)
            location_conditions = []
            for term in location_terms:
                # 1. Prefix matching (index-friendly): 'Washington%'
                location_conditions.append("e.ActionGeo_FullName LIKE %s")
                query_params.append(f'{term}%')
                
                # 2. Prefix matching after comma (city name after comma): '%, Washington%'
                location_conditions.append("e.ActionGeo_FullName LIKE %s")
                query_params.append(f'%, {term}%')
                
                # 3. Country code (2-3 uppercase letters)
                if len(term) <= 3 and term.isalpha():
                    location_conditions.append("e.ActionGeo_CountryCode = %s")
                    query_params.append(term.upper()[:3])
                
                # 4. State code matching (e.g., DC, TX, CA)
                if len(term) == 2:
                    location_conditions.append("e.ActionGeo_ADM1Code = %s")
                    query_params.append(f'US_{term.upper()}')
            
            # Combine all location conditions
            if location_conditions:
                conditions.append(f"({' OR '.join(location_conditions)})")
        
        # Event type
        if params.event_type != 'any':
            type_conditions = {
                'conflict': "e.GoldsteinScale < -5",
                'cooperation': "e.GoldsteinScale > 5",
                'protest': "e.EventRootCode = '14'",
                'diplomacy': "e.EventRootCode IN ('01', '02', '03')",
                'military': "e.EventRootCode IN ('18', '19', '20')",
                'economic': "e.EventRootCode = '06'"
            }
            if params.event_type in type_conditions:
                conditions.append(type_conditions[params.event_type])
        
        # Build complete query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Sort: prioritize fingerprinted (more info), then by heat
        query += f"""
        ORDER BY 
            CASE WHEN f.fingerprint IS NOT NULL THEN 1 ELSE 0 END DESC,
            e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT {params.max_results}
        """
        
        # Execute query
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, tuple(query_params))
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    if not rows:
                        return f"❌ notFoundWith '{params.query}' relatedEvent（Timerange: {date_start} ~ {date_end}）"
                    
                    # Format as readable result
                    return _format_search_results_v2(rows, columns, params.query)
        except Exception as e:
            logger.error(f"Search events failed: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_event_detail(params: GetEventDetailInput) -> str:
        """
        Get event details - includes cause and effect analysis
        
        Supports two fingerprint formats:
        - Standard fingerprint: "US-20240115-WDC-PROTEST-001" (ETL generated)
        - Temporary fingerprint: "EVT-2024-12-25-1217480788" (temporarily generated by search_events)
        """
        fingerprint = params.fingerprint
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    
                    # Determine fingerprint type
                    if fingerprint.startswith('EVT-'):
                        # Temporary fingerprint format: EVT-YYYY-MM-DD-GID
                        # Extract GlobalEventID
                        parts = fingerprint.split('-')
                        if len(parts) >= 4:
                            # Last part is GID, convert to integer
                            try:
                                global_event_id = int(parts[-1])
                            except ValueError:
                                return f"❌ Temporary fingerprint format error, cannot parse GID: {fingerprint}"
                        else:
                            return f"❌ Temporary fingerprint format error: {fingerprint}"
                        
                        # Directly query events_table
                        await cursor.execute(f"""
                            SELECT * FROM {DEFAULT_TABLE}
                            WHERE GlobalEventID = %s
                        """, (global_event_id,))
                        
                        event_row = await cursor.fetchone()
                        if not event_row:
                            return f"⚠️ Event not found: GlobalEventID={global_event_id}"
                        
                        event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                        event_data = dict(zip(event_cols, event_row))
                        
                        # Generate display content in real-time
                        return _format_event_detail_from_raw(event_data, fingerprint, params)
                    
                    else:
                        # Standard fingerprint, query fingerprint table
                        await cursor.execute("""
                            SELECT global_event_id, fingerprint, headline, summary,
                                   key_actors, event_type_label, severity_score,
                                   location_name, location_country
                            FROM event_fingerprints
                            WHERE fingerprint = %s
                        """, (fingerprint,))
                        
                        fp_row = await cursor.fetchone()
                        
                        if fp_row:
                            global_event_id = int(fp_row[0]) if fp_row[0] else None
                            if not global_event_id:
                                return f"⚠️ Fingerprint data incomplete: {fingerprint}"
                            # Get complete event data
                            await cursor.execute(f"""
                                SELECT * FROM {DEFAULT_TABLE}
                                WHERE GlobalEventID = %s
                            """, (global_event_id,))
                            event_row = await cursor.fetchone()
                            event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                            event_data = dict(zip(event_cols, event_row)) if event_row else {}
                            
                            # Build output using fingerprint table data
                            output = []
                            output.append(f"# 📰 {fp_row[2] or 'EventDetails'}")
                            output.append(f"**Fingerprint ID**: `{fingerprint}`")
                            output.append(f"**GlobalEventID**: {global_event_id}")
                            output.append(f"**Time**: {event_data.get('SQLDATE', 'N/A')}")
                            output.append(f"**Location**: {fp_row[7] or event_data.get('ActionGeo_FullName', 'N/A')}")
                            output.append(f"**Type**: {fp_row[5] or 'N/A'}")
                            output.append(f"**Severity**: {'🔴' * int((fp_row[6] or 5) / 2)}")
                            output.append("")
                            
                            if fp_row[3]:  # summary
                                output.append(f"**Summary**: {fp_row[3]}")
                                output.append("")
                            
                            # Actors
                            if fp_row[4]:  # key_actors
                                try:
                                    actors = json.loads(fp_row[4])
                                    if actors:
                                        output.append(f"**Actors**: {', '.join(actors)}")
                                        output.append("")
                                except:
                                    pass
                            
                            # rawData
                            output.append("## 📊 Data Metrics")
                            output.append(f"- GoldsteinScale: {event_data.get('GoldsteinScale', 'N/A')}")
                            output.append(f"- NumArticles: {event_data.get('NumArticles', 'N/A')}")
                            output.append(f"- AvgTone: {event_data.get('AvgTone', 'N/A')}")
                            output.append("")
                            
                            # placeholder：Cause and Effect Analysis
                            if params.include_causes or params.include_effects:
                                output.append("## ⏱️ Causal Analysis")
                                output.append("_(requires running causal chain analysis pipeline)_")
                                output.append("")
                            
                            return "\n".join(output)
                        else:
                            # try用fingerprintas GID directquery
                            try:
                                await cursor.execute(f"""
                                    SELECT * FROM {DEFAULT_TABLE}
                                    WHERE GlobalEventID = %s
                                """, (fingerprint,))
                                
                                event_row = await cursor.fetchone()
                                if event_row:
                                    event_cols = [desc[0] for desc in cursor.description] if cursor.description else []
                                    event_data = dict(zip(event_cols, event_row))
                                    return _format_event_detail_from_raw(event_data, fingerprint, params)
                            except:
                                pass
                            
                            return f"⚠️ Event fingerprint `{fingerprint}` not yet generated or does not exist\n\nHint: This fingerprint may not have been processed by ETL yet, or use search_events to search again。"
                    
        except Exception as e:
            logger.error(f"Failed to get event details: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_regional_overview(params: GetRegionalOverviewInput) -> str:
        """
        GetRegional SituationOverview - 洞察Summaryandnon-rawData
        
        Example:
        - region="Middle East", time_range="week"
        - region="China", time_range="month", include_risks=true
        """
        # Calculate date range
        end_date = datetime.now().date()
        days_map = {'day': 1, 'week': 7, 'month': 30, 'quarter': 90, 'year': 365}
        start_date = end_date - timedelta(days=days_map.get(params.time_range, 7))
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Check if pre-computed regional statistics exist
                    await cursor.execute("""
                        SELECT * FROM region_daily_stats
                        WHERE region_code = %s AND date BETWEEN %s AND %s
                        ORDER BY date DESC
                        LIMIT 7
                    """, (params.region.upper(), start_date, end_date))
                    
                    stats_rows = await cursor.fetchall()
                    
                    if stats_rows:
                        # Use pre-computed data
                        return _format_regional_overview_precomputed(
                            stats_rows, params.region, start_date, end_date,
                            params.include_trend, params.include_risks
                        )
                    
                    # Fallback: real-time query
                    await cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total,
                            AVG(GoldsteinScale) as avg_goldstein,
                            AVG(AvgTone) as avg_tone,
                            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflicts,
                            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation
                        FROM {DEFAULT_TABLE}
                        WHERE SQLDATE BETWEEN %s AND %s
                          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
                    """, (start_date, end_date, params.region.upper(), f'%{params.region}%'))
                    
                    row = await cursor.fetchone()
                    
                    output = []
                    output.append(f"# 🌍 {params.region} Regional Situation")
                    output.append(f"**Timerange**: {start_date} ~ {end_date}")
                    output.append("")
                    
                    if row and row[0]:
                        total = row[0]
                        avg_goldstein = row[1] or 0
                        conflicts = row[3] or 0
                        
                        # Situation Score
                        intensity = min(10, max(1, abs(avg_goldstein)))
                        risk_level = _calculate_risk_level(intensity)
                        output.append(f"**Situation Score**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
                        output.append(f"**Risk Level**: {risk_level}")
                        output.append("")
                        
                        output.append("## 📈 Key Metrics")
                        output.append(f"- Total Events: {total}")
                        output.append(f"- Conflict Events: {conflicts} ({conflicts/total*100:.1f}%)")
                        output.append(f"- Average Goldstein Index: {avg_goldstein:.2f}")
                        output.append("")
                        
                        # Hot Events（real-timequery）
                        await cursor.execute(f"""
                            SELECT Actor1Name, Actor2Name, EventCode, GoldsteinScale, 
                                   NumArticles, ActionGeo_FullName, SQLDATE
                            FROM {DEFAULT_TABLE}
                            WHERE SQLDATE BETWEEN %s AND %s
                              AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
                            ORDER BY NumArticles * ABS(GoldsteinScale) DESC
                            LIMIT 5
                        """, (start_date, end_date, params.region.upper(), f'%{params.region}%'))
                        
                        hot_events = await cursor.fetchall()
                        if hot_events:
                            output.append("## 🔥 Hot Events")
                            for i, evt in enumerate(hot_events, 1):
                                actor1, actor2 = evt[0], evt[1]
                                location = evt[5] or params.region
                                output.append(f"{i}. {actor1} vs {actor2} ({location}) - {evt[4]}articles")
                            output.append("")
                    else:
                        output.append("⚠️ 该Time段withinnotFoundRelated Events")
                    
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"Failed to get regional overview: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_hot_events(params: GetHotEventsInput) -> str:
        """
        GetdailyHot Events推荐
        
        Example:
        - date="2024-01-15", top_n=5
        - region_filter="Asia", top_n=10
        """
        # Default to yesterday
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # First try to get from pre-computed table
                    await cursor.execute("""
                        SELECT hot_event_fingerprints, top_actors, top_locations
                        FROM daily_summary
                        WHERE date = %s
                    """, (query_date,))
                    
                    result = await cursor.fetchone()
                    
                    events = []
                    
                    if result and result[0]:
                        # Has pre-computed data
                        hot_fingerprints = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                        
                        # Get fingerprint details
                        for fp in hot_fingerprints[:params.top_n]:
                            await cursor.execute("""
                                SELECT f.fingerprint, f.headline, f.summary, f.severity_score,
                                       f.location_name, e.SQLDATE, e.GoldsteinScale, e.NumArticles,
                                       e.GlobalEventID, 'standard' as fp_type
                                FROM event_fingerprints f
                                JOIN events_table e ON f.global_event_id = e.GlobalEventID
                                WHERE f.fingerprint = %s
                            """, (fp,))
                            row = await cursor.fetchone()
                            if row:
                                events.append(row)
                    
                    # e.g.果没Has pre-computed data，real-timequerybuttrymatchfingerprinttable
                    if not events:
                        region_condition = ""
                        query_params = [query_date]
                        
                        if params.region_filter:
                            region_condition = "AND (e.ActionGeo_CountryCode = %s OR e.ActionGeo_FullName LIKE %s)"
                            query_params.extend([params.region_filter.upper(), f'%{params.region_filter}%'])
                        
                        # 先查real-time热点，然afterLEFT JOINfingerprinttableGetStandard fingerprint
                        await cursor.execute(f"""
                            SELECT 
                                COALESCE(f.fingerprint, CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR))) as fingerprint,
                                COALESCE(f.headline, CONCAT(
                                    COALESCE(NULLIF(e.Actor1Name, ''), 'One party'), 
                                    ' vs ', 
                                    COALESCE(NULLIF(e.Actor2Name, ''), 'Other party')
                                )) as headline,
                                COALESCE(f.summary, e.ActionGeo_FullName) as summary,
                                COALESCE(f.severity_score, ABS(e.GoldsteinScale)) as severity_score,
                                COALESCE(f.location_name, e.ActionGeo_FullName) as location_name,
                                e.SQLDATE as date,
                                e.GoldsteinScale,
                                e.NumArticles,
                                e.GlobalEventID,
                                CASE WHEN f.fingerprint IS NOT NULL THEN 'standard' ELSE 'temp' END as fp_type
                            FROM {DEFAULT_TABLE} e
                            LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
                            WHERE e.SQLDATE = %s {region_condition}
                            ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
                            LIMIT %s
                        """, tuple(query_params + [params.top_n]))
                        
                        events = await cursor.fetchall()
                    
                    # Formatizationoutput
                    if not events:
                        return f"📭 {query_date} notFoundHot Events"
                    
                    output = []
                    output.append(f"# 🔥 {query_date} Hot Events TOP {len(events)}")
                    output.append("")
                    
                    for i, evt in enumerate(events, 1):
                        fingerprint = evt[0]
                        raw_headline = evt[1]
                        # 改进 headline 显示
                        if raw_headline and raw_headline not in ['One party vs Other party', ' vs ', 'NULL vs NULL']:
                            headline = raw_headline
                        else:
                            # tryfromfingerprintorEvent type推断
                            gid = evt[8] if len(evt) > 8 else (fingerprint.split('-')[-1] if '-' in str(fingerprint) else 'notknow')
                            headline = f"Event #{gid}"
                        location = evt[4] or "notknowLocation"
                        severity = evt[3] or 5
                        num_articles = evt[7] or 0
                        fp_type = evt[9] if len(evt) > 9 else 'unknown'
                        
                        # standard记fingerprintType
                        fp_badge = "📌" if fp_type == 'standard' else "📝"
                        
                        output.append(f"## {i}. {headline}")
                        output.append(f"**fingerprint**: {fp_badge} `{fingerprint}` {'(standard)' if fp_type == 'standard' else '(temporary)'}")
                        output.append(f"**Location**: {location} | **Severity**: {'🔴' * int(severity / 2)}")
                        output.append(f"**articlesamount**: {num_articles} ")
                        if evt[2] and len(str(evt[2])) > 10:
                            output.append(f"**Summary**: {str(evt[2])[:100]}...")
                        output.append("")
                    
                    output.append("💡 _Use `get_event_detail` ViewDetails_")
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"GetHot Eventsfailed: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_top_events(params: GetTopEventsInput) -> str:
        """
        Get top events by heat score in a time period
        
        Heat score = NumArticles × |GoldsteinScale| (media coverage × conflict intensity)
        
        Examples:
        - Full year 2024: start_date="2024-01-01", end_date="2024-12-31"
        - Washington DC in 2024: start_date="2024-01-01", end_date="2024-12-31", region_filter="Washington"
        - USA conflicts: start_date="2024-01-01", end_date="2024-12-31", region_filter="USA", event_type="conflict"
        - Middle East protests: region_filter="Middle East", event_type="protest"
        
        Region filter supports: country codes (USA, CHN), city names (Washington, Beijing), regions (Middle East)
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Buildqueryitem(s)item
                    conditions = ["SQLDATE BETWEEN %s AND %s"]
                    query_params = [params.start_date, params.end_date]
                    
                    # Region filter（intelligentparse，support索引optizationquery）
                    if params.region_filter:
                        region_input = params.region_filter.strip()
                        
                        # intelligentparse用户输入
                        parsed_regions = _parse_region_input(region_input)
                        
                        # Buildindex-friendlymatchitem(s)item
                        region_conditions = []
                        
                        for region in parsed_regions:
                            # 1. Prefix matching (index-friendly): 'Washington%'
                            region_conditions.append("ActionGeo_FullName LIKE %s")
                            query_params.append(f'{region}%')
                            
                            # 2. 逗号afterbefore缀match: '%, Washington%'
                            region_conditions.append("ActionGeo_FullName LIKE %s")
                            query_params.append(f'%, {region}%')
                            
                            # 3. Country code (2-3 uppercase letters)
                            if len(region) <= 3 and region.isalpha():
                                region_conditions.append("ActionGeo_CountryCode = %s")
                                query_params.append(region.upper()[:3])
                            
                            # 4. State code matching (e.g., DC, TX, CA)
                            if len(region) == 2:
                                region_conditions.append("ActionGeo_ADM1Code = %s")
                                query_params.append(f'US_{region.upper()}')
                        
                        where_clause_region = " OR ".join(region_conditions)
                        conditions.append(f"({where_clause_region})")
                    
                    # Event typefilter
                    if params.event_type == 'conflict':
                        conditions.append("GoldsteinScale < -5")
                    elif params.event_type == 'cooperation':
                        conditions.append("GoldsteinScale > 5")
                    elif params.event_type == 'protest':
                        conditions.append("EventRootCode = '14'")
                    
                    where_clause = " AND ".join(conditions)
                    
                    # queryHeat最高Event
                    # Heat = NumArticles * |GoldsteinScale| (articlesamount * conflictintensity)
                    await cursor.execute(f"""
                        SELECT 
                            GlobalEventID,
                            SQLDATE,
                            Actor1Name,
                            Actor2Name,
                            ActionGeo_FullName,
                            ActionGeo_CountryCode,
                            EventRootCode,
                            GoldsteinScale,
                            NumArticles,
                            NumSources,
                            AvgTone,
                            SOURCEURL
                        FROM {DEFAULT_TABLE}
                        WHERE {where_clause}
                        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
                        LIMIT %s
                    """, tuple(query_params + [params.top_n]))
                    
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return f"📭 {params.start_date} ~ {params.end_date} No events matching criteria found during this period"
                    
                    # Formatizationoutput
                    output = []
                    output.append(f"# 🔥 {params.start_date} ~ {params.end_date} Highest heat events TOP {len(rows)}")
                    if params.region_filter:
                        output.append(f"**Region filter**: {params.region_filter}")
                    if params.event_type != 'any':
                        output.append(f"**Typefilter**: {params.event_type}")
                    output.append("")
                    output.append("| Rank | Fingerprint ID | Event | Heat | Date | Location |")
                    output.append("|------|--------|------|------|------|------|")
                    
                    detail_list = []
                    
                    for i, row in enumerate(rows, 1):
                        (gid, date, actor1, actor2, location, country, 
                         event_root, goldstein, articles, sources, tone, url) = row
                        
                        # generateTemporary fingerprint
                        temp_fp = f"EVT-{date}-{gid}"
                        
                        # Event typelabel
                        type_labels = {
                            '01': 'statement', '02': 'appeal', '03': 'intention',
                            '04': 'consultation', '05': 'cooperation', '06': 'aid',
                            '07': 'aid', '08': 'aid', '09': 'concession',
                            '10': 'demand', '11': 'dissatisfaction', '12': 'reject',
                            '13': 'threat', '14': 'protest', '15': '武力',
                            '16': 'degrade', '17': 'force', '18': 'friction',
                            '19': 'conflict', '20': 'attack'
                        }
                        event_label = type_labels.get(str(event_root)[:2], 'Event') if event_root else 'Event'
                        
                        # Heatscore
                        hot_score = (articles or 0) * abs(goldstein or 0)
                        
                        actor1 = actor1 or 'Some country'
                        actor2 = actor2 or 'Other party'
                        location_short = (location or 'notknow')[:15]  # shortenLocation
                        
                        # 简izationTitle
                        title = f"{actor1[:10]} vs {actor2[:10]}"
                        
                        # table格行
                        output.append(f"| {i} | `{temp_fp}` | {title} [{event_label}] | {hot_score:.0f} | {date} | {location_short} |")
                        
                        # Detailed Information（used forafter续展开）
                        detail_list.append({
                            'rank': i,
                            'fingerprint': temp_fp,
                            'title': title,
                            'event_label': event_label,
                            'date': date,
                            'location': location,
                            'hot_score': hot_score,
                            'articles': articles,
                            'goldstein': goldstein,
                            'tone': tone
                        })
                    
                    output.append("")
                    output.append("## Detailed Information")
                    output.append("")
                    
                    for d in detail_list[:5]:  # only展示before5Details
                        output.append(f"### {d['rank']}. {d['title']} [{d['event_label']}]")
                        output.append(f"- **fingerprint**: `{d['fingerprint']}` ← Copy this ID to view details")
                        output.append(f"- **Time**: {d['date']} | **Location**: {d['location']}")
                        output.append(f"- **Heat**: {d['hot_score']:.0f} (articles{d['articles']} × intensity{abs(d['goldstein'] or 0):.1f})")
                        output.append(f"- **Goldstein**: {d['goldstein']:.2f} | **Tone**: {d['tone']:.2f}")
                        output.append("")
                    
                    if len(detail_list) > 5:
                        output.append(f"_... also have {len(detail_list) - 5} Event，UseFingerprint IDViewDetails_")
                        output.append("")
                    
                    output.append("💡 **ViewEventDetails**: `get_event_detail(fingerprint='EVT-YYYY-MM-DD-GID')`")
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"GetTopEventfailed: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_daily_brief(params: GetDailyBriefInput) -> str:
        """
        Getdaily简report - categorynews-likeSummary
        
        Example:
        - date="2024-01-15", format="summary"
        - region_focus="global", format="executive"
        """
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # tryfrom预calculatetableGet
                    await cursor.execute("""
                        SELECT *
                        FROM daily_summary
                        WHERE date = %s
                    """, (query_date,))
                    
                    brief = await cursor.fetchone()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    
                    if brief:
                        data = dict(zip(cols, brief))
                    else:
                        # real-timecalculate
                        await cursor.execute(f"""
                            SELECT 
                                COUNT(*) as total_events,
                                SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_events,
                                SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation_events,
                                AVG(GoldsteinScale) as avg_goldstein,
                                AVG(AvgTone) as avg_tone
                            FROM {DEFAULT_TABLE}
                            WHERE SQLDATE = %s
                        """, (query_date,))
                        
                        row = await cursor.fetchone()
                        data = {
                            'total_events': row[0] if row else 0,
                            'conflict_events': row[1] if row else 0,
                            'cooperation_events': row[2] if row else 0,
                            'avg_goldstein': row[3] if row else 0,
                            'avg_tone': row[4] if row else 0,
                            'top_actors': '[]',
                            'top_locations': '[]'
                        }
                    
                    output = []
                    output.append(f"# 📰 {query_date} 全球Event简report")
                    output.append("")
                    
                    # one句话总结
                    total = data.get('total_events', 0)
                    conflict = data.get('conflict_events', 0)
                    conflict_pct = (conflict / max(total, 1)) * 100
                    goldstein = data.get('avg_goldstein', 0) or 0
                    
                    output.append(f"📊 **Overview**: Today recorded a total of **{total:,}** occurrencecountry际Event，")
                    output.append(f"Conflict Events {conflict} occurrence ({conflict_pct:.1f}%)，")
                    output.append(f"Average Goldstein Indexfor {goldstein:.2f}")
                    output.append("")
                    
                    # according toformatreturndifferent详细程degree
                    if params.format == 'summary':
                        # Summary version
                        if brief and data.get('hot_event_fingerprints'):
                            hot_fps = json.loads(data['hot_event_fingerprints']) if isinstance(data['hot_event_fingerprints'], str) else data['hot_event_fingerprints']
                            output.append("## 🔥 Today's Hot Events")
                            for fp in hot_fps[:3]:
                                output.append(f"- `{fp}`")
                            output.append("")
                        
                        output.append("💡 _Use `get_hot_events` Get详细热点信info_")
                        
                    elif params.format == 'detailed':
                        # Detailed version
                        if data.get('top_actors'):
                            try:
                                actors = json.loads(data['top_actors']) if isinstance(data['top_actors'], str) else data['top_actors']
                                if actors:
                                    output.append("## 👥 mainActors")
                                    for actor in actors[:5]:
                                        name = actor.get('name', 'Unknown')
                                        count = actor.get('count', 0)
                                        output.append(f"- {name}: {count} 次")
                                    output.append("")
                            except:
                                pass
                        
                        if data.get('top_locations'):
                            try:
                                locations = json.loads(data['top_locations']) if isinstance(data['top_locations'], str) else data['top_locations']
                                if locations:
                                    output.append("## 🌍 Active Regions")
                                    for loc in locations[:5]:
                                        name = loc.get('name', 'Unknown')
                                        count = loc.get('count', 0)
                                        output.append(f"- {name}: {count} occurrence")
                                    output.append("")
                            except:
                                pass
                    
                    elif params.format == 'executive':
                        # 执行Summary版
                        output.append("## 📋 执行Summary")
                        trend = "⚠️ conflict trend rising" if goldstein < -3 else "✅ situation relatively stable"
                        output.append(f"- {trend}")
                        output.append(f"- Event密degree: {total/1000:.1f}K/天")
                        output.append("")
                    
                    return "\n".join(output)
                    
        except Exception as e:
            logger.error(f"Failed to get daily brief: {e}")
            return f"❌ Query failed: {str(e)}"
    
    
    # ========================================================================
    # RAG semanticsearchtool (from txx_docker)
    # ========================================================================
    
    @mcp.tool()
    async def search_news_context(params: NewsSearchInput) -> str:
        """
        【RAG semanticsearch】query新闻know识libraryGet真实articles细节
        
        When users need to know:
        - Event具体occurrence因
        - Specific demands of crowds
        - Police response
        - Event详细背scenario
        
        call this tool to search real news text in vector knowledge base。
        
        Examplequery:
        - "protesters demanding climate action"
        - "police response to Washington protest"
        - "Texas border conflict reasons"
        """
        try:
            import os
            import chromadb
            from chromadb.utils import embedding_functions
            
            # Initialize ChromaDB
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../chroma_db'))
            
            if not os.path.exists(db_path):
                return f"❌ Vector database not found: {db_path}\nPlease run first: python start_kb.py Build knowledge base"
            
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
                return "❌ 新闻集合notFound，请先Build knowledge base"
            
            # Execute semantic search
            results = collection.query(
                query_texts=[params.query],
                n_results=params.n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return f"📭 Not found in knowledge base related to '{params.query}' related新闻articles。\n\nSuggestions:\n1. Try different English keywords\n2. Check if knowledge base is built (Run start_kb.py)"
            
            # FormatizationResult
            output = [f"# 🔍 RAG semanticsearchResult: '{params.query}'\n"]
            output.append(f"Found {len(results['documents'][0])} related news:\n")
            
            for i in range(len(results['documents'][0])):
                doc_text = results['documents'][0][i]
                event_id = results['ids'][0][i]
                url = results['metadatas'][0][i].get('source_url', 'Unknown')
                date = results['metadatas'][0][i].get('date', 'Unknown')
                
                # 截取before1000字符
                snippet = doc_text[:1000] + "..." if len(doc_text) > 1000 else doc_text
                
                output.append(f"## 📰 Result {i+1}")
                output.append(f"- **Event ID**: {event_id}")
                output.append(f"- **Date**: {date}")
                output.append(f"- **Source**: {url}")
                output.append(f"\n**within容Summary**:\n{snippet}\n")
            
            return "\n".join(output)
            
        except ImportError:
            return "❌ ChromaDB not安装，请Run: pip install chromadb sentence-transformers"
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return f"❌ RAG search failed: {str(e)}"
    
    
    # ========================================================================
    # streamingquerytool (from txx_docker)
    # ========================================================================
    
    @mcp.tool()
    async def stream_events(params: StreamQueryInput) -> str:
        """
        【streamingquery】处理大amountEventData，withinmemory-friendly
        
        当need处理大amountEvent时Use（e.g."analysis全yearallprotestEvent"），
        Streaming read avoids loading everything into memory at once。
        
        Applicable scenarios:
        - Preview before data export
        - 大amountEvent统计analysis
        - Memory-sensitive environments
        
        Example:
        - actor_name="Protest" - 查找allprotestRelated Events
        - actor_name="USA" + Timerange - UScountry全yearEvent
        """
        try:
            from ..database.streaming import StreamingQuery
            from ..database import get_db_pool
            
            pool = await get_db_pool()
            streaming = StreamingQuery(pool, chunk_size=50)
            
            # Buildquery
            date_filter = ""
            params_list = [f"%{params.actor_name}%", f"%{params.actor_name}%"]
            
            if params.start_date and params.end_date:
                date_filter = "AND SQLDATE BETWEEN %s AND %s"
                params_list.extend([params.start_date, params.end_date])
            
            query = f"""
                SELECT SQLDATE, Actor1Name, Actor2Name, EventCode,
                       GoldsteinScale, AvgTone, ActionGeo_FullName,
                       ActionGeo_Lat, ActionGeo_Long
                FROM {DEFAULT_TABLE}
                WHERE (Actor1Name LIKE %s OR Actor2Name LIKE %s)
                {date_filter}
                ORDER BY SQLDATE DESC
            """
            
            output = [f"# 🔍 streamingqueryResult: {params.actor_name}", ""]
            output.append("| Date | Actor1 | Actor2 | Goldstein | Tone | location |")
            output.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in streaming.stream(query, tuple(params_list)):
                output.append(
                    f"| {sanitize_text(row.get('SQLDATE'))} | "
                    f"{sanitize_text(row.get('Actor1Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('Actor2Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('GoldsteinScale', 'N/A'))} | "
                    f"{sanitize_text(row.get('AvgTone', 'N/A'))} | "
                    f"{sanitize_text(row.get('ActionGeo_FullName', 'N/A'))[:20]} |"
                )
                
                count += 1
                if count >= params.max_results:
                    output.append("| ... | (更多Result...) | ... | ... | ... | ... |")
                    break
            
            output.append(f"\n*Total returned {count} item(s)Result (streaming read)*")
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"streamingQuery failed: {e}")
            return f"❌ streamingQuery failed: {str(e)}"

    # =======================================================================
    # optizationanalysistool (and行query + streaming处理)
    # =======================================================================
    
    @mcp.tool()
    async def get_dashboard(params: DashboardInput) -> str:
        """
        [Optimized] Dashboard data - concurrent multi-dimensional statistics
        
        simultaneouslyreturn：dailyTrend、Top Actors、place理分布、Event type分布、综合统计
        3-5x faster than serial queries。
        
        Applicable scenarios:
        - 快速Overview某段Time整体state势
        - Get multi-dimensional statistics
        - Dashboard display
        """
        try:
            service = GDELTServiceOptimized()
            dashboard = await service.get_dashboard_data(
                params.start_date, params.end_date
            )
            
            lines = ["# 📊 DashboardData\n"]
            
            summary = dashboard.get("summary_stats", {})
            if "data" in summary and summary["data"]:
                s = summary["data"][0]
                lines.append(f"**Statistics Period**: {params.start_date} to {params.end_date}")
                lines.append(f"- 总Eventdata: {s.get('total_events', 0):,}")
                lines.append(f"- 独特Actors: {s.get('unique_actors', 0):,}")
                lines.append(f"- Average Goldstein: {s.get('avg_goldstein', 0):.2f}")
                lines.append("")
            
            daily = dashboard.get("daily_trend", {})
            if "data" in daily:
                lines.append("## 📈 Daily Trends (last 7 days)")
                for row in daily["data"][:7]:
                    lines.append(f"- {row.get('SQLDATE')}: {row.get('cnt')} Event")
                lines.append("")
            
            actors = dashboard.get("top_actors", {})
            if "data" in actors:
                lines.append("## 🎭 Top 5 Actors")
                for i, row in enumerate(actors["data"][:5], 1):
                    lines.append(f"{i}. {row.get('Actor1Name')}: {row.get('cnt')} Event")
                lines.append("")
            
            # calculate总耗时（only统计字典TypeResult）
            total_time = sum(
                v.get("elapsed_ms", 0) 
                for v in dashboard.values() 
                if isinstance(v, dict) and "elapsed_ms" in v
            )
            lines.append(f"\n*Query time: {total_time:.0f}ms (parallel optimization)*")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"DashboardQuery failed: {e}")
            return f"❌ Query failed: {str(e)}"
    
    
    @mcp.tool()
    async def analyze_time_series(params: TimeSeriesInput) -> str:
        """
        【optization】advancedTimeseriesanalysis - Datalibrary端聚合
        
        supportday/周/month粒degreeTimeTrendanalysis，All aggregation completed on database side，
        only传输Result，极大减少网络开销。
        
        Applicable scenarios:
        - analysisEvent随Time变izationTrend
        - tothandifferentTime粒degree模format
        - Identify periodic patterns
        """
        try:
            service = GDELTServiceOptimized()
            results = await service.analyze_time_series_advanced(
                params.start_date, params.end_date, params.granularity
            )
            
            if not results:
                return "📭 notFoundData"
            
            lines = [f"# 📈 Timeseriesanalysis ({params.granularity})\n"]
            lines.append(f"**Timerange**: {params.start_date} to {params.end_date}")
            lines.append(f"**Data points**: {len(results)} ")
            lines.append("")
            
            for row in results[:20]:  # 最多显示20
                period = row.get("period")
                lines.append(f"### {period}")
                lines.append(f"- Eventdata: {row.get('event_count', 0):,}")
                lines.append(f"- Conflict ratio: {row.get('conflict_pct', 0)}%")
                lines.append(f"- Cooperation ratio: {row.get('cooperation_pct', 0)}%")
                lines.append(f"- Average Goldstein: {row.get('avg_goldstein', 0)}")
                lines.append("")
            
            if len(results) > 20:
                lines.append(f"_... also have {len(results) - 20} Time周期_")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Timeseriesanalysisfailed: {e}")
            return f"❌ analysisfailed: {str(e)}"
    
    
    @mcp.tool()
    async def get_geo_heatmap(params: GeoHeatmapInput) -> str:
        """
        [Optimized] Geographic heatmap data - grid aggregation
        
        Aggregate nearby coordinates to grids, reducing frontend rendering pressure。
        return热点经纬degree、intensity、averageconflictvalueetc.信info。
        
        Applicable scenarios:
        - inplacemapabove可视izationEvent分布
        - Identify hot spot areas
        - Geographic density analysis
        """
        try:
            service = GDELTServiceOptimized()
            results = await service.get_geo_heatmap(
                params.start_date, params.end_date, params.precision
            )
            
            if not results:
                return "📭 notFoundplace理Data"
            
            heatmap_data = [
                {
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "intensity": int(row["intensity"]),
                    "avg_conflict": float(row["avg_conflict"]) if row["avg_conflict"] else None,
                    "location": row["sample_location"]
                }
                for row in results[:100]
            ]
            
            return f"""# 🗺️ Geographic Heatmap Data

**Timerange**: {params.start_date} to {params.end_date}
**Precision**: {params.precision} decimal places
**Hot spot count**: {len(heatmap_data)}

```json
{json.dumps(heatmap_data[:10], indent=2, ensure_ascii=False)}
```

*completeData共 {len(heatmap_data)} item(s)*

**Description**: 
- `intensity`: 该网格withinEventdataamount
- `avg_conflict`: Average conflict index (GoldsteinScale)
- Use `lat` and `lng` can mark hotspots on map
"""
        except Exception as e:
            logger.error(f"热力mapQuery failed: {e}")
            return f"❌ Query failed: {str(e)}"
    
    
    @mcp.tool()
    async def stream_query_events(params: StreamQueryInput) -> str:
        """
        [Optimized] Streaming query - process large data
        
        Use服务器端游standardstreaming readData，withinmemory usage稳定，
        Can handle regardless of data volume。
        
        Applicable scenarios:
        - need导出大amountEvent
        - Large data volume statistical analysis
        - Memory-sensitive environment
        
        With `stream_events` difference:
        - 本tool按Actors名称search
        - supports fuzzy matching Actor1Name and Actor2Name
        """
        try:
            service = GDELTServiceOptimized()
            
            lines = [f"# 🔍 streamingqueryResult: {params.actor_name}\n"]
            lines.append("| Date | Actor1 | Actor2 | Goldstein | Tone | location |")
            lines.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in service.stream_events_by_actor(
                params.actor_name, params.start_date, params.end_date
            ):
                # Use sanitize_text 防止 Markdown table格by破坏
                lines.append(
                    f"| {sanitize_text(row.get('SQLDATE'))} | "
                    f"{sanitize_text(row.get('Actor1Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('Actor2Name', 'N/A'))[:15]} | "
                    f"{sanitize_text(row.get('GoldsteinScale', 'N/A'))} | "
                    f"{sanitize_text(row.get('AvgTone', 'N/A'))} | "
                    f"{sanitize_text(row.get('ActionGeo_FullName', 'N/A'))[:20]} |"
                )
                
                count += 1
                if count >= params.max_results:
                    lines.append("| ... | (更多Result截断) | ... | ... | ... | ... |")
                    break
            
            lines.append(f"\n*Total returned {count} item(s)Result (streaming read)*")
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"streamingQuery failed: {e}")
            return f"❌ streamingQuery failed: {str(e)}"

    logger.info("✅ Core tools V2 registered (6basictool + RAG + 4optizationanalysistool)")


# ============================================================================
# Helper Functions
# ============================================================================

def sanitize_text(text) -> str:
    """Clean illegal characters in text to prevent Markdown table corruption"""
    if text is None:
        return "N/A"
    text = str(text)
    # remove surrogate pairs
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # 替换控制字符
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    # remove null bytes and Markdown table格特殊字符
    text = text.replace('\x00', '').replace('|', ' ').replace('\n', ' ')
    return text.strip()


def _parse_time_hint(time_hint: Optional[str]) -> tuple:
    """parseTimeHintforDaterange"""
    end = datetime.now().date()
    
    if not time_hint:
        # Default last 7 days
        start = end - timedelta(days=7)
    elif time_hint == 'today':
        start = end
    elif time_hint == 'yesterday':
        start = end - timedelta(days=1)
        end = start
    elif time_hint == 'this_week':
        start = end - timedelta(days=7)
    elif time_hint == 'this_month':
        start = end - timedelta(days=30)
    elif len(time_hint) == 4 and time_hint.isdigit():  # YYYY (e.g. "2024")
        # Full yearrange
        start = datetime.strptime(time_hint + "-01-01", '%Y-%m-%d').date()
        end = datetime.strptime(time_hint + "-12-31", '%Y-%m-%d').date()
    elif len(time_hint) == 7:  # YYYY-MM
        start = datetime.strptime(time_hint + "-01", '%Y-%m-%d').date()
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        try:
            start = datetime.strptime(time_hint, '%Y-%m-%d').date()
            end = start
        except:
            start = end - timedelta(days=7)
    
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def _parse_region_input(region_input: str) -> list:
    """
    Smart parse user region input for index-friendly queries
    
    Supports:
    - Chinese/English: 'Washington' → ['Washington', 'DC']
    - City + State: 'Washington DC' → ['Washington', 'DC']
    - Abbreviations: 'DC', 'TX', 'CA'
    - Full names: 'Washington', 'Texas'
    - Multiple variants: ['Washington', 'DC', 'Washingto', 'D.C.']
    
    Returns list of search terms for index-friendly LIKE queries
    """
    import re
    
    region = region_input.strip()
    results = set()
    
    # Common Chinese to English mappings
    cn_to_en = {
        'Washington': ['Washington', 'DC'],
        '纽约': ['New York', 'NYC'],
        '洛杉矶': ['Los Angeles', 'LA'],
        '芝加哥': ['Chicago'],
        '休斯顿': ['Houston'],
        '旧金山': ['San Francisco', 'SF'],
        '西雅map': ['Seattle'],
        '波士顿': ['Boston'],
        '迈阿密': ['Miami'],
        '达拉斯': ['Dallas'],
        '奥斯汀': ['Austin'],
        '费城': ['Philadelphia'],
        '亚特兰大': ['Atlanta'],
        '丹佛': ['Denver'],
        '凤凰城': ['Phoenix'],
        '底特律': ['Detroit'],
        'UScountry': ['United States', 'USA', 'US'],
        'incountry': ['China', 'CHN', 'CN'],
        '英country': ['United Kingdom', 'UK', 'GBR', 'GB'],
        'methodcountry': ['France', 'FRA', 'FR'],
        '德country': ['Germany', 'DEU', 'DE'],
        'day本': ['Japan', 'JPN', 'JP'],
        '俄罗斯': ['Russia', 'RUS', 'RU'],
        '加拿大': ['Canada', 'CAN', 'CA'],
        '墨西哥': ['Mexico', 'MEX', 'MX'],
        'printdegree': ['India', 'IND', 'IN'],
        '澳大利亚': ['Australia', 'AUS', 'AU'],
        '巴西': ['Brazil', 'BRA', 'BR'],
        'in东': ['Middle East', 'Mideast'],
        '欧洲': ['Europe', 'European'],
        '亚洲': ['Asia', 'Asian'],
        'non-洲': ['Africa', 'African'],
        '德state': ['Texas', 'TX'],
        '得克萨斯': ['Texas', 'TX'],
        '加state': ['California', 'CA'],
        '加利福尼亚': ['California', 'CA'],
        '佛state': ['Florida', 'FL'],
        '佛罗里达': ['Florida', 'FL'],
        '宾state': ['Pennsylvania', 'PA'],
        '宾夕method尼亚': ['Pennsylvania', 'PA'],
        '伊利诺伊': ['Illinois', 'IL'],
        '俄亥俄': ['Ohio', 'OH'],
        '密歇根': ['Michigan', 'MI'],
        '乔治亚': ['Georgia', 'GA'],
        '北卡': ['North Carolina', 'NC'],
        '南卡': ['South Carolina', 'SC'],
        '弗吉尼亚': ['Virginia', 'VA'],
        '马里兰': ['Maryland', 'MD'],
        'New Jersey': ['New Jersey', 'NJ'],
        '马萨诸塞': ['Massachusetts', 'MA'],
        '亚利桑那': ['Arizona', 'AZ'],
        '科罗拉多': ['Colorado', 'CO'],
        '犹他': ['Utah', 'UT'],
        'within华达': ['Nevada', 'NV'],
        '俄勒冈': ['Oregon', 'OR'],
        'Washingtonstate': ['Washington State', 'WA'],
        '夏威夷': ['Hawaii', 'HI'],
        '阿拉斯加': ['Alaska', 'AK'],
    }
    
    # Check for Chinese mappings
    if region in cn_to_en:
        results.update(cn_to_en[region])
    
    # Add original input
    results.add(region)
    
    # Remove 'City' suffix if present
    region_clean = re.sub(r'\s+(City|County|State)$', '', region, flags=re.IGNORECASE)
    if region_clean != region:
        results.add(region_clean)
    
    # Split by common separators (for "Washington DC" → ["Washington", "DC"])
    parts = re.split(r'[,\s]+', region)
    for part in parts:
        if part and len(part) > 1:  # Ignore single chars
            results.add(part.strip())
            # Check if part is Chinese
            if part in cn_to_en:
                results.update(cn_to_en[part])
    
    # Add common variations for state abbreviations
    us_states = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    }
    
    upper_region = region.upper()
    if upper_region in us_states:
        results.add(upper_region)  # Add abbreviation
        results.add(us_states[upper_region])  # Add full name
        # Also add with state suffix removed for cities like "Washington"
        if upper_region == 'DC':
            results.add('Washington')  # DC is usually Washington DC
    
    # Remove duplicates and empty strings
    return sorted(list(results))


def _calculate_risk_level(intensity: float) -> str:
    """calculateRisk Level"""
    if intensity > 7:
        return "极高"
    elif intensity > 5:
        return "高"
    elif intensity > 3:
        return "in"
    else:
        return "低"


def _format_search_results_v2(rows: list, columns: list, original_query: str) -> str:
    """FormatizationsearchResultV2 - UseETLfingerprint系统"""
    if not rows:
        return f"❌ notFoundWith '{original_query}' relatedEvent"
    
    output = [f"# 🔍 searchResult: '{original_query}'", ""]
    
    # 统计fingerprint覆盖situation
    fp_idx = columns.index('fingerprint') if 'fingerprint' in columns else -1
    with_fingerprint = sum(1 for row in rows if fp_idx >= 0 and row[fp_idx]) if fp_idx >= 0 else 0
    output.append(f"Found {len(rows)} Related Events (of which {with_fingerprint} 有ETLfingerprint)\n")
    
    for i, row in enumerate(rows, 1):
        data = dict(zip(columns, row))
        
        actor1 = data.get('Actor1Name', '') or 'Some country'
        actor2 = data.get('Actor2Name', '') or 'Other party'
        location = data.get('ActionGeo_FullName', '') or 'notknowLocation'
        date = data.get('SQLDATE', 'N/A')
        goldstein = data.get('GoldsteinScale', 0) or 0
        articles = data.get('NumArticles', 0) or 0
        event_root = str(data.get('EventRootCode', ''))[:2]
        
        # opt先UseETLgeneratedfingerprint，否ruleUseTemporary fingerprint
        fingerprint = data.get('fingerprint')
        if fingerprint:
            fp_display = f"📌 {fingerprint}"  # Standard fingerprint
            fp_type = "standard"
        else:
            gid = data.get('GlobalEventID', '0')
            fingerprint = f"EVT-{date}-{gid}"
            fp_display = f"📝 {fingerprint}"  # Temporary fingerprint
            fp_type = "temporary"
        
        # UseETLgeneratedEvent typelabel（e.g.if have）
        event_label = data.get('event_type_label')
        if not event_label:
            type_labels = {
                '01': 'statement', '02': 'appeal', '03': 'intention',
                '04': 'consultation', '05': 'cooperation', '06': 'aid',
                '07': 'aid', '08': 'aid', '09': 'concession',
                '10': 'demand', '11': 'dissatisfaction', '12': 'reject',
                '13': 'threat', '14': 'protest', '15': '武力展示',
                '16': 'degrade', '17': 'force', '18': 'friction',
                '19': 'conflict', '20': 'attack'
            }
            event_label = type_labels.get(event_root, 'Event')
        
        output.append(f"## {i}. {actor1} vs {actor2} [{event_label}]")
        output.append(f"**fingerprint** ({fp_type}): `{fp_display}`")
        
        # 显示ETLgeneratedSummary（e.g.if have）
        headline = data.get('headline')
        if headline:
            output.append(f"**Title**: {headline}")
        
        summary = data.get('summary')
        if summary:
            # 截断长Summary
            short_summary = summary[:100] + "..." if len(summary) > 100 else summary
            output.append(f"**Summary**: {short_summary}")
        
        output.append(f"**Time**: {date} | **Location**: {location}")
        output.append(f"**Conflict Index**: {goldstein:.1f} | **articlesamount**: {articles} ")
        output.append("")
    
    output.append("💡 **Hint**: Use `get_event_detail(fingerprint='...')` ViewEventDetails")
    output.append("📌 Standard fingerprint：ETLalready处理，信infocomplete | 📝 Temporary fingerprint：real-timegenerate，basic信info")
    return "\n".join(output)


def _format_regional_overview_precomputed(rows: list, region: str, 
                                          start_date, end_date,
                                          include_trend: bool, 
                                          include_risks: bool) -> str:
    """Formatization预calculatedistrict域Overview"""
    output = []
    output.append(f"# 🌍 {region} Regional Situation (pre-computed data)")
    output.append(f"**Timerange**: {start_date} ~ {end_date}")
    output.append("")
    
    # calculateaveragevalue
    total_events = sum(r[4] for r in rows)  # event_count
    avg_conflict = sum(r[5] for r in rows if r[5]) / len(rows) if rows else 0
    
    intensity = min(10, max(1, avg_conflict))
    risk_level = _calculate_risk_level(intensity)
    
    output.append(f"**Situation Score**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
    output.append(f"**Risk Level**: {risk_level}")
    output.append("")
    
    output.append("## 📈 Key Metrics")
    output.append(f"- Total Events: {total_events}")
    output.append(f"- day均Event: {total_events / len(rows):.1f}")
    output.append(f"- averageconflictintensity: {avg_conflict:.2f}")
    output.append("")
    
    if include_trend and len(rows) > 1:
        output.append("## 📊 Trend")
        # simpleTrend判断
        first_half = sum(r[5] for r in rows[:len(rows)//2] if r[5]) / (len(rows)//2) if rows else 0
        second_half = sum(r[5] for r in rows[len(rows)//2:] if r[5]) / (len(rows) - len(rows)//2) if rows else 0
        
        if second_half > first_half * 1.1:
            output.append("- conflictintensity: 📈 above升Trend")
        elif second_half < first_half * 0.9:
            output.append("- conflictintensity: 📉 under降Trend")
        else:
            output.append("- conflictintensity: ➡️ relatively stable")
        output.append("")
    
    if include_risks:
        output.append("## ⚠️ Risk Assessment")
        if intensity > 7:
            output.append("- **High risk**: conflictintensity持续高位")
        elif intensity > 5:
            output.append("- **Medium risk**: Local conflicts occur from time to time")
        else:
            output.append("- **Low risk**: Overall situation stable")
        output.append("")
    
    return "\n".join(output)


def _format_event_detail_from_raw(event_data: dict, fingerprint: str, params) -> str:
    """
    fromrawEventDataFormatizationDetails（无fingerprinttableData时）
    """
    actor1 = event_data.get('Actor1Name', '') or 'Some country'
    actor2 = event_data.get('Actor2Name', '') or 'Other party'
    location = event_data.get('ActionGeo_FullName', '') or 'notknowLocation'
    date = event_data.get('SQLDATE', 'N/A')
    goldstein = event_data.get('GoldsteinScale', 0) or 0
    articles = event_data.get('NumArticles', 0) or 0
    tone = event_data.get('AvgTone', 0) or 0
    gid = event_data.get('GlobalEventID', 'N/A')
    event_root = str(event_data.get('EventRootCode', ''))[:2]
    country = event_data.get('ActionGeo_CountryCode', 'XX')
    
    # Event typelabel
    type_labels = {
        '01': 'diplomacystatement', '02': 'diplomacyappeal', '03': '政策intention',
        '04': 'diplomacyconsultation', '05': '参Withcooperation', '06': '物资aid',
        '07': '人员aid', '08': '保护aid', '09': 'concession缓and',
        '10': '提出demand', '11': 'table达dissatisfaction', '12': 'reject反to',
        '13': 'threat警notification', '14': 'protest示威', '15': 'show of force',
        '16': 'relationship downgrade', '17': 'coercion', '18': 'militaryfriction',
        '19': '大规模conflict', '20': '武装attack'
    }
    event_label = type_labels.get(event_root, '其他Event')
    
    # Severity
    severity = min(10, max(1, abs(goldstein) * 2))
    if articles > 100:
        severity += 1
    severity = min(10, severity)
    
    output = []
    output.append(f"# 📰 {actor1} vs {actor2} [{event_label}]")
    output.append(f"**Fingerprint ID**: `{fingerprint}`")
    output.append(f"**GlobalEventID**: {gid}")
    output.append(f"**Time**: {date}")
    output.append(f"**Location**: {location} ({country})")
    output.append(f"**Type**: {event_label}")
    output.append(f"**Severity**: {'🔴' * int(severity / 2)}")
    output.append("")
    
    # real-timegenerateSummary
    intensity_desc = "Minor"
    if abs(goldstein) > 7:
        intensity_desc = "Severe"
    elif abs(goldstein) > 4:
        intensity_desc = "Moderate"
    
    coverage = ""
    if articles > 100:
        coverage = f"，受to广泛articles({articles})"
    elif articles > 10:
        coverage = f"，受toone定articles({articles})"
    
    summary = f"{actor1}With{actor2}in{location}发生{intensity_desc}interaction{coverage}。"
    output.append(f"**Summary**: {summary}")
    output.append("")
    
    if actor1 != 'Some country' or actor2 != 'Other party':
        actors = [a for a in [actor1, actor2] if a not in ['Some country', 'Other party']]
        if actors:
            output.append(f"**Actors**: {', '.join(actors)}")
            output.append("")
    
    # rawData
    output.append("## 📊 Data Metrics")
    output.append(f"- GoldsteinScale: {goldstein:.2f}")
    output.append(f"- NumArticles: {articles}")
    output.append(f"- AvgTone: {tone:.2f}")
    output.append(f"- QuadClass: {event_data.get('QuadClass', 'N/A')}")
    output.append("")
    
    # placeholder
    if params.include_causes or params.include_effects:
        output.append("## ⏱️ Causal Analysis")
        output.append("_(requires running causal chain analysis pipeline)_")
        output.append("")
    
    if params.include_related:
        output.append("## 🔗 Related Events")
        output.append("_(requires event similarity calculation)_")
        output.append("")
    
    return "\n".join(output)
