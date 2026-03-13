"""LLM service for Kimi API integration."""

import json
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gdelt_api.config import Settings
from gdelt_api.core.exceptions import LLMError
from gdelt_api.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Service for LLM API interactions."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
            timeout=httpx.Timeout(settings.llm.timeout),
            default_headers={
                "User-Agent": "gdelt-narrative-api/1.0",
                "X-Client-Name": "gdelt-api",
            },
        )
    
    @retry(
        retry=retry_if_exception_type((LLMError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletion:
        """Send chat completion request."""
        
        temp = temperature if temperature is not None else self.settings.llm.temperature
        max_tok = max_tokens if max_tokens is not None else self.settings.llm.max_tokens
        
        logger.debug(
            "llm_chat_request",
            message_count=len(messages),
            tool_count=len(tools) if tools else 0,
            model=self.settings.llm.model,
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice if tools else "none",
                temperature=temp,
                max_tokens=max_tok,
            )
            
            logger.debug(
                "llm_chat_response",
                model=response.model,
                usage=response.usage.dict() if response.usage else None,
            )
            
            return response
            
        except Exception as e:
            logger.error("llm_chat_failed", error=str(e))
            raise LLMError(f"LLM API error: {e}")
    
    def extract_tool_calls(self, response: ChatCompletion) -> list[dict[str, Any]]:
        """Extract tool calls from response."""
        message = response.choices[0].message
        
        if not message.tool_calls:
            return []
        
        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in message.tool_calls
        ]
    
    def extract_message(
        self, 
        response: ChatCompletion,
    ) -> dict[str, Any]:
        """Extract message content from response."""
        message = response.choices[0].message
        
        result: dict[str, Any] = {
            "role": "assistant",
            "content": message.content or "",
        }
        
        # Include reasoning_content if present (Kimi-specific)
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            result["reasoning_content"] = message.reasoning_content
        
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        
        return result
    
    def build_tool_result_message(
        self,
        tool_call_id: str,
        result: str,
    ) -> dict[str, str]:
        """Build a tool result message."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }
