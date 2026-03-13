"""FastAPI dependency injection."""

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from gdelt_api.config import Settings, get_settings
from gdelt_api.core.logging import get_logger
from gdelt_api.db import get_session
from gdelt_api.mcp import MCPClient
from gdelt_api.services import ChatService, EventService

logger = get_logger(__name__)


# MCP Client stored in app state
async def get_mcp_client(request: Request) -> MCPClient:
    """Get MCP client from app state."""
    if not hasattr(request.app.state, "mcp_client"):
        raise RuntimeError("MCP client not initialized")
    return request.app.state.mcp_client


async def get_chat_service(
    request: Request,
    settings: Settings = Depends(get_settings),
    mcp_client: MCPClient = Depends(get_mcp_client),
) -> ChatService:
    """Get chat service with dependencies."""
    return ChatService(settings, mcp_client)


async def get_event_service(
    session: AsyncSession = Depends(get_session),
) -> EventService:
    """Get event service with database session."""
    return EventService(session)
