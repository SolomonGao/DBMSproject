"""
FastAPI Dependencies

Provides dependency injection for:
- DataService (Dashboard queries)
- GDELTAgent (Chat intelligence)
"""

from typing import AsyncGenerator
from fastapi import Request

from backend.services.data_service import data_service, DataService


async def get_data_service() -> AsyncGenerator[DataService, None]:
    """Yield the DataService singleton (lazy init if not already done)."""
    if not data_service._initialized:
        try:
            await data_service.initialize()
        except Exception:
            pass  # Let endpoints handle the error and return 503
    yield data_service


def get_agent(request: Request):
    """Get the LangGraph agent from app state."""
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise RuntimeError("Agent not initialized. Check startup events.")
    return agent
