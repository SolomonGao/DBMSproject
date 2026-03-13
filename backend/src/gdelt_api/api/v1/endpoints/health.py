"""Health check endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from gdelt_api.config import Settings, get_settings
from gdelt_api.mcp import MCPClient
from gdelt_api.api.dependencies import get_mcp_client

router = APIRouter()


@router.get("")
async def health_check(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.env,
    }


@router.get("/ready")
async def readiness_check(
    request: Request,
    mcp_client: MCPClient = Depends(get_mcp_client),
) -> dict[str, Any]:
    """Readiness check including dependencies."""
    checks = {
        "mcp": mcp_client.is_connected,
    }
    
    all_healthy = all(checks.values())
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Liveness check."""
    return {"status": "alive"}
