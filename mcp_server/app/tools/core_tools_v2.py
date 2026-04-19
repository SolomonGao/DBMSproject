"""
GDELT MCP Core Tools V2
Design Philosophy: From high-parameter queries to high-intent understanding

from:
  query_by_actor(actor="USA", date_start="2024-01-01", ...)
to:
  search_events(query="1monthWashington protests", max_results=10)

Tool count: 15 → 5
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Import database connection
from ..database import get_db_pool
from ..cache import query_cache
from ..queries import core_queries
from ..queries.query_utils import (
    sanitize_text,
    parse_time_hint,
    parse_region_input,
    calculate_risk_level,
)

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "events_table"


# ============================================================================
# Input Model Definitions
# ============================================================================

class SearchEventsInput(BaseModel):
    """Search events - supports natural language queries"""
    query: str = Field(
        ...,
        description="Natural language query，e.g.'1monthWashington protests'、'inEast recentconflict'"
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
    format: Literal["markdown", "json"] = Field(
        default="markdown",
        description="Output format: markdown (for LLM) or json (for API)"
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
    """DashboardDatainput"""
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
    format: Literal["markdown", "json"] = Field(
        default="markdown",
        description="Output format: markdown (for LLM) or json (for API)"
    )


class TimeSeriesInput(BaseModel):
    """Timeseriesanalysisinput"""
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
        description="Timegranularitydegree: day(day), week(week), month(month)"
    )
    format: Literal["markdown", "json"] = Field(
        default="markdown",
        description="Output format: markdown (for LLM) or json (for API)"
    )


class GeoHeatmapInput(BaseModel):
    """placeheatmapmapinput"""
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
        description="sitstandardPrecision(smalldatapositiondata)，exceedbigPrecisionexceedhigh"
    )
    format: Literal["markdown", "json"] = Field(
        default="markdown",
        description="Output format: markdown (for LLM) or json (for API)"
    )


# ============================================================================
# toolNotebookfunctiondata
# ============================================================================

def register_core_tools(mcp: FastMCP):
    """NotebookcoretoolV2toMCPservicehandler"""
    
    @mcp.tool()
    async def search_events(params: SearchEventsInput) -> str:
        """
        Intelligent event search - core entry tool
        
        Example:
        - "1monthWashington protests" → time_hint=2024-01, location_hint=Washington, event_type=protest
        - "ineastmilitaryconflict" → location_hint=Middle East, event_type=conflict
        - "inUSeconomictowardcome" → query="China US economic"
        """
        # parseTimeHint（e.g.resultnohasprovide，tryfrom query providefetch）
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
        
        try:
            pool = await get_db_pool()
            rows = await core_queries.query_search_events(
                pool, params.query, time_hint, params.location_hint,
                params.event_type, params.max_results
            )
            
            if not rows:
                date_start, date_end = parse_time_hint(time_hint)
                return f"❌ notFoundWith '{params.query}' relatedEvent（Timerange: {date_start} ~ {date_end}）"
            
            if params.format == "json":
                return json.dumps({"data": rows, "query": params.query, "total": len(rows)}, default=str, ensure_ascii=False)
            
            # Convert dict rows to tuples for legacy formatter
            columns = list(rows[0].keys()) if rows else []
            row_tuples = [tuple(r.get(c) for c in columns) for r in rows]
            return _format_search_results_v2(row_tuples, columns, params.query)
            
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
        try:
            pool = await get_db_pool()
            result = await core_queries.query_event_detail(pool, params.fingerprint)
            
            if result is None:
                return f"⚠️ Event fingerprint `{params.fingerprint}` not yet generated or does not exist\n\nHint: use search_events to search again。"
            
            # Temporary fingerprint: result is a flat dict of event data
            if isinstance(result, dict) and "event_data" not in result:
                return _format_event_detail_from_raw(result, params.fingerprint, params)
            
            # Standard fingerprint: structured result
            fp = result
            event_data = fp.get("event_data", {})
            output = []
            output.append(f"# 📰 {fp.get('headline') or 'EventDetails'}")
            output.append(f"**Fingerprint ID**: `{fp.get('fingerprint')}`")
            output.append(f"**GlobalEventID**: {event_data.get('GlobalEventID', 'N/A')}")
            output.append(f"**Time**: {event_data.get('SQLDATE', 'N/A')}")
            output.append(f"**Location**: {fp.get('location_name') or event_data.get('ActionGeo_FullName', 'N/A')}")
            output.append(f"**Type**: {fp.get('event_type_label') or 'N/A'}")
            output.append(f"**Severity**: {'🔴' * int((fp.get('severity_score') or 5) / 2)}")
            output.append("")
            
            if fp.get('summary'):
                output.append(f"**Summary**: {fp['summary']}")
                output.append("")
            
            if fp.get('key_actors'):
                try:
                    actors = json.loads(fp['key_actors'])
                    if actors:
                        output.append(f"**Actors**: {', '.join(actors)}")
                        output.append("")
                except Exception:
                    pass
            
            output.append("## 📊 Data Metrics")
            output.append(f"- GoldsteinScale: {event_data.get('GoldsteinScale', 'N/A')}")
            output.append(f"- NumArticles: {event_data.get('NumArticles', 'N/A')}")
            output.append(f"- AvgTone: {event_data.get('AvgTone', 'N/A')}")
            output.append("")
            
            if params.include_causes or params.include_effects:
                output.append("## ⏱️ Causal Analysis")
                output.append("_(requires running causal chain analysis pipeline)_")
                output.append("")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Failed to get event details: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_regional_overview(params: GetRegionalOverviewInput) -> str:
        """
        GetRegional SituationOverview - insightSummaryandnon-rawData
        
        Example:
        - region="Middle East", time_range="week"
        - region="China", time_range="month", include_risks=true
        """
        try:
            pool = await get_db_pool()
            result = await core_queries.query_regional_overview(pool, params.region, params.time_range)
            
            start_date = result["start"]
            end_date = result["end"]
            output = []
            output.append(f"# 🌍 {params.region} Regional Situation")
            output.append(f"**Timerange**: {start_date} ~ {end_date}")
            output.append("")
            
            if result["source"] == "precomputed":
                # Format precomputed rows (simplified)
                rows = result["rows"]
                total_events = sum(r.get("event_count", 0) for r in rows)
                avg_conflict = sum(r.get("conflict_intensity", 0) for r in rows if r.get("conflict_intensity")) / len(rows) if rows else 0
                intensity = min(10, max(1, avg_conflict))
                output.append(f"**Situation Score**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
                output.append(f"**Risk Level**: {calculate_risk_level(intensity)}")
                output.append("")
                output.append("## 📈 Key Metrics")
                output.append(f"- Total Events: {total_events}")
                output.append("")
                return "\n".join(output)
            
            # Realtime result
            summary = result.get("summary", {})
            total = summary.get("total", 0)
            avg_goldstein = summary.get("avg_goldstein", 0) or 0
            conflicts = summary.get("conflicts", 0) or 0
            
            if total:
                intensity = min(10, max(1, abs(avg_goldstein)))
                output.append(f"**Situation Score**: {intensity:.1f}/10 {'🔴' if intensity > 7 else '🟡' if intensity > 4 else '🟢'}")
                output.append(f"**Risk Level**: {calculate_risk_level(intensity)}")
                output.append("")
                output.append("## 📈 Key Metrics")
                output.append(f"- Total Events: {total}")
                output.append(f"- Conflict Events: {conflicts} ({conflicts/total*100:.1f}%)")
                output.append(f"- Average Goldstein Index: {avg_goldstein:.2f}")
                output.append("")
                
                hot_events = result.get("hot_events", [])
                if hot_events:
                    output.append("## 🔥 Hot Events")
                    for i, evt in enumerate(hot_events, 1):
                        actor1 = evt.get("Actor1Name", "Unknown")
                        actor2 = evt.get("Actor2Name", "Unknown")
                        location = evt.get("ActionGeo_FullName", params.region)
                        output.append(f"{i}. {actor1} vs {actor2} ({location})")
                    output.append("")
            else:
                output.append("⚠️ No related events found in this time period")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Failed to get regional overview: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_hot_events(params: GetHotEventsInput) -> str:
        """
        GetdailyHot Eventsrecommend
        
        Example:
        - date="2024-01-15", top_n=5
        - region_filter="Asia", top_n=10
        """
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            events = await core_queries.query_hot_events(pool, query_date, params.region_filter, params.top_n)
            
            if not events:
                return f"📭 {query_date} notFoundHot Events"
            
            output = []
            output.append(f"# 🔥 {query_date} Hot Events TOP {len(events)}")
            output.append("")
            
            for i, evt in enumerate(events, 1):
                fingerprint = evt.get("fingerprint", "")
                headline = evt.get("headline", "")
                if not headline or headline in ['One party vs Other party', ' vs ', 'NULL vs NULL']:
                    gid = evt.get("GlobalEventID", fingerprint.split('-')[-1] if '-' in str(fingerprint) else 'unknown')
                    headline = f"Event #{gid}"
                location = evt.get("location_name") or evt.get("ActionGeo_FullName", "Unknown location")
                severity = evt.get("severity_score") or 5
                num_articles = evt.get("NumArticles") or 0
                fp_type = evt.get("fp_type", "unknown")
                fp_badge = "📌" if fp_type == 'standard' else "📝"
                
                output.append(f"## {i}. {headline}")
                output.append(f"**fingerprint**: {fp_badge} `{fingerprint}` {'(standard)' if fp_type == 'standard' else '(temporary)'}")
                output.append(f"**Location**: {location} | **Severity**: {'🔴' * int(severity / 2)}")
                output.append(f"**articlesamount**: {num_articles} ")
                summary = evt.get("summary", "")
                if summary and len(str(summary)) > 10:
                    output.append(f"**Summary**: {str(summary)[:100]}...")
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
        """
        try:
            pool = await get_db_pool()
            rows = await core_queries.query_top_events(
                pool, params.start_date, params.end_date,
                params.region_filter, params.event_type, params.top_n
            )
            
            if not rows:
                return f"📭 {params.start_date} ~ {params.end_date} No events matching criteria found during this period"
            
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
                gid = row.get("GlobalEventID")
                date = row.get("SQLDATE")
                actor1 = row.get("Actor1Name") or 'Some country'
                actor2 = row.get("Actor2Name") or 'Other party'
                location = row.get("ActionGeo_FullName")
                event_root = row.get("EventRootCode")
                goldstein = row.get("GoldsteinScale")
                articles = row.get("NumArticles")
                tone = row.get("AvgTone")
                
                temp_fp = f"EVT-{date}-{gid}"
                type_labels = {
                    '01': 'statement', '02': 'appeal', '03': 'intention',
                    '04': 'consultation', '05': 'cooperation', '06': 'aid',
                    '07': 'aid', '08': 'aid', '09': 'concession',
                    '10': 'demand', '11': 'dissatisfaction', '12': 'reject',
                    '13': 'threat', '14': 'protest', '15': 'force',
                    '16': 'degrade', '17': 'force', '18': 'friction',
                    '19': 'conflict', '20': 'attack'
                }
                event_label = type_labels.get(str(event_root)[:2], 'Event') if event_root else 'Event'
                hot_score = (articles or 0) * abs(goldstein or 0)
                location_short = (location or 'unknown')[:15]
                title = f"{actor1[:10]} vs {actor2[:10]}"
                
                output.append(f"| {i} | `{temp_fp}` | {title} [{event_label}] | {hot_score:.0f} | {date} | {location_short} |")
                detail_list.append({
                    'rank': i, 'fingerprint': temp_fp, 'title': title,
                    'event_label': event_label, 'date': date, 'location': location,
                    'hot_score': hot_score, 'articles': articles,
                    'goldstein': goldstein, 'tone': tone
                })
            
            output.append("")
            output.append("## Detailed Information")
            output.append("")
            for d in detail_list[:5]:
                output.append(f"### {d['rank']}. {d['title']} [{d['event_label']}]")
                output.append(f"- **fingerprint**: `{d['fingerprint']}`")
                output.append(f"- **Time**: {d['date']} | **Location**: {d['location']}")
                output.append(f"- **Heat**: {d['hot_score']:.0f}")
                output.append(f"- **Goldstein**: {d['goldstein']:.2f} | **Tone**: {d['tone']:.2f}")
                output.append("")
            
            if len(detail_list) > 5:
                output.append(f"_... also have {len(detail_list) - 5} Event_")
                output.append("")
            
            output.append("💡 **ViewEventDetails**: `get_event_detail(fingerprint='EVT-YYYY-MM-DD-GID')`")
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"GetTopEventfailed: {e}")
            return f"❌ Query failed: {str(e)}"

    @mcp.tool()
    async def get_daily_brief(params: GetDailyBriefInput) -> str:
        """
        Getdailysimplereport - categorynews-likeSummary
        
        Example:
        - date="2024-01-15", format="summary"
        - region_focus="global", format="executive"
        """
        query_date = params.date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # tryfromprecalculatetableGet
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
                    output.append(f"# 📰 {query_date} allglobeEventsimplereport")
                    output.append("")
                    
                    # onesentencewordsummary
                    total = data.get('total_events', 0)
                    conflict = data.get('conflict_events', 0)
                    conflict_pct = (conflict / max(total, 1)) * 100
                    goldstein = data.get('avg_goldstein', 0) or 0
                    
                    output.append(f"📊 **Overview**: Today recorded a total of **{total:,}** occurrencecountryborderEvent，")
                    output.append(f"Conflict Events {conflict} occurrence ({conflict_pct:.1f}%)，")
                    output.append(f"Average Goldstein Indexfor {goldstein:.2f}")
                    output.append("")
                    
                    # according toformatreturndifferentdetailedprocessdegree
                    if params.format == 'summary':
                        # Summary version
                        if brief and data.get('hot_event_fingerprints'):
                            hot_fps = json.loads(data['hot_event_fingerprints']) if isinstance(data['hot_event_fingerprints'], str) else data['hot_event_fingerprints']
                            output.append("## 🔥 Today's Hot Events")
                            for fp in hot_fps[:3]:
                                output.append(f"- `{fp}`")
                            output.append("")
                        
                        output.append("💡 _Use `get_hot_events` Getdetailedhotinfoinfo_")
                        
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
                                        output.append(f"- {name}: {count} time")
                                    output.append("")
                            except Exception:
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
                            except Exception:
                                pass
                    
                    elif params.format == 'executive':
                        # execrowSummaryversion
                        output.append("## 📋 execrowSummary")
                        trend = "⚠️ conflict trend rising" if goldstein < -3 else "✅ situation relatively stable"
                        output.append(f"- {trend}")
                        output.append(f"- Eventsecretdegree: {total/1000:.1f}K/day")
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
        【RAG semanticsearch】querynewsknowknowledgelibraryGettruerealarticlesdetails
        
        When users need to know:
        - Eventspecificoccurrencebecause
        - Specific demands of crowds
        - Police response
        - Eventdetailedbackgroundscenario
        
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
            db_path = str(Path(__file__).resolve().parents[3] / 'chroma_db')
            
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
                return "❌ newssetnotFound，pleasefirstBuild knowledge base"
            
            # Execute semantic search
            results = collection.query(
                query_texts=[params.query],
                n_results=params.n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return f"📭 Not found in knowledge base related to '{params.query}' relatednewsarticles。\n\nSuggestions:\n1. Try different English keywords\n2. Check if knowledge base is built (Run start_kb.py)"
            
            # FormatizationResult
            output = [f"# 🔍 RAG semanticsearchResult: '{params.query}'\n"]
            output.append(f"Found {len(results['documents'][0])} related news:\n")
            
            for i in range(len(results['documents'][0])):
                doc_text = results['documents'][0][i]
                event_id = results['ids'][0][i]
                url = results['metadatas'][0][i].get('source_url', 'Unknown')
                date = results['metadatas'][0][i].get('date', 'Unknown')
                
                # interceptfetchbefore1000character
                snippet = doc_text[:1000] + "..." if len(doc_text) > 1000 else doc_text
                
                output.append(f"## 📰 Result {i+1}")
                output.append(f"- **Event ID**: {event_id}")
                output.append(f"- **Date**: {date}")
                output.append(f"- **Source**: {url}")
                output.append(f"\n**withincontentSummary**:\n{snippet}\n")
            
            return "\n".join(output)
            
        except ImportError:
            return "❌ ChromaDB notsafeinstall，pleaseRun: pip install chromadb sentence-transformers"
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return f"❌ RAG search failed: {str(e)}"
    
    
    # ========================================================================
    # streamingquerytool (from txx_docker)
    # ========================================================================
    
    @mcp.tool()
    async def stream_events(params: StreamQueryInput) -> str:
        """
        【streamingquery】handleprocessbigamountEventData，withinmemory-friendly
        
        whenneedhandleprocessbigamountEventwhenUse（e.g."analysisallyearallprotestEvent"），
        Streaming read avoids loading everything into memory at once。
        
        Applicable scenarios:
        - Preview before data export
        - bigamountEventstatisticsanalysis
        - Memory-sensitive environments
        
        Example:
        - actor_name="Protest" - findallprotestRelated Events
        - actor_name="USA" + Timerange - UScountryallyearEvent
        """
        try:
            pool = await get_db_pool()
            
            output = [f"# 🔍 streamingqueryResult: {params.actor_name}", ""]
            output.append("| Date | Actor1 | Actor2 | Goldstein | Tone | location |")
            output.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in core_queries.query_stream_events(
                pool, params.actor_name, params.start_date, params.end_date,
                max_results=params.max_results
            ):
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
                    output.append("| ... | (more results...) | ... | ... | ... | ... |")
                    break
            
            output.append(f"\n*Total returned {count} items (streaming read)*")
            return "\n".join(output)
            
        except asyncio.TimeoutError:
            logger.error("streamingQuery failed: Query timeout (30s)")
            return "❌ streamingQuery failed: Query timeout (30s). The dataset is too large for a fuzzy LIKE scan. Try narrowing the date range or using a more specific actor name."
        except Exception as e:
            logger.error(f"streamingQuery failed: {e}")
            return f"❌ streamingQuery failed: {str(e)}"

    # =======================================================================
    # optizationanalysistool (androwquery + streaminghandleprocess)
    # =======================================================================
    
    @mcp.tool()
    async def get_dashboard(params: DashboardInput) -> str:
        """
        [Optimized] Dashboard data - concurrent multi-dimensional statistics
        
        simultaneouslyreturn：dailyTrend、Top Actors、placeprocessdistribution、Event typedistribution、comprehensivecombinestatistics
        3-5x faster than serial queries。
        
        Applicable scenarios:
        - fastspeedOverviewsomesegmentTimewholebodystatetrend
        - Get multi-dimensional statistics
        - Dashboard display
        """
        try:
            pool = await get_db_pool()
            dashboard = await core_queries.query_dashboard(
                pool, params.start_date, params.end_date
            )
            
            if params.format == "json":
                return json.dumps(dashboard, default=str, ensure_ascii=False)
            
            lines = ["# 📊 DashboardData\n"]
            
            summary = dashboard.get("summary_stats", {})
            if "data" in summary and summary["data"]:
                s = summary["data"][0]
                lines.append(f"**Statistics Period**: {params.start_date} to {params.end_date}")
                lines.append(f"- totalEventdata: {s.get('total_events', 0):,}")
                lines.append(f"- uniqueActors: {s.get('unique_actors', 0):,}")
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
            
            # calculatetotalconsumewhen（onlystatisticscharacterclassicTypeResult）
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
        【optization】advancedTimeseriesanalysis - Datalibraryendaggregate
        
        supportday/week/monthgranularitydegreeTimeTrendanalysis，All aggregation completed on database side，
        onlytransmittransportResult，extremebigreducenetworkopensell。
        
        Applicable scenarios:
        - analysisEventfollowTimevariableizationTrend
        - tothandifferentTimegranularitydegreemodelformat
        - Identify periodic patterns
        """
        try:
            pool = await get_db_pool()
            results = await core_queries.query_time_series(
                pool, params.start_date, params.end_date, params.granularity
            )
            
            if not results:
                return "📭 notFoundData"
            
            if params.format == "json":
                return json.dumps(results, default=str, ensure_ascii=False)
            
            lines = [f"# 📈 Timeseriesanalysis ({params.granularity})\n"]
            lines.append(f"**Timerange**: {params.start_date} to {params.end_date}")
            lines.append(f"**Data points**: {len(results)} ")
            lines.append("")
            
            for row in results[:20]:  # mostmultidisplay20
                period = row.get("period")
                lines.append(f"### {period}")
                lines.append(f"- Eventdata: {row.get('event_count', 0):,}")
                lines.append(f"- Conflict ratio: {row.get('conflict_pct', 0)}%")
                lines.append(f"- Cooperation ratio: {row.get('cooperation_pct', 0)}%")
                lines.append(f"- Average Goldstein: {row.get('avg_goldstein', 0)}")
                lines.append("")
            
            if len(results) > 20:
                lines.append(f"_... also have {len(results) - 20} Timeweekperiod_")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Timeseriesanalysisfailed: {e}")
            return f"❌ analysisfailed: {str(e)}"
    
    
    @mcp.tool()
    async def get_geo_heatmap(params: GeoHeatmapInput) -> str:
        """
        [Optimized] Geographic heatmap data - grid aggregation
        
        Aggregate nearby coordinates to grids, reducing frontend rendering pressure。
        returnhotlatlondegree、intensity、averageconflictvalueetc.infoinfo。
        
        Applicable scenarios:
        - inplacemapabovecanviewizationEventdistribution
        - Identify hot spot areas
        - Geographic density analysis
        """
        try:
            pool = await get_db_pool()
            results = await core_queries.query_geo_heatmap(
                pool, params.start_date, params.end_date, params.precision
            )
            
            if not results:
                return "📭 notFoundplaceprocessData"
            
            heatmap_data = [
                {
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "intensity": int(row["intensity"]),
                    "avg_conflict": float(row["avg_conflict"]) if row["avg_conflict"] else None,
                    "location": row["sample_location"]
                }
                for row in results
            ]
            
            if params.format == "json":
                return json.dumps(heatmap_data, default=str, ensure_ascii=False)
            
            return f"""# 🗺️ Geographic Heatmap Data

**Timerange**: {params.start_date} to {params.end_date}
**Precision**: {params.precision} decimal places
**Hot spot count**: {len(heatmap_data)}

```json
{json.dumps(heatmap_data[:10], indent=2, ensure_ascii=False)}
```

*completeDatatotal {len(heatmap_data)} item(s)*

**Description**: 
- `intensity`: thisgridwithinEventdataamount
- `avg_conflict`: Average conflict index (GoldsteinScale)
- Use `lat` and `lng` can mark hotspots on map
"""
        except Exception as e:
            logger.error(f"heatmapQuery failed: {e}")
            return f"❌ Query failed: {str(e)}"
    
    
    @mcp.tool()
    async def stream_query_events(params: StreamQueryInput) -> str:
        """
        [Optimized] Streaming query - process large data
        
        Useservicehandlerendtravelstandardstreaming readData，withinmemory usagestablefix，
        Can handle regardless of data volume。
        
        Applicable scenarios:
        - needexportbigamountEvent
        - Large data volume statistical analysis
        - Memory-sensitive environment
        
        With `stream_events` difference:
        - thistoolbyActorsnametitlesearch
        - supports fuzzy matching Actor1Name and Actor2Name
        """
        try:
            pool = await get_db_pool()
            
            lines = [f"# 🔍 streamingqueryResult: {params.actor_name}\n"]
            lines.append("| Date | Actor1 | Actor2 | Goldstein | Tone | location |")
            lines.append("|------|--------|--------|-----------|------|------|")
            
            count = 0
            async for row in core_queries.query_stream_events(
                pool, params.actor_name, params.start_date, params.end_date,
                max_results=params.max_results
            ):
                # Use sanitize_text preventstop Markdown tablegridbybreakbad
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
                    lines.append("| ... | (updatemultiResultinterceptbreak) | ... | ... | ... | ... |")
                    break
            
            lines.append(f"\n*Total returned {count} item(s)Result (streaming read)*")
            return "\n".join(lines)
            
        except asyncio.TimeoutError:
            logger.error("streamingQuery failed: Query timeout (30s)")
            return "❌ streamingQuery failed: Query timeout (30s). The dataset is too large for a fuzzy LIKE scan. Try narrowing the date range or using a more specific actor name."
        except Exception as e:
            logger.error(f"streamingQuery failed: {e}")
            return f"❌ streamingQuery failed: {str(e)}"

    logger.info("✅ Core tools V2 registered (6basictool + RAG + 4optizationanalysistool)")


# ============================================================================
# Helper Functions
# ============================================================================













def _format_search_results_v2(rows: list, columns: list, original_query: str) -> str:
    """FormatizationsearchResultV2 - UseETLfingerprintsystem"""
    if not rows:
        return f"❌ notFoundWith '{original_query}' relatedEvent"
    
    output = [f"# 🔍 searchResult: '{original_query}'", ""]
    
    # statisticsfingerprintoverridesituation
    fp_idx = columns.index('fingerprint') if 'fingerprint' in columns else -1
    with_fingerprint = sum(1 for row in rows if fp_idx >= 0 and row[fp_idx]) if fp_idx >= 0 else 0
    output.append(f"Found {len(rows)} Related Events (of which {with_fingerprint} hasETLfingerprint)\n")
    
    for i, row in enumerate(rows, 1):
        data = dict(zip(columns, row))
        
        actor1 = data.get('Actor1Name', '') or 'Some country'
        actor2 = data.get('Actor2Name', '') or 'Other party'
        location = data.get('ActionGeo_FullName', '') or 'notknowLocation'
        date = data.get('SQLDATE', 'N/A')
        goldstein = data.get('GoldsteinScale', 0) or 0
        articles = data.get('NumArticles', 0) or 0
        event_root = str(data.get('EventRootCode', ''))[:2]
        
        # optfirstUseETLgeneratedfingerprint，noruleUseTemporary fingerprint
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
                '13': 'threat', '14': 'protest', '15': 'forceexpandshow',
                '16': 'degrade', '17': 'force', '18': 'friction',
                '19': 'conflict', '20': 'attack'
            }
            event_label = type_labels.get(event_root, 'Event')
        
        output.append(f"## {i}. {actor1} vs {actor2} [{event_label}]")
        output.append(f"**fingerprint** ({fp_type}): `{fp_display}`")
        
        # displayETLgeneratedSummary（e.g.if have）
        headline = data.get('headline')
        if headline:
            output.append(f"**Title**: {headline}")
        
        summary = data.get('summary')
        if summary:
            # interceptbreaklongSummary
            short_summary = summary[:100] + "..." if len(summary) > 100 else summary
            output.append(f"**Summary**: {short_summary}")
        
        output.append(f"**Time**: {date} | **Location**: {location}")
        output.append(f"**Conflict Index**: {goldstein:.1f} | **articlesamount**: {articles} ")
        output.append("")
    
    output.append("💡 **Hint**: Use `get_event_detail(fingerprint='...')` ViewEventDetails")
    output.append("📌 Standard fingerprint：ETLalreadyhandleprocess，infoinfocomplete | 📝 Temporary fingerprint：real-timegenerate，basicinfoinfo")
    return "\n".join(output)


def _format_event_detail_from_raw(event_data: dict, fingerprint: str, params) -> str:
    """
    fromrawEventDataFormatizationDetails（nofingerprinttableDatawhen）
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
        '01': 'diplomacystatement', '02': 'diplomacyappeal', '03': 'policyintention',
        '04': 'diplomacyconsultation', '05': 'paramWithcooperation', '06': 'suppliesaid',
        '07': 'personnelaid', '08': 'protectaid', '09': 'concessionslowand',
        '10': 'provideoutputdemand', '11': 'tablereachdissatisfaction', '12': 'rejectantito',
        '13': 'threatalertnotification', '14': 'protestshowthreat', '15': 'show of force',
        '16': 'relationship downgrade', '17': 'coercion', '18': 'militaryfriction',
        '19': 'bigrulemodelconflict', '20': 'militaryinstallattack'
    }
    event_label = type_labels.get(event_root, 'otherEvent')
    
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
        coverage = f"，accepttowidespreadarticles({articles})"
    elif articles > 10:
        coverage = f"，accepttoonefixarticles({articles})"
    
    summary = f"{actor1}With{actor2}in{location}occur{intensity_desc}interaction{coverage}。"
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
