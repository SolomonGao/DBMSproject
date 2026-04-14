# llm.py - LLM Interface Module
"""
LLM Client:
- Using OpenAI client wrapper
- Pass spoofing headers via http_client
- Tool calling handling
- Conversation history management
"""

import asyncio
import json
import re
from typing import List, Dict, Any, Optional, Callable, Awaitable

import httpx
from openai import AsyncOpenAI

from .logger import get_logger

logger = get_logger("llm")


def sanitize_text(text: str) -> str:
    """
    Clean illegal UTF-8 characters (surrogate pairs) from text
    
    These characters cannot be encoded by JSON/UTF-8 and will cause API call failures.
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Remove surrogate pairs (U+D800-U+DFFF)
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    
    # Replace control characters (keep normal newlines and tabs)
    import unicodedata
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    return text


class LLMClient:
    """LLM Client - Using OpenAI wrapper, disguised as Claude Code"""
    
    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.provider = provider.lower()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize OpenAI client
        # Use default_headers to disguise as Claude Code
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            default_headers={
                "User-Agent": "claude-code/1.0",
                "X-Client-Name": "claude-code",
            },
        )
        
        self.messages: List[Dict[str, Any]] = []
        
        logger.debug(f"Initializing LLMClient: provider={provider}, model={model}")
    
    def add_system_message(self, content: str):
        """Add system message"""
        content = sanitize_text(content)
        self.messages.append({"role": "system", "content": content})
        logger.debug(f"Added system message: {content[:50]}...")
    
    def add_user_message(self, content: str):
        """Add user message"""
        content = sanitize_text(content)
        self.messages.append({"role": "user", "content": content})
        logger.debug(f"Added user message: {content[:50]}...")
    
    def add_assistant_message(self, content: str):
        """Add assistant message"""
        content = sanitize_text(content)
        self.messages.append({"role": "assistant", "content": content})
    
    def add_tool_result(self, tool_call_id: str, content: str):
        """Add tool call result"""
        if not tool_call_id:
            logger.error("Attempted to add empty tool_call_id, skipping")
            return
        
        content = sanitize_text(content)
        # Ensure tool_call_id is not modified (API requires exact match)
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })
        logger.debug(f"Added tool result [{tool_call_id}]: {content[:50]}...")
    
    def clear_history(self, keep_system: bool = True):
        """Clear conversation history"""
        if keep_system:
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            self.messages = system_msgs
            logger.info("Conversation history cleared (system messages kept)")
        else:
            self.messages.clear()
            logger.info("Conversation history completely cleared")
    
    def get_history_length(self) -> int:
        """Get conversation history length"""
        return len(self.messages)
    
    def truncate_history(self, max_messages: int = 10, keep_system: bool = True):
        """
        Truncate conversation history, keep only recent N messages
        
        Args:
            max_messages: Maximum number of messages to keep (excluding system messages)
            keep_system: Whether to keep system messages
        """
        system_msgs = [m for m in self.messages if m["role"] == "system"] if keep_system else []
        non_system_msgs = [m for m in self.messages if m["role"] != "system"]
        
        # Keep only recent N non-system messages
        if len(non_system_msgs) > max_messages:
            kept_msgs = non_system_msgs[-max_messages:]
            self.messages = system_msgs + kept_msgs
            logger.info(f"History truncated: keeping recent {max_messages} messages")
        
        return len(self.messages)
    
    async def chat(
        self,
        tools: Optional[List[Dict]] = None,
        tool_executor: Optional[Callable[[str, Dict], Awaitable[str]]] = None,
        on_step: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> str:
        """
        Send chat request
        
        Args:
            tools: Available tools list
            tool_executor: Tool execution function
        
        Returns:
            AI reply content
        """
        try:
            # Validate message format (especially tool messages must have tool_call_id)
            valid_messages = []
            for i, msg in enumerate(self.messages):
                if msg.get("role") == "tool":
                    if not msg.get("tool_call_id"):
                        logger.error(f"Message {i} is a tool message missing tool_call_id, skipping")
                        continue
                valid_messages.append(msg)
            
            if len(valid_messages) != len(self.messages):
                logger.warning(f"Filtered {len(self.messages) - len(valid_messages)} invalid messages")
                self.messages = valid_messages
            
            logger.info(f"Sending request to {self.provider} (history: {len(self.messages)} messages)")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )
            
            message = response.choices[0].message
            
            # Handle tool calls
            if message.tool_calls and tool_executor:
                return await self._handle_tool_calls(message, tools, tool_executor, on_step)
            
            # Normal reply
            content = message.content or ""
            
            # Kimi specific reasoning_content
            if hasattr(message, "reasoning_content") and message.reasoning_content:
                logger.debug(f"Model reasoning: {message.reasoning_content[:100]}...")
                if on_step:
                    on_step("llm_reasoning", {"reasoning": message.reasoning_content})
                # Fallback: if content is empty but reasoning exists, use reasoning as reply
                if not content.strip():
                    content = message.reasoning_content
            
            # Backend force execution for high-likelihood tools when LLM returns empty
            if not content.strip() and tools and tool_executor:
                recent_user_msg = ""
                for msg in reversed(self.messages):
                    if msg.get("role") == "user":
                        recent_user_msg = msg.get("content", "")
                        break
                
                force_result = await self._try_force_tool_execution(
                    tools, tool_executor, recent_user_msg, on_step
                )
                if force_result:
                    return force_result
            
            # Final fallback for completely empty responses
            if not content.strip():
                content = "(The model returned an empty response. Please try rephrasing your question.)"
            
            self.add_assistant_message(content)
            logger.info(f"Received reply: {content[:100]}{'...' if len(content) > 100 else ''}")
            
            return content
            
        except Exception as e:
            logger.exception(f"LLM API error: {e}")
            return f"LLM request failed: {e}"
    
    async def _handle_tool_calls(
        self,
        message,
        tools: Optional[List[Dict]],
        tool_executor: Callable[[str, Dict], Awaitable[str]],
        on_step: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> str:
        """Handle tool calls"""
        # Build assistant's tool call request message
        assistant_msg = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        }
        
        # If thinking feature is enabled, need to include reasoning_content
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            assistant_msg["reasoning_content"] = message.reasoning_content
            logger.debug(f"Tool call reasoning: {message.reasoning_content[:100]}...")
        
        self.messages.append(assistant_msg)
        
        logger.info(f"AI requests to call {len(message.tool_calls)} tools")
        
        if on_step:
            on_step("tool_calls", {
                "tools": [
                    {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                    for tc in message.tool_calls
                ]
            })
        
        # Execute tool calls in parallel
        async def execute_single_tool(tool_call):
            """Execute single tool call"""
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"[Parallel] Calling tool: {tool_name}")
            logger.debug(f"Arguments: {json.dumps(tool_args, ensure_ascii=False)}")
            
            if on_step:
                on_step("tool_call_start", {"name": tool_name, "arguments": tool_args})
            
            start_time = asyncio.get_event_loop().time()
            result = await tool_executor(tool_name, tool_args)
            elapsed = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"[Parallel] Tool {tool_name} returned ({elapsed:.2f}s): {result[:80]}{'...' if len(result) > 80 else ''}")
            
            if on_step:
                on_step("tool_result", {
                    "name": tool_name,
                    "elapsed": round(elapsed, 2),
                    "result_preview": result[:200] + ("..." if len(result) > 200 else "")
                })
            
            return tool_call.id, result
        
        # Execute all tools in parallel
        results = await asyncio.gather(*[
            execute_single_tool(tc) for tc in message.tool_calls
        ])
        
        # Add results in original order (maintain tool_call_id correspondence)
        for tool_call in message.tool_calls:
            tc_id_to_match = tool_call.id
            if not tc_id_to_match:
                logger.error("Tool call ID is empty, skipping")
                continue
            
            for tc_id, result in results:
                if tc_id == tc_id_to_match:
                    self.add_tool_result(tc_id_to_match, result)
                    break
            else:
                # No matching result found
                logger.error(f"Tool call result not found: {tc_id_to_match}")
                self.add_tool_result(tc_id_to_match, "Tool execution failed: result not found")
        
        # Request again to get final reply
        final_reply = await self.chat(tools=None, tool_executor=None, on_step=on_step)
        if not final_reply.strip():
            final_reply = "(The model returned an empty response after tool execution. Please try again.)"
        return final_reply
    
    async def _try_force_tool_execution(
        self,
        tools: List[Dict],
        tool_executor: Callable[[str, Dict], Awaitable[str]],
        user_input: str,
        on_step: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ) -> Optional[str]:
        """Try to force-execute a tool when LLM returns empty response.
        
        Returns the final LLM-generated summary if successful, None otherwise.
        """
        tool_names = [t.get("function", {}).get("name") for t in tools if t.get("function", {}).get("name")]
        
        # Priority order: easy-to-infer args first
        for target in ["get_event_detail", "get_daily_brief", "get_hot_events", 
                       "search_news_context", "get_regional_overview", "get_top_events"]:
            if target not in tool_names:
                continue
            
            args: Optional[Dict] = None
            
            if target == "get_event_detail":
                match = re.search(r'(?:EVT|US)-\d{4}(?:-\d{2}-\d{2})?-[A-Z]*-*\d+', user_input)
                if match:
                    args = {"fingerprint": match.group(0), "include_causes": True}
            
            elif target in ("get_daily_brief", "get_hot_events"):
                args = {}  # all optional
            
            elif target == "search_news_context":
                if user_input.strip():
                    args = {"query": user_input.strip()[:200], "n_results": 3}
            
            elif target == "get_regional_overview":
                region = self._extract_region(user_input)
                if region:
                    args = {"region": region}
            
            elif target == "get_top_events":
                dates = self._extract_year_range(user_input)
                if dates:
                    args = {"start_date": dates[0], "end_date": dates[1]}
            
            if args is None:
                continue
            
            logger.warning(f"Backend forcing {target} with args {args}")
            if on_step:
                on_step("backend_force_execution", {"tool": target, "inferred_args": args})
            try:
                result = await tool_executor(target, args)
                self.add_assistant_message(f"I have executed {target} for you.")
                self.add_user_message(
                    f"Here is the raw result:\n{result}\n\n"
                    "Please summarize this in a clear, concise way for the user."
                )
                return await self.chat(tools=None, tool_executor=None, on_step=on_step)
            except Exception as exc:
                logger.exception(f"Forced {target} execution failed: {exc}")
                # Try next tool instead of giving up immediately
                continue
        
        return None
    
    @staticmethod
    def _extract_region(text: str) -> Optional[str]:
        """Extract common region names from user input."""
        text_lower = text.lower()
        regions = [
            ("middle east", "Middle East"),
            ("new york", "New York"),
            ("washington", "Washington"),
            ("california", "California"),
            ("texas", "Texas"),
            ("florida", "Florida"),
            ("china", "China"),
            ("russia", "Russia"),
            ("ukraine", "Ukraine"),
            ("israel", "Israel"),
            ("palestine", "Palestine"),
            ("europe", "Europe"),
            ("asia", "Asia"),
            ("africa", "Africa"),
            ("north america", "North America"),
            ("south america", "South America"),
            ("mexico", "Mexico"),
            ("canada", "Canada"),
            ("united states", "United States"),
            ("usa", "USA"),
            ("us", "US"),
            ("uk", "UK"),
            ("britain", "UK"),
            ("france", "France"),
            ("germany", "Germany"),
            ("japan", "Japan"),
            ("india", "India"),
            ("brazil", "Brazil"),
            ("australia", "Australia"),
        ]
        for keyword, region_name in regions:
            if keyword in text_lower:
                return region_name
        return None
    
    @staticmethod
    def _extract_year_range(text: str) -> Optional[tuple[str, str]]:
        """Extract year and return full date range."""
        match = re.search(r'\b(20\d{2})\b', text)
        if match:
            year = match.group(1)
            return (f"{year}-01-01", f"{year}-12-31")
        return None
    
    async def close(self):
        """Close LLM client connection"""
        if hasattr(self, 'client'):
            try:
                await self.client.close()
            except Exception as e:
                logger.warning(f"Error closing LLM client: {e}")
