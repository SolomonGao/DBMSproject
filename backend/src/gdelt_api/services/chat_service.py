"""Chat service handling conversation flow."""

from typing import Any

from gdelt_api.config import Settings
from gdelt_api.core.exceptions import ValidationError
from gdelt_api.core.logging import get_logger
from gdelt_api.mcp.client import MCPClient
from gdelt_api.models.chat import (
    ChatRequest,
    ChatResponse,
    Message,
    ToolCall,
    ToolResult,
)
from gdelt_api.services.llm_service import LLMService

logger = get_logger(__name__)


class ChatService:
    """Service for handling chat conversations."""
    
    def __init__(
        self,
        settings: Settings,
        mcp_client: MCPClient,
    ) -> None:
        self.settings = settings
        self.mcp_client = mcp_client
        self.llm_service = LLMService(settings)
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request."""
        logger.info("chat_request", message_count=len(request.messages))
        
        # Prepare messages
        messages = self._prepare_messages(request)
        
        # Get available tools
        tools = self.mcp_client.get_openai_tools()
        
        # First LLM call
        response = await self.llm_service.chat(
            messages=[m.model_dump(exclude_none=True) for m in messages],
            tools=tools if tools else None,
            tool_choice="auto" if tools else "none",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        # Extract response
        assistant_msg = self.llm_service.extract_message(response)
        messages.append(Message(**assistant_msg))
        
        # Check for tool calls
        tool_calls = self.llm_service.extract_tool_calls(response)
        
        if not tool_calls:
            logger.info("chat_no_tools", reply_length=len(assistant_msg.get("content", "")))
            return ChatResponse(
                reply=assistant_msg.get("content", ""),
                messages=messages,
                reasoning_content=assistant_msg.get("reasoning_content"),
            )
        
        # Execute tool calls
        logger.info("executing_tools", tool_count=len(tool_calls))
        tool_results = await self._execute_tools(tool_calls)
        
        # Add tool results to messages
        for result in tool_results:
            messages.append(Message(
                role="tool",
                content=result.result if result.success else result.error or "",
                tool_call_id=result.tool_call_id,
            ))
        
        # Second LLM call with tool results
        final_response = await self.llm_service.chat(
            messages=[m.model_dump(exclude_none=True) for m in messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        final_msg = self.llm_service.extract_message(final_response)
        messages.append(Message(**final_msg))
        
        logger.info("chat_complete", reply_length=len(final_msg.get("content", "")))
        
        return ChatResponse(
            reply=final_msg.get("content", ""),
            messages=messages,
            tool_calls=[ToolCall(**tc) for tc in tool_calls],
            tool_results=tool_results,
            reasoning_content=final_msg.get("reasoning_content"),
        )
    
    def _prepare_messages(self, request: ChatRequest) -> list[Message]:
        """Prepare messages for LLM."""
        messages = list(request.messages)
        
        # Add system prompt if not present and provided
        if request.system_prompt:
            if not any(m.role == "system" for m in messages):
                messages.insert(0, Message(role="system", content=request.system_prompt))
        
        return messages
    
    async def _execute_tools(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[ToolResult]:
        """Execute tool calls."""
        results: list[ToolResult] = []
        
        for tc in tool_calls:
            try:
                result = await self.mcp_client.call_tool(
                    tc["name"],
                    tc["arguments"],
                )
                
                results.append(ToolResult(
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    result=result,
                    success=True,
                ))
                
            except Exception as e:
                logger.error("tool_execution_failed", tool=tc["name"], error=str(e))
                results.append(ToolResult(
                    tool_call_id=tc["id"],
                    name=tc["name"],
                    result="",
                    success=False,
                    error=str(e),
                ))
        
        return results
