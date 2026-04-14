"""
Lightweight Router - Based on Ollama + Qwen 2.5B

Responsibilities:
1. User input cleaning and standardization
2. Intent recognition (query/analysis/chat)
3. Tool pre-selection (for LLM reference)
4. Safety filtering

Architecture:
User -> Router (Qwen 2.5B local) -> [Optional] LLM (Kimi/Claude) -> MCP Server
"""

import json
import re
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .logger import get_logger

logger = get_logger("router")


@dataclass
class RouterDecision:
    """Router decision result"""
    intent: str                    # Intent: query | analysis | chat | direct
    cleaned_input: str             # Cleaned user input
    confidence: float              # Confidence 0-1
    suggested_tools: List[str]     # Suggested tools
    direct_response: Optional[str] = None  # Direct response (for chat)
    skip_llm: bool = False         # Whether to skip LLM
    reasoning: str = ""            # Decision reasoning


class OllamaRouter:
    """
    Ollama Local Router
    
    Uses Qwen 2.5B for lightweight intent recognition
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:3b"):
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/chat"
        logger.info(f"Router initialized: {model} @ {base_url}")
    
    async def route(self, user_input: str, context: List[Dict] = None) -> RouterDecision:
        """
        Main routing function
        
        Returns:
            RouterDecision: Contains processing decision
        """
        # Step 1: Basic cleaning
        cleaned = self._basic_clean(user_input)
        
        # Step 2: Handle system commands
        if cleaned.startswith('/'):
            return self._handle_command(cleaned)
        
        # Step 3: Safety check
        safety_flags = self._safety_check(cleaned)
        if safety_flags:
            return RouterDecision(
                intent="blocked",
                cleaned_input=cleaned,
                confidence=1.0,
                suggested_tools=[],
                direct_response="⚠️ Input contains unsafe content, please rephrase.",
                skip_llm=True,
                reasoning=f"Safety flags: {safety_flags}"
            )
        
        # Step 4: Quick rule-based check (reduce model calls)
        rule_result = self._quick_check(cleaned)
        if rule_result:
            return rule_result
        
        # Step 5: Call Qwen 2.5B for intent recognition
        try:
            return await self._call_ollama(cleaned, context)
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            # Fallback to rule-based classification
            return self._fallback_classify(cleaned)
    
    def _basic_clean(self, text: str) -> str:
        """Basic text cleaning"""
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)  # Normalize spaces
        text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)  # Remove zero-width characters
        return text
    
    def _safety_check(self, text: str) -> List[str]:
        """Safety check"""
        flags = []
        dangerous = ['drop table', 'delete from', 'truncate table', ';--']
        if any(d in text.lower() for d in dangerous):
            flags.append("sql_injection")
        return flags
    
    def _handle_command(self, command: str) -> RouterDecision:
        """Handle system commands"""
        return RouterDecision(
            intent="command",
            cleaned_input=command,
            confidence=1.0,
            suggested_tools=[],
            skip_llm=True,
            reasoning="System command"
        )
    
    def _quick_check(self, text: str) -> Optional[RouterDecision]:
        """Quick rule-based check (avoid model calls)"""
        text_lower = text.lower()
        
        # CLI commands (starting with /)
        if text.startswith('/'):
            return RouterDecision(
                intent="command",
                cleaned_input=text,
                confidence=1.0,
                suggested_tools=[],
                skip_llm=True,
                reasoning="CLI command"
            )
        
        # Simple greetings (Chinese + English)
        greetings = ['yougood', 'hello', 'hi', 'ok', 'okay']
        if any(g in text_lower for g in greetings) and len(text) < 10:
            return RouterDecision(
                intent="chat",
                cleaned_input=text,
                confidence=0.95,
                suggested_tools=[],
                direct_response=None,  # Let LLM respond
                skip_llm=False,
                reasoning="Simple greeting"
            )
        
        # Daily brief keywords (Chinese + English)
        daily_brief_keywords = [
            'brief', 'daily report', 'daily brief', 'daily report', 'news brief',
            'todaydaynews', 'todaybrief', 'What happened today', 'newssummary',
            'newsbrief', 'eachdaynews', 'daily news', 'todaynews'
        ]
        if any(kw in text_lower for kw in daily_brief_keywords):
            return RouterDecision(
                intent="query",
                cleaned_input=text,
                confidence=0.95,
                suggested_tools=["get_daily_brief"],
                skip_llm=False,
                reasoning="Daily brief request"
            )
        
        # Explicit database query keywords (Chinese)
        if any(kw in text_lower for kw in ['queryinquiry', 'queryfind', 'searchsearch', 'queryoneunder']):
            return None  # Needs further model analysis
        
        return None
    
    async def _call_ollama(self, text: str, context: List[Dict] = None) -> RouterDecision:
        """Call local Ollama"""
        
        system_prompt = """You are an intelligent routing assistant. Analyze user input and output JSON format decisions.

Intent Classification:
- query: Needs to query GDELT database (e.g., "Virginia news", "events in Jan 2024")
- analysis: Needs statistical analysis (e.g., "conflict trends", "Top 10 actors", "heatmap visualization")
- chat: Casual chat, greetings, simple Q&A (e.g., "hello", "thanks", "what can you do")
- clarification: Needs user clarification (input ambiguous or incomplete)

Available Tools (merge-optimized complete toolset):

[Core Search Tools]
- search_events: Intelligent event search (core entry) - supports natural language like "protests in Washington in Jan"
- get_event_detail: Get event details (via fingerprint ID like US-20240115-WDC-PROTEST-001)
- search_news_context: RAG semantic search - query news knowledge base for real report details

[Analysis & Statistics Tools]
- get_dashboard: Dashboard data - 5 queries in parallel, fast multi-dimensional stats
- analyze_time_series: Time series analysis - supports day/week/month granularity trend analysis, includes conflict/cooperation trends
- get_geo_heatmap: Geographic heatmap - grid aggregation showing event density
- get_regional_overview: Regional situation overview (e.g., "Middle East situation")

[Event Discovery Tools]
- get_hot_events: Hot event recommendations (single day)
- get_top_events: Time period heat ranking (cross-time range, e.g., "hottest events in 2024")
- get_daily_brief: Daily brief

[Advanced Query Tools]
- stream_events: Stream query - handles large data volumes, memory-friendly
- stream_query_events: Optimized streaming query by actor name

[Diagnostic Tools]
- get_cache_stats: View query cache statistics
- clear_cache: Clear query cache

Tool Selection Guide:
- User says "search", "find", "look up" -> search_events
- User mentions "details", "tell me more" + fingerprint ID -> get_event_detail
- User asks "why", "demands", "details" -> search_news_context (RAG)
- User asks "statistics", "trends", "analysis", "conflict trends", "cooperation trends" -> get_dashboard or analyze_time_series
- User asks "map", "distribution", "heat" -> get_geo_heatmap
- User asks "situation", "status", "how is" -> get_regional_overview
- User asks "hot", "news", "what happened" (single day) -> get_hot_events
- User asks "hottest", "Top", "ranking" (cross-time) -> get_top_events
- User wants "brief", "daily report", "summary" -> get_daily_brief
- User says "large data", "export all" -> stream_events or stream_query_events

Tool Combination Suggestions:
- Deep event analysis: search_events -> get_event_detail -> search_news_context
- Regional situation: get_regional_overview + get_geo_heatmap
- Time trends: analyze_time_series + get_dashboard

Output Format (strict JSON):
{
    "intent": "query|analysis|chat|clarification",
    "confidence": 0.95,
    "suggested_tools": ["tool1", "tool2"],
    "needs_llm": true,
    "reasoning": "brief explanation"
}

Notes:
1. Only output JSON, no other content
2. needs_llm: true when complex query requires LLM reasoning, false for simple queries
3. confidence: number between 0-1
4. Prefer new tools (V2), don't use old ones like query_by_actor"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User input: {text}"}
        ]
        
        # Add context (last 3 rounds)
        if context:
            recent = context[-6:] if len(context) > 6 else context
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if len(content) > 200:
                    content = content[:200] + "..."
                messages.insert(-1, {"role": role, "content": content})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=aiohttp.ClientTimeout(total=5)  # 5 second timeout
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama error: {resp.status}")
                
                data = await resp.json()
                content = data["message"]["content"]
                
                # Parse JSON
                try:
                    # Extract JSON (in case of extra text)
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group().strip()
                        # Try to fix incomplete JSON (missing closing })
                        if json_str and json_str[-1] != '}':
                            json_str += '}'
                        result = json.loads(json_str)
                    else:
                        result = json.loads(content)
                    
                    # Fix: if suggested_tools is non-empty, MUST need LLM to execute them
                    needs_llm = result.get("needs_llm", True)
                    suggested_tools = result.get("suggested_tools", [])
                    if suggested_tools:
                        needs_llm = True
                    
                    return RouterDecision(
                        intent=result.get("intent", "query"),
                        cleaned_input=text,
                        confidence=result.get("confidence", 0.7),
                        suggested_tools=suggested_tools,
                        skip_llm=not needs_llm,
                        reasoning=result.get("reasoning", "")
                    )
                except json.JSONDecodeError:
                    # Silent handling, use fallback
                    logger.debug(f"Router JSON parse failed, using fallback: {content[:100]}...")
                    return self._fallback_classify(text)
    
    def _fallback_classify(self, text: str) -> RouterDecision:
        """Rule-based Fallback - used when Ollama fails"""
        text_lower = text.lower()
        
        # Daily brief detection (Chinese + English)
        if any(kw in text_lower for kw in ['brief', 'daily report', 'brief', 'daily report', 'news summary']):
            return RouterDecision(
                intent="query",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["get_daily_brief"],
                skip_llm=False,
                reasoning="Fallback: daily brief request"
            )
        
        # Analysis & Dashboard (Chinese + English)
        if any(kw in text_lower for kw in ['statistics', 'analyze', 'trends', 'dashboard', 'instrumenttabledisk']):
            return RouterDecision(
                intent="analysis",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["get_dashboard", "analyze_time_series"],
                skip_llm=False,
                reasoning="Fallback: analysis keywords"
            )
        
        # Geographic / Heatmap (Chinese + English)
        if any(kw in text_lower for kw in ['map', 'heatmap', 'heatmap', 'locationprocess', 'distribution', 'canviewization']):
            return RouterDecision(
                intent="analysis",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["get_geo_heatmap", "get_regional_overview"],
                skip_llm=False,
                reasoning="Fallback: geographic visualization"
            )
        
        # Time series / trends (Chinese)
        if any(kw in text_lower for kw in ['whenintervalordercolumn', 'trends', 'variableization', 'trend', 'time series']):
            return RouterDecision(
                intent="analysis",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["analyze_time_series"],
                skip_llm=False,
                reasoning="Fallback: time series keywords"
            )
        
        # Streaming / large data (Chinese)
        if any(kw in text_lower for kw in ['export', 'all', 'all', 'streaming', 'bigamountdata']):
            return RouterDecision(
                intent="query",
                cleaned_input=text,
                confidence=0.6,
                suggested_tools=["stream_events", "stream_query_events"],
                skip_llm=False,
                reasoning="Fallback: streaming query"
            )
        
        # Default: use core V2 tools
        return RouterDecision(
            intent="query",
            cleaned_input=text,
            confidence=0.6,
            suggested_tools=["search_events", "get_top_events"],
            skip_llm=False,
            reasoning="Fallback: default to V2 search tools"
        )
    
    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return self.model in models
                    return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
