"""
GDELT Agent — LangGraph ReAct Agent for conversational analysis.

Architecture:
- Uses LangGraph's create_react_agent for robust tool-calling loops
- Tools are direct Python functions wrapping DataService (no MCP process overhead)
- Supports conversation memory via thread_id
- Streaming events for real-time thinking steps

Design choice: Tools directly call DataService instead of going through MCP.
Reason: Faster (no stdio/sse overhead), more reliable (no process management),
and the Agent layer is logically distinct from the MCP tool-definition layer.
"""

import asyncio
import json
import os
import re
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta

import httpx
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from langgraph.prebuilt import create_react_agent

from backend.services.data_service import DataService

# ---------------------------------------------------------------------------
# Monkey-patch langchain-openai to preserve Kimi API's reasoning_content
# ---------------------------------------------------------------------------
# Kimi's coding API (api.kimi.com/coding/v1) ALWAYS returns reasoning_content
# for assistant messages. LangChain drops this field during message conversion.
# On multi-turn conversations (after tool calls), the API returns 400 because
# reasoning_content is missing from the assistant message we send back.
# NOTE: extra_body={"thinking": False} causes 400 on this endpoint, so we
# must preserve reasoning_content instead of disabling it.
# ---------------------------------------------------------------------------
import langchain_openai.chat_models.base as _lc_base
from langchain_core.messages import AIMessage

_original_convert_dict_to_message = _lc_base._convert_dict_to_message
_original_convert_message_to_dict = _lc_base._convert_message_to_dict

def _patched_convert_dict_to_message(_dict):
    msg = _original_convert_dict_to_message(_dict)
    if isinstance(msg, AIMessage) and "reasoning_content" in _dict:
        msg.additional_kwargs["reasoning_content"] = _dict["reasoning_content"]
    return msg

def _patched_convert_message_to_dict(message, api="chat/completions"):
    d = _original_convert_message_to_dict(message, api)
    if isinstance(message, AIMessage) and "reasoning_content" in message.additional_kwargs:
        d["reasoning_content"] = message.additional_kwargs["reasoning_content"]
    return d

_lc_base._convert_dict_to_message = _patched_convert_dict_to_message
_lc_base._convert_message_to_dict = _patched_convert_message_to_dict


SYSTEM_PROMPT = """You are GDELT Analyst, an intelligent assistant specialized in analyzing the GDELT 2.0 North American event database.

Your capabilities:
1. Answer natural language questions about geopolitical events
2. Retrieve event details, trends, and statistics
3. Compare regions, actors, or time periods
4. Explain causes and context using news semantic search
5. Analyze true bilateral country-pair trends using Actor1CountryCode/Actor2CountryCode
6. Forecast future event intensity with the trained Transformer Hawkes Process (THP) model

Guidelines:
- Be concise but insightful (2-4 paragraphs max)
- When presenting data, highlight the most important findings
- Always cite specific numbers, dates, and actor names when available
- If data is ambiguous, say so clearly
- Use the available tools to fetch real data rather than hallucinating
- For bilateral country questions such as United States vs Canada, call get_country_pair_trends before using broad regional summaries.
- For forecast, prediction, risk outlook, or next-N-day questions, call get_event_forecast and mention the forecast source, model, prediction interval, and peak risk day.
- For "why", "cause", "background", "context", or narrative explanation questions, call search_news_context first, then combine the retrieved context with structured SQL statistics.
- Treat ChromaDB RAG results as semantic context and examples, not as exact aggregate counts.

When comparing two things (e.g., Washington vs New York), fetch data for BOTH before analyzing.
"""


class ThinkingTracker:
    """Collects thinking steps for frontend display."""
    
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
    
    def add(self, step_type: str, content: str = "", data: Optional[Dict] = None):
        self.steps.append({
            "type": step_type,
            "content": content,
            "data": data or {},
            "timestamp": time.time(),
        })


class GDELTAgent:
    """
    Conversational Agent for GDELT analysis.
    
    Usage:
        agent = GDELTAgent(data_service)
        response = await agent.chat("What happened in Washington last month?")
    """
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.tracker: Optional[ThinkingTracker] = None
        
        # Build tools
        self.tools = self._build_tools()
        
        # Build LLM
        self.llm = self._build_llm()
        
        # Build graph agent (stateless — history is managed by frontend)
        self.graph = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SYSTEM_PROMPT,
        )
    
    def _build_llm(self) -> BaseChatModel:
        """Initialize LLM from environment configuration."""
        provider = os.getenv("LLM_PROVIDER", "kimi").lower()
        
        # Map provider to config
        configs = {
            "kimi": {
                "api_key": os.getenv("KIMI_CODE_API_KEY", os.getenv("MOONSHOT_API_KEY", "")),
                "base_url": os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1"),
                "model": os.getenv("LLM_MODEL", "kimi-k2-0905-preview"),
            },
            "moonshot": {
                "api_key": os.getenv("MOONSHOT_API_KEY", ""),
                "base_url": os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1"),
                "model": os.getenv("LLM_MODEL", "kimi-k2-0905-preview"),
            },
            "claude": {
                "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                "base_url": os.getenv("LLM_BASE_URL", "https://api.anthropic.com/v1"),
                "model": os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022"),
            },
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
                "model": os.getenv("LLM_MODEL", "gpt-4o"),
            },
        }
        
        cfg = configs.get(provider, configs["kimi"])
        
        if not cfg["api_key"]:
            raise ValueError(f"API key not set for provider: {provider}")
        
        # Kimi Coding API requires Claude Code identity headers.
        # Verified: "claude-code/1.0" + "X-Client-Name: claude-code" returns 200 OK.
        async def _inject_claude_headers(request: httpx.Request):
            request.headers["User-Agent"] = "claude-code/1.0"
            request.headers["X-Client-Name"] = "claude-code"

        http_async_client = httpx.AsyncClient(
            event_hooks={"request": [_inject_claude_headers]}
        )
        
        return ChatOpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model=cfg["model"],
            temperature=0.3,
            max_tokens=4096,
            http_async_client=http_async_client,
        )

    def _extract_country_pair(self, message: str) -> Optional[tuple[str, str]]:
        country_patterns = [
            ("United States", r"\b(united states|usa|u\.s\.|us|america)\b"),
            ("Canada", r"\b(canada|canadian|can)\b"),
            ("Mexico", r"\b(mexico|mexican|mex)\b"),
            ("China", r"\b(china|chinese|chn)\b"),
            ("Russia", r"\b(russia|russian|rus)\b"),
            ("Ukraine", r"\b(ukraine|ukrainian|ukr)\b"),
            ("Israel", r"\b(israel|israeli|isr)\b"),
        ]
        found: List[str] = []
        lowered = message.lower()
        for country, pattern in country_patterns:
            if re.search(pattern, lowered) and country not in found:
                found.append(country)
        if len(found) >= 2:
            return found[0], found[1]
        return None

    def _extract_year_range(self, message: str) -> Optional[tuple[str, str]]:
        match = re.search(r"\b(20\d{2})\b", message)
        if not match:
            return None
        year = match.group(1)
        return f"{year}-01-01", f"{year}-12-31"

    def _extract_iso_date(self, message: str) -> Optional[str]:
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        return match.group(1) if match else None

    def _extract_event_type(self, message: str) -> str:
        lowered = message.lower()
        if "conflict" in lowered:
            return "conflict"
        if "cooperation" in lowered or "cooperative" in lowered:
            return "cooperation"
        if "protest" in lowered:
            return "protest"
        return "all"

    def _extract_forecast_days(self, message: str) -> int:
        match = re.search(r"\bnext\s+(\d{1,2})\s+days?\b", message.lower())
        if not match:
            match = re.search(r"\b(\d{1,2})[-\s]?day\b", message.lower())
        if not match:
            return 7
        return max(1, min(int(match.group(1)), 60))

    def _format_country_pair_reply(self, result: Dict[str, Any]) -> str:
        summary = result.get("summary", {}) or {}
        total = int(summary.get("total_events") or 0)
        cooperation = int(summary.get("cooperation_events") or 0)
        conflict = int(summary.get("conflict_events") or 0)
        neutral = int(summary.get("neutral_events") or 0)
        peak_conflict = result.get("peak_conflict_day") or {}
        peak_cooperation = result.get("peak_cooperation_day") or {}
        country_a = result.get("country_a")
        country_b = result.get("country_b")
        start_date = result.get("start_date")
        end_date = result.get("end_date")

        return (
            f"From {start_date} to {end_date}, GDELT records {total:,} bilateral events "
            f"between {country_a} and {country_b}. Cooperation is the dominant pattern: "
            f"{cooperation:,} cooperative events ({summary.get('cooperation_pct', 0)}%) versus "
            f"{conflict:,} conflict events ({summary.get('conflict_pct', 0)}%), with "
            f"{neutral:,} neutral events. The average Goldstein score is "
            f"{summary.get('avg_goldstein', 'n/a')}, so the overall relationship is coded as "
            f"{summary.get('dominant_trend', 'mixed')}.\n\n"
            f"The strongest conflict spike is {peak_conflict.get('period', 'n/a')} "
            f"({peak_conflict.get('conflict_pct', 'n/a')}% conflict), while the strongest "
            f"cooperation day is {peak_cooperation.get('period', 'n/a')} "
            f"({peak_cooperation.get('cooperation_pct', 'n/a')}% cooperation). "
            f"This answer uses the fast bilateral country-pair path based on "
            f"Actor1CountryCode/Actor2CountryCode, not broad regional keyword matching."
        )

    def _format_forecast_reply(self, result: Dict[str, Any]) -> str:
        forecast = result.get("forecast", []) or []
        summary = result.get("summary", {}) or {}
        checkpoint = result.get("checkpoint", {}) or {}
        first = forecast[0] if forecast else {}
        peak_date = summary.get("peak_risk_date") or first.get("date", "n/a")
        model = result.get("model", "THP")
        target = result.get("target", {}) or {}
        target_label = target.get("region") or target.get("actor") or "global"

        return (
            f"Forecast source: THP model + GDELT data. For {target_label}, the model "
            f"predicts {round(float(first.get('median_events') or first.get('expected_events') or 0)):,} "
            f"median events on {first.get('date', 'the first forecast day')}, with an interval of "
            f"{round(float(first.get('low_events') or 0)):,} to "
            f"{round(float(first.get('high_events') or 0)):,}.\n\n"
            f"The peak risk day is {peak_date}. Model: {model}; checkpoint loaded: "
            f"{bool(checkpoint.get('available'))}. This fast path skips the full LLM tool loop and "
            f"calls the trained THP forecast service directly."
        )

    async def _try_fast_answer(self, message: str) -> Optional[Dict[str, Any]]:
        lowered = message.lower()
        forecast_cues = ("forecast", "predict", "prediction", "risk outlook", "next")
        if any(cue in lowered for cue in forecast_cues):
            forecast_start = self._extract_iso_date(message)
            country_pair = self._extract_country_pair(message)
            if forecast_start and country_pair:
                start = datetime.strptime(forecast_start, "%Y-%m-%d").date()
                forecast_days = self._extract_forecast_days(message)
                event_type = self._extract_event_type(message)
                target = f"{country_pair[0]} and {country_pair[1]}"
                history_start = start - timedelta(days=30)
                history_end = start - timedelta(days=1)
                self.tracker.add(
                    "tool_call",
                    "Fast path: get_event_forecast",
                    {
                        "name": "get_event_forecast",
                        "args": {
                            "forecast_start_date": forecast_start,
                            "target": target,
                            "event_type": event_type,
                            "forecast_days": forecast_days,
                        },
                    },
                )
                result = await self.data_service.forecast_event_risk(
                    start_date=history_start.strftime("%Y-%m-%d"),
                    end_date=history_end.strftime("%Y-%m-%d"),
                    region=target,
                    actor=None,
                    event_type=event_type,
                    forecast_days=forecast_days,
                )
                self.tracker.add(
                    "tool_result",
                    "Result from get_event_forecast",
                    {"name": "get_event_forecast", "preview": json.dumps(result.get("summary", {}), default=str)[:200]},
                )
                reply = self._format_forecast_reply(result)
                self.tracker.add("agent_response", reply)
                return {
                    "reply": reply,
                    "thinking_steps": self.tracker.steps,
                    "tools_used": ["get_event_forecast"],
                }

        comparison_cues = ("compare", "versus", " vs ", "between", "trend", "trends")
        relation_cues = ("cooperation", "cooperative", "conflict", "conflictual", "goldstein")
        if not any(cue in lowered for cue in comparison_cues):
            return None
        if not any(cue in lowered for cue in relation_cues):
            return None

        country_pair = self._extract_country_pair(message)
        date_range = self._extract_year_range(message)
        if not country_pair or not date_range:
            return None

        country_a, country_b = country_pair
        start_date, end_date = date_range
        self.tracker.add(
            "tool_call",
            "Fast path: get_country_pair_trends",
            {
                "name": "get_country_pair_trends",
                "args": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "country_a": country_a,
                    "country_b": country_b,
                },
            },
        )
        result = await self.data_service.get_country_pair_trends(
            start_date, end_date, country_a, country_b
        )
        self.tracker.add(
            "tool_result",
            "Result from get_country_pair_trends",
            {"name": "get_country_pair_trends", "preview": json.dumps(result.get("summary", {}), default=str)[:200]},
        )
        reply = self._format_country_pair_reply(result)
        self.tracker.add("agent_response", reply)
        return {
            "reply": reply,
            "thinking_steps": self.tracker.steps,
            "tools_used": ["get_country_pair_trends"],
        }
    
    def _build_tools(self) -> List[BaseTool]:
        """Build LangChain tools from DataService methods.
        
        Tools migrated from merge-ui tools v2:
        - search_events, get_event_detail, get_regional_overview
        - get_hot_events, get_top_events, get_daily_brief
        - get_dashboard, get_time_series, get_geo_heatmap
        """
        ds = self.data_service
        
        async def search_events_tool(
            query: str,
            time_hint: Optional[str] = None,
            location_hint: Optional[str] = None,
            event_type: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """Search GDELT events by keywords, time, location, or event type."""
            rows = await ds.search_events(query, time_hint, location_hint, event_type, max_results=limit)
            if not rows:
                return "No events found matching the criteria."
            return json.dumps(rows[:5], default=str, indent=2)
        
        async def get_event_detail_tool(fingerprint: str) -> str:
            """Get detailed information about a specific event by its fingerprint ID.
            
            Fingerprint formats:
            - Standard: 'US-20240115-WDC-PROTEST-001' (ETL generated)
            - Temporary: 'EVT-2024-01-15-123456789' (from search_results)
            """
            detail = await ds.get_event_detail(fingerprint)
            if not detail:
                return f"Event not found for fingerprint: {fingerprint}"
            return json.dumps(detail, default=str, indent=2)
        
        async def get_regional_overview_tool(
            region: str, time_range: str = "week"
        ) -> str:
            """Get regional situation overview with trend and risk analysis.
            
            Args:
                region: Region name or code, e.g. 'USA', 'China', 'Middle East'
                time_range: 'day', 'week', 'month', 'quarter', or 'year'
            """
            result = await ds.get_regional_overview(region, time_range)
            return json.dumps(result, default=str, indent=2)
        
        async def get_hot_events_tool(
            date: Optional[str] = None,
            region_filter: Optional[str] = None,
            top_n: int = 5
        ) -> str:
            """Get hot event recommendations for a specific date.
            
            Args:
                date: Date in YYYY-MM-DD format (default: yesterday)
                region_filter: Optional region filter, e.g. 'Asia', 'Europe', 'USA'
                top_n: Number of hot events to return (1-20)
            """
            rows = await ds.get_hot_events(date, region_filter, top_n)
            if not rows:
                return "No hot events found for the specified criteria."
            return json.dumps(rows, default=str, indent=2)
        
        async def get_top_events_tool(
            start_date: str,
            end_date: str,
            region_filter: Optional[str] = None,
            event_type: Optional[str] = None,
            top_n: int = 10
        ) -> str:
            """Get highest-heat events in a time period.
            
            Args:
                start_date: Start date (YYYY-MM-DD)
                end_date: End date (YYYY-MM-DD)
                region_filter: Optional region, e.g. 'USA', 'China'
                event_type: Optional filter: 'conflict', 'cooperation', 'protest', or 'any'
                top_n: Number to return (1-50)
            """
            rows = await ds.get_top_events(start_date, end_date, region_filter, event_type, top_n)
            if not rows:
                return "No events found for the specified criteria."
            return json.dumps(rows[:10], default=str, indent=2)
        
        async def get_daily_brief_tool(query_date: Optional[str] = None) -> str:
            """Get a daily brief summary for a specific date.
            
            Args:
                query_date: Date in YYYY-MM-DD format (default: yesterday)
            """
            result = await ds.get_daily_brief(query_date)
            if not result:
                return "No daily brief available for the specified date."
            return json.dumps(result, default=str, indent=2)
        
        async def get_dashboard_tool(start_date: str, end_date: str) -> str:
            """Get comprehensive dashboard statistics for a date range."""
            result = await ds.get_dashboard(start_date, end_date)
            summary = result.get("summary_stats", {}).get("data", [{}])[0]
            trend = result.get("daily_trend", {})
            return json.dumps({
                "summary": summary,
                "daily_data_points": trend.get("count", 0),
                "top_actors": result.get("top_actors", {}).get("data", [])[:5],
            }, default=str, indent=2)
        
        async def get_time_series_tool(start_date: str, end_date: str, granularity: str = "day") -> str:
            """Get time series data showing trends over time."""
            rows = await ds.get_time_series(start_date, end_date, granularity)
            return json.dumps(rows, default=str, indent=2)

        async def get_country_pair_trends_tool(
            start_date: str,
            end_date: str,
            country_a: str,
            country_b: str,
        ) -> str:
            """Get true bilateral cooperation/conflict trends between two countries.

            Uses Actor1CountryCode/Actor2CountryCode in both directions, so it is
            the right tool for questions like United States vs Canada in 2024.
            """
            result = await ds.get_country_pair_trends(start_date, end_date, country_a, country_b)
            daily = result.get("daily", [])
            top_conflict_days = sorted(
                daily, key=lambda row: float(row.get("conflict_pct") or 0), reverse=True
            )[:3]
            top_cooperation_days = sorted(
                daily, key=lambda row: float(row.get("cooperation_pct") or 0), reverse=True
            )[:3]
            compact_result = {
                "country_a": result.get("country_a"),
                "country_b": result.get("country_b"),
                "code_a": result.get("code_a"),
                "code_b": result.get("code_b"),
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date"),
                "source": result.get("source"),
                "summary": result.get("summary"),
                "daily_points": len(daily),
                "peak_conflict_day": result.get("peak_conflict_day"),
                "peak_cooperation_day": result.get("peak_cooperation_day"),
                "top_conflict_days": top_conflict_days,
                "top_cooperation_days": top_cooperation_days,
            }
            return json.dumps(compact_result, default=str, indent=2)

        async def get_event_forecast_tool(
            forecast_start_date: str,
            target: str = "global",
            event_type: str = "all",
            forecast_days: int = 7,
            lookback_days: int = 30,
        ) -> str:
            """Forecast future GDELT event intensity with the trained THP model.

            Args:
                forecast_start_date: First forecast day in YYYY-MM-DD format.
                target: Forecast target. Examples: 'United States and Canada',
                    'Police and United States', 'actor_pair: Canada and United States',
                    'Canada', or 'global'.
                event_type: 'all', 'conflict', 'cooperation', or 'protest'.
                forecast_days: Number of days to forecast, 1-60.
                lookback_days: Historical days before forecast_start_date, usually 30.
            """
            try:
                start = datetime.strptime(forecast_start_date, "%Y-%m-%d").date()
            except ValueError:
                return "Invalid forecast_start_date. Use YYYY-MM-DD, for example 2024-02-01."

            safe_forecast_days = max(1, min(int(forecast_days or 7), 60))
            safe_lookback_days = max(7, min(int(lookback_days or 30), 120))
            history_start = start - timedelta(days=safe_lookback_days)
            history_end = start - timedelta(days=1)
            normalized_event_type = (event_type or "all").lower()
            if normalized_event_type not in {"all", "conflict", "cooperation", "protest"}:
                normalized_event_type = "all"

            target_text = (target or "").strip()
            region = None if target_text.lower() in {"", "global", "all", "overall"} else target_text

            result = await ds.forecast_event_risk(
                start_date=history_start.strftime("%Y-%m-%d"),
                end_date=history_end.strftime("%Y-%m-%d"),
                region=region,
                actor=None,
                event_type=normalized_event_type,
                forecast_days=safe_forecast_days,
            )
            checkpoint = result.get("checkpoint", {}) or {}
            metadata = checkpoint.get("metadata", {}) or {}
            compact_result = {
                "source": "THP model + GDELT data",
                "model": result.get("model"),
                "target": result.get("target"),
                "series_key": checkpoint.get("series_key"),
                "checkpoint_available": checkpoint.get("available"),
                "checkpoint_error": checkpoint.get("error"),
                "model_metadata": {
                    "model_version": metadata.get("model_version"),
                    "best_epoch": metadata.get("best_epoch"),
                    "completed_epochs": metadata.get("completed_epochs"),
                    "device": metadata.get("device"),
                    "amp": metadata.get("amp"),
                },
                "baseline_comparison": checkpoint.get("baseline_comparison"),
                "summary": result.get("summary"),
                "forecast": result.get("forecast", [])[:safe_forecast_days],
                "attention_context": result.get("attention_context", [])[:5],
                "recent_history": result.get("recent_history", [])[-7:],
                "meta": result.get("_meta"),
            }
            return json.dumps(compact_result, default=str, indent=2)
        
        async def get_geo_heatmap_tool(start_date: str, end_date: str, precision: int = 2) -> str:
            """Get geographic heatmap data showing event density."""
            rows = await ds.get_geo_heatmap(start_date, end_date, precision)
            return json.dumps(rows[:20], default=str, indent=2)
        
        async def get_current_date_tool() -> str:
            """Get the current date."""
            return datetime.now().strftime("%Y-%m-%d")
        
        async def search_news_context_tool(
            query: str,
            n_results: int = 5
        ) -> str:
            """Search real news article content via ChromaDB vector semantic search.
            
            Use this when the user asks about:
            - Event causes, background, or detailed context
            - Protester demands or crowd specifics
            - Police/government response details
            - Anything requiring reading actual news text (not just GDELT metadata)
            """
            result = await ds.search_news_context(query, n_results)
            
            if "error" in result:
                return f"ChromaDB search error: {result.get('error')}: {result.get('message', '')}"
            
            if not result.get("results"):
                return f"No ChromaDB semantic context found for '{query}'."
            
            output = [f"# ChromaDB RAG context for: '{query}'\n"]
            for i, r in enumerate(result["results"]):
                content = r["content"]
                snippet = content[:1000] + "..." if len(content) > 1000 else content
                output.append(f"## Result {i+1}")
                output.append(f"- **Event ID**: {r.get('event_id', 'Unknown')}")
                output.append(f"- **Date**: {r.get('date', 'Unknown')}")
                output.append(f"- **Actors**: {r.get('actor1', '')} / {r.get('actor2', '')}")
                output.append(f"- **Location**: {r.get('location', '')}")
                output.append(f"- **Event type**: {r.get('event_type', '')}")
                output.append(f"- **Goldstein**: {r.get('goldstein', '')}")
                if r.get("distance") is not None:
                    output.append(f"- **Vector distance**: {float(r['distance']):.4f}")
                output.append(f"- **Source**: {r.get('source_url', 'Unknown')}")
                output.append(f"\n**Content**:\n{snippet}\n")
            
            return "\n".join(output)
        
        return [
            StructuredTool.from_function(
                coroutine=search_events_tool,
                name="search_events",
                description="Search GDELT events by keywords, time, location, or event type (conflict/cooperation/protest). Returns structured event data with fingerprints.",
            ),
            StructuredTool.from_function(
                coroutine=get_event_detail_tool,
                name="get_event_detail",
                description="Get detailed information about a specific event using its fingerprint ID. Use after search_events to drill down.",
            ),
            StructuredTool.from_function(
                coroutine=get_regional_overview_tool,
                name="get_regional_overview",
                description="Get regional situation overview with statistics, trends, and hot events. region='USA'/'China'/'Middle East', time_range='day'/'week'/'month'/'quarter'/'year'.",
            ),
            StructuredTool.from_function(
                coroutine=get_hot_events_tool,
                name="get_hot_events",
                description="Get hot event recommendations for a specific date. Use for 'what happened yesterday' or daily brief style queries.",
            ),
            StructuredTool.from_function(
                coroutine=get_top_events_tool,
                name="get_top_events",
                description="Get highest-heat (most significant) events in a time period. Supports region and event type filtering.",
            ),
            StructuredTool.from_function(
                coroutine=get_daily_brief_tool,
                name="get_daily_brief",
                description="Get a daily brief summary with aggregated statistics for a specific date.",
            ),
            StructuredTool.from_function(
                coroutine=get_dashboard_tool,
                name="get_dashboard",
                description="Get comprehensive statistics dashboard for a date range (YYYY-MM-DD format).",
            ),
            StructuredTool.from_function(
                coroutine=get_time_series_tool,
                name="get_time_series",
                description="Get time series trends data. Granularity: day, week, or month.",
            ),
            StructuredTool.from_function(
                coroutine=get_country_pair_trends_tool,
                name="get_country_pair_trends",
                description="Get true bilateral cooperation/conflict trends between two countries using Actor1CountryCode/Actor2CountryCode. Use for US-Canada, China-US, Russia-Ukraine, etc.",
            ),
            StructuredTool.from_function(
                coroutine=get_event_forecast_tool,
                name="get_event_forecast",
                description="Forecast future event intensity with the trained neural THP model. Use for predict/forecast/risk outlook/next 7 days questions. Supports country pairs, actor pairs, countries, event_type filters, and low/median/high prediction intervals.",
            ),
            StructuredTool.from_function(
                coroutine=get_geo_heatmap_tool,
                name="get_geo_heatmap",
                description="Get geographic event density heatmap for a date range.",
            ),
            StructuredTool.from_function(
                coroutine=get_current_date_tool,
                name="get_current_date",
                description="Get today's date in YYYY-MM-DD format.",
            ),
            StructuredTool.from_function(
                coroutine=search_news_context_tool,
                name="search_news_context",
                description="RAG semantic search over real news articles. Use for event causes, background context, protester demands, police response, or any query requiring actual news text (not just GDELT metadata).",
            ),
        ]
    
    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a chat message and return response with thinking steps.
        
        Args:
            message: User's natural language query
            history: Previous conversation messages
            session_id: Unique session for memory persistence
            
        Returns:
            dict with keys: reply, thinking_steps, tools_used, session_id
        """
        self.tracker = ThinkingTracker()
        session_id = session_id or f"session_{int(time.time() * 1000)}"
        
        # Convert history to LangChain messages
        lc_messages = []
        if history:
            for msg in history[-10:]:  # Keep last 10 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
        
        lc_messages.append(HumanMessage(content=message))
        
        self.tracker.add("user_message", message)

        fast_result = await self._try_fast_answer(message)
        if fast_result:
            return {
                "reply": fast_result["reply"],
                "session_id": session_id,
                "thinking_steps": fast_result["thinking_steps"],
                "tools_used": fast_result["tools_used"],
            }
        
        # Run agent
        tools_used = []
        try:
            # Stream to capture intermediate steps
            final_response = ""
            async for event in self.graph.astream(
                {"messages": lc_messages},
                stream_mode="values",
            ):
                messages = event.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        if last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                tools_used.append(tc.get("name", "unknown"))
                                self.tracker.add(
                                    "tool_call",
                                    f"Calling {tc.get('name')}",
                                    {"name": tc.get("name"), "args": tc.get("args", {})},
                                )
                        else:
                            final_response = last_msg.content
                    elif isinstance(last_msg, ToolMessage):
                        self.tracker.add(
                            "tool_result",
                            f"Result from {last_msg.name}",
                            {"name": last_msg.name, "preview": str(last_msg.content)[:200]},
                        )
            
            if not final_response:
                final_response = "I processed your request but couldn't generate a response. Please try again."
            
            self.tracker.add("agent_response", final_response)
            
        except Exception as e:
            import traceback, logging
            logging.getLogger("gdelt_agent").error(f"Agent error: {e}\n{traceback.format_exc()}")
            self.tracker.add("error", str(e))
            final_response = f"I encountered an error: {e}"
        
        return {
            "reply": final_response,
            "session_id": session_id,
            "thinking_steps": self.tracker.steps,
            "tools_used": list(set(tools_used)),
        }
    
    def get_tool_info(self) -> List[Dict[str, str]]:
        """Return list of available tools for frontend display."""
        return [
            {"name": tool.name, "description": tool.description or ""}
            for tool in self.tools
        ]
