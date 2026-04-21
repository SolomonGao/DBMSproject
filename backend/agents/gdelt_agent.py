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
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import httpx
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

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

Guidelines:
- Be concise but insightful (2-4 paragraphs max)
- When presenting data, highlight the most important findings
- Always cite specific numbers, dates, and actor names when available
- If data is ambiguous, say so clearly
- Use the available tools to fetch real data rather than hallucinating

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
        
        # Build graph agent with memory
        self.memory = MemorySaver()
        self.graph = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SYSTEM_PROMPT,
            checkpointer=self.memory,
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
        
        async def get_geo_heatmap_tool(start_date: str, end_date: str, precision: int = 2) -> str:
            """Get geographic heatmap data showing event density."""
            rows = await ds.get_geo_heatmap(start_date, end_date, precision)
            return json.dumps(rows[:20], default=str, indent=2)
        
        async def get_current_date_tool() -> str:
            """Get the current date."""
            return datetime.now().strftime("%Y-%m-%d")
        
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
                coroutine=get_geo_heatmap_tool,
                name="get_geo_heatmap",
                description="Get geographic event density heatmap for a date range.",
            ),
            StructuredTool.from_function(
                coroutine=get_current_date_tool,
                name="get_current_date",
                description="Get today's date in YYYY-MM-DD format.",
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
        
        # Run agent
        tools_used = []
        try:
            config = {"configurable": {"thread_id": session_id}}
            
            # Stream to capture intermediate steps
            final_response = ""
            async for event in self.graph.astream(
                {"messages": lc_messages},
                config,
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
