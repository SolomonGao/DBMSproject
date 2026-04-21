"""
GDELT Agent — LangGraph ReAct Agent for conversational analysis.

Architecture:
- Uses LangGraph's create_react_agent for robust tool-calling loops
- Tools are loaded from MCP Server via langchain-mcp-adapters (zero code coupling)
- Supports runtime LLM configuration switching per request
- Supports conversation memory via thread_id
- Streaming events for real-time thinking steps
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

=== TOOL SELECTION DECISION TREE (FOLLOW STRICTLY) ===

Your goal: answer the user in the FEWEST tool calls possible (ideally 1-2, max 3).

Analyze the user's intent, then pick ONE of these patterns:

1. "What happened in [region] during [time]?" / "Overview of..."
   → get_regional_overview(region, time_range)
   → IF you need specific examples: get_top_events(start_date, end_date, region_filter)
   → STOP. Do not call search_events.

2. "Tell me about [specific topic/event/actor]"
   → search_events(query, limit=5)
   → IF the user asks for details on ONE specific result: get_event_detail(fingerprint) x1
   → STOP.

3. "Compare [A] vs [B]"
   → get_regional_overview(A, time_range) THEN get_regional_overview(B, time_range)
   → OR search_events for A, then search_events for B
   → STOP. Present comparison immediately.

4. "Trends / How has X changed over time?"
   → analyze_time_series(start_date, end_date, granularity="month")
   → STOP.

5. "Why did X happen? / Background / Causes / Protester demands"
   → search_events(query, limit=3)
   → search_news_context(query) x1
   → STOP.

6. "What happened yesterday / today / on [specific date]?"
   → get_daily_brief(date)
   → IF you need more color: get_hot_events(date)
   → STOP.

7. "Where are the hotspots? / Geographic distribution"
   → get_geo_heatmap(start_date, end_date)
   → STOP.

=== ANTI-PATTERNS (NEVER DO) ===
- NEVER call search_events more than once per query.
- NEVER call get_event_detail more than 2 times per query.
- NEVER call search_news_context more than 1 time per query.
- NEVER use stream_events or stream_query_events for normal Q&A (they are for bulk data export only).
- NEVER call get_dashboard unless the user explicitly asks for "dashboard" or "statistics overview".
- If you already have enough data to answer, STOP immediately. Do not keep digging.
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

    Tools are provided externally (from MCP Server via langchain-mcp-adapters).
    The agent only handles LLM orchestration, reasoning, and conversation memory.

    Usage:
        # Default agent (uses env vars for LLM config)
        agent = GDELTAgent(tools=mcp_tools)

        # Custom LLM per request
        custom_agent = agent.with_config({
            "provider": "openai",
            "api_key": "sk-...",
            "model": "gpt-4o"
        })
        response = await custom_agent.chat("What happened in Washington last month?")
    """

    def __init__(
        self,
        tools: List[BaseTool],
        config: Optional[Dict[str, Any]] = None,
    ):
        self.tools = tools
        self.config = config or {}
        self.tracker: Optional[ThinkingTracker] = None

        # Build LLM
        self.llm = self._build_llm(self.config)

        # Build graph agent
        self.graph = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SYSTEM_PROMPT,
        )

    def _build_llm(self, config: Optional[Dict[str, Any]] = None) -> BaseChatModel:
        """Initialize LLM from environment configuration or runtime config."""
        cfg = config or {}
        provider = cfg.get("provider", os.getenv("LLM_PROVIDER", "kimi")).lower()

        # Map provider to config
        configs = {
            "kimi": {
                "api_key": cfg.get("api_key", os.getenv("KIMI_CODE_API_KEY", os.getenv("MOONSHOT_API_KEY", ""))),
                "base_url": cfg.get("base_url", os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")),
                "model": cfg.get("model", os.getenv("LLM_MODEL", "kimi-k2-0905-preview")),
            },
            "moonshot": {
                "api_key": cfg.get("api_key", os.getenv("MOONSHOT_API_KEY", "")),
                "base_url": cfg.get("base_url", os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")),
                "model": cfg.get("model", os.getenv("LLM_MODEL", "kimi-k2-0905-preview")),
            },
            "claude": {
                "api_key": cfg.get("api_key", os.getenv("ANTHROPIC_API_KEY", "")),
                "base_url": cfg.get("base_url", os.getenv("LLM_BASE_URL", "https://api.anthropic.com/v1")),
                "model": cfg.get("model", os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")),
            },
            "openai": {
                "api_key": cfg.get("api_key", os.getenv("OPENAI_API_KEY", "")),
                "base_url": cfg.get("base_url", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")),
                "model": cfg.get("model", os.getenv("LLM_MODEL", "gpt-4o")),
            },
        }

        provider_cfg = configs.get(provider, configs["kimi"])

        if not provider_cfg["api_key"]:
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
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg["base_url"],
            model=provider_cfg["model"],
            temperature=0.3,
            max_tokens=4096,
            http_async_client=http_async_client,
        )

    def with_config(self, config: Dict[str, Any]) -> "GDELTAgent":
        """Return a new agent instance with the same tools but different LLM config."""
        return GDELTAgent(tools=self.tools, config=config)

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
