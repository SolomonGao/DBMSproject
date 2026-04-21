"""
FastAPI Application Entry Point

Features:
- Lifespan management: DB pool init / cleanup, MCP Client init
- CORS for local frontend development
- Two router groups: /api/v1/data (Dashboard) and /api/v1/agent (Chat)
- Static file serving for built frontend
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import data, agent
from backend.services.data_service import data_service
from backend.agents.gdelt_agent import GDELTAgent

# MCP Client imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools


# ---------------------------------------------------------------------------
# Lifespan: Initialize services on startup, cleanup on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print("🚀 Initializing GDELT Analysis Platform...")
    
    # Initialize DataService (Dashboard queries)
    db_ok = False
    try:
        await data_service.initialize()
        print("✅ DataService initialized")
        db_ok = True
    except Exception as e:
        print(f"⚠️  DataService initialization failed: {e}")
        print("   Dashboard endpoints will return errors until DB is available.")
    
    # Initialize MCP Client and Agent
    mcp_tools = []
    agent_instance = None
    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["mcp_server/main.py"],
            env={**os.environ},
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                all_tools = await load_mcp_tools(session)
                
                # Filter out tools not suitable for conversational Q&A
                skip_tools = {"stream_events", "stream_query_events"}
                mcp_tools = [t for t in all_tools if t.name not in skip_tools]
                
                print(f"✅ MCP Client connected, loaded {len(mcp_tools)} tools (filtered {len(skip_tools)} bulk-export tools)")
                
                # Initialize default Agent (uses env vars for LLM config)
                agent_instance = GDELTAgent(tools=mcp_tools)
                print("✅ Agent initialized")
                
                app.state.mcp_tools = mcp_tools
                app.state.agent = agent_instance
                
                # Print available routes
                print("\n📡 Available endpoints:")
                for route in app.routes:
                    if hasattr(route, "methods") and hasattr(route, "path"):
                        methods = ",".join(route.methods - {"HEAD"})
                        if methods:
                            print(f"   {methods:8s} {route.path}")
                
                status = "🟢" if db_ok else "🟡"
                print(f"\n{status} Server ready (DB: {'connected' if db_ok else 'disconnected'})\n")
                
                yield  # Server runs here
                
                # Cleanup after yield
                print("\n🛑 Shutting down...")
                
    except Exception as e:
        print(f"⚠️  MCP Client / Agent initialization failed: {e}")
        print("   Chat endpoints will be unavailable. Check LLM_PROVIDER and API keys.")
        app.state.mcp_tools = []
        app.state.agent = None
        
        # Print available routes even without agent
        print("\n📡 Available endpoints:")
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                methods = ",".join(route.methods - {"HEAD"})
                if methods:
                    print(f"   {methods:8s} {route.path}")
        
        status = "🟢" if db_ok else "🟡"
        print(f"\n{status} Server ready (DB: {'connected' if db_ok else 'disconnected'}, Agent: unavailable)\n")
        
        yield  # Must yield even if agent failed
        
        print("\n🛑 Shutting down...")
    
    # Cleanup DataService
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
