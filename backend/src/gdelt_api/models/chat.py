"""Chat-related models."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """Chat message model."""
    
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="Message role"
    )
    content: str = Field(..., description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="Tool calls")
    tool_call_id: str | None = Field(None, description="Tool call ID")
    reasoning_content: str | None = Field(None, description="Reasoning content")
    
    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Ensure content is not empty after stripping."""
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v


class ToolCall(BaseModel):
    """Tool call model."""
    
    id: str = Field(..., description="Tool call ID")
    name: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResult(BaseModel):
    """Tool execution result model."""
    
    tool_call_id: str = Field(..., description="Tool call ID")
    name: str = Field(..., description="Tool name")
    result: str = Field(..., description="Tool execution result")
    success: bool = Field(True, description="Whether the tool execution was successful")
    error: str | None = Field(None, description="Error message if failed")


class ChatRequest(BaseModel):
    """Chat request model."""
    
    messages: list[Message] = Field(
        ..., 
        min_length=1,
        description="Chat messages history"
    )
    system_prompt: str | None = Field(
        None,
        description="Optional system prompt override"
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation"
    )
    max_tokens: int | None = Field(
        None,
        ge=1,
        le=8192,
        description="Maximum tokens to generate"
    )
    
    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: list[Message]) -> list[Message]:
        """Ensure at least one user message exists."""
        if not any(m.role == "user" for m in v):
            raise ValueError("At least one user message is required")
        return v


class ChatResponse(BaseModel):
    """Chat response model."""
    
    reply: str = Field(..., description="Assistant's reply")
    messages: list[Message] = Field(..., description="Updated message history")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, 
        description="Tool calls made during this turn"
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list,
        description="Tool execution results"
    )
    usage: dict[str, int] | None = Field(None, description="Token usage information")
    reasoning_content: str | None = Field(None, description="Model reasoning content")
