"""GDELT Narrative API - FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from gdelt_api.api.errors import setup_exception_handlers
from gdelt_api.api.v1 import api_router
from gdelt_api.config import get_settings
from gdelt_api.core.events import Event, event_bus
from gdelt_api.core.logging import configure_logging, get_logger
from gdelt_api.db import close_db, init_db
from gdelt_api.mcp import MCPClient

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.env,
    )
    
    # Initialize logging
    configure_logging()
    
    # Initialize database
    await init_db()
    logger.info("database_initialized")
    
    # Initialize MCP client
    mcp_client = MCPClient(settings)
    try:
        await mcp_client.connect()
        app.state.mcp_client = mcp_client
        logger.info("mcp_client_connected")
    except Exception as e:
        logger.error("mcp_client_connection_failed", error=str(e))
        # Continue without MCP - endpoints will handle this
    
    # Emit startup event
    await event_bus.emit(Event("app.startup", {"version": settings.app_version}))
    
    logger.info("application_ready")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    # Close MCP client
    if hasattr(app.state, "mcp_client"):
        await app.state.mcp_client.close()
        logger.info("mcp_client_closed")
    
    # Close database
    await close_db()
    logger.info("database_closed")
    
    # Emit shutdown event
    await event_bus.emit(Event("app.shutdown", {}))
    
    logger.info("application_stopped")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="Spatio-Temporal Narrative AI Agent for North America Event Analysis",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Exception handlers
    setup_exception_handlers(app)
    
    # API routes
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    
    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "gdelt_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1,
        log_level=settings.log_level.lower(),
    )
