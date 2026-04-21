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
        
        # OpenAI SDK's chat.completions.create() accepts extra_body as a special
        # kwarg that gets merged into the request body. LangChain's ChatOpenAI
        # also supports it as a direct parameter.
        return ChatOpenAI(
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            model=cfg["model"],
            temperature=0.3,
            max_tokens=4096,
            http_async_client=http_async_client,
            extra_body={"thinking": False},
        )
    
    def _build_tools(self) -> List[BaseTool]:
        """Build LangChain tools from DataService methods."""
        ds = self.data_service
        
        async def search_events_tool(query: str, time_hint: Optional[str] = None, location_hint: Optional[str] = None, limit: int = 10) -> str:
            """Search for events matching a query."""
            rows = await ds.search_events(query, time_hint, location_hint, max_results=limit)
            if not rows:
                return "No events found matching the criteria."
            return json.dumps(rows[:5], default=str, indent=2)
        
        async def get_dashboard_tool(start_date: str, end_date: str) -> str:
            """Get comprehensive dashboard statistics for a date range."""
            result = await ds.get_dashboard(start_date, end_date)
            # Summarize key stats
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
                description="Search GDELT events by keywords, time, or location. Returns structured event data.",
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
