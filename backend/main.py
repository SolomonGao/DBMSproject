"""
FastAPI Application Entry Point

Features:
- Lifespan management: DB pool init / cleanup
- CORS for local frontend development
- Two router groups: /api/v1/data (Dashboard) and /api/v1/agent (Chat)
- Static file serving for built frontend
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import data, agent
from backend.services.data_service import data_service
from backend.agents.gdelt_agent import GDELTAgent


# ---------------------------------------------------------------------------
# Lifespan: Initialize services on startup, cleanup on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print("🚀 Initializing GDELT Analysis Platform...")
    
    # Initialize DataService (DB pool)
    db_ok = False
    try:
        await data_service.initialize()
        print("✅ DataService initialized")
        db_ok = True
    except Exception as e:
        print(f"⚠️  DataService initialization failed: {e}")
        print("   Dashboard endpoints will return errors until DB is available.")
    
    # Initialize Agent (requires LLM API key; DB optional for some tools)
    try:
        app.state.agent = GDELTAgent(data_service)
        print("✅ Agent initialized")
    except Exception as e:
        print(f"⚠️  Agent initialization failed: {e}")
        print("   Chat endpoints will be unavailable. Check LLM_PROVIDER and API keys.")
        app.state.agent = None
    
    # Print available routes
    print("\n📡 Available endpoints:")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            methods = ",".join(route.methods - {"HEAD"})
            if methods:
                print(f"   {methods:8s} {route.path}")
    
    status = "🟢" if db_ok else "🟡"
    print(f"\n{status} Server ready (DB: {'connected' if db_ok else 'disconnected'})\n")
    
    yield
    
    # Cleanup
    print("\n🛑 Shutting down...")
    try:
        await data_service.close()
        print("✅ DataService closed")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="GDELT Analysis Platform",
        description="Dashboard + AI Chat for GDELT 2.0 event analysis",
        version="2.0.0",
        lifespan=lifespan,
    )
    
    # CORS: Allow local frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # API Routers
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(agent.router, prefix="/api/v1")
    
    # Health check at root
    @app.get("/health", tags=["health"])
    async def root_health():
        return {"ok": True, "service": "gdelt-platform", "version": "2.0.0"}
    
    # Serve built frontend (if exists)
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    
    return app


# Global app instance
app = create_app()
