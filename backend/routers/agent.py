"""
Agent Routes — Chat API

Conversational endpoints powered by LangGraph ReAct Agent.
Agent tools are loaded from MCP Server via langchain-mcp-adapters.
"""

from fastapi import APIRouter, HTTPException, Request

from backend.agents.gdelt_agent import GDELTAgent
from backend.schemas.responses import (
    ChatRequest, ChatResponse, ToolsResponse, ToolInfo,
    HelpsResponse, HelpItem,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
):
    """
    Natural language chat with tool-calling capabilities.
    
    Supports custom LLM configuration per request via llm_config.
    If llm_config is not provided, uses the server's default agent.
    """
    default_agent = getattr(req.app.state, "agent", None)
    mcp_tools = getattr(req.app.state, "mcp_tools", [])
    
    if default_agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized. Check LLM_PROVIDER and API keys.")
    
    try:
        # Use custom LLM config if provided
        if request.llm_config:
            agent = default_agent.with_config(request.llm_config.model_dump(exclude_none=True))
        else:
            agent = default_agent
        
        result = await agent.chat(
            message=request.message,
            history=request.history,
            session_id=request.session_id,
        )
        
        return ChatResponse(
            reply=result["reply"],
            session_id=result["session_id"],
            thinking_steps=[
                {"type": s["type"], "content": s.get("content", ""), "data": s.get("data", {})}
                for s in result.get("thinking_steps", [])
            ],
            tools_used=result.get("tools_used", []),
        )
    except ValueError as e:
        # Likely invalid LLM config (e.g. missing API key)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@router.get("/tools", response_model=ToolsResponse)
async def list_tools(
    req: Request,
):
    """List available tools the agent can use."""
    agent = getattr(req.app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized.")
    
    try:
        tools = agent.get_tool_info()
        return ToolsResponse(
            tools=[ToolInfo(**t) for t in tools]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {e}")


@router.get("/helps", response_model=HelpsResponse)
async def list_helps(
    req: Request,
):
    """List available slash commands and usage tips."""
    agent = getattr(req.app.state, "agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized.")
    
    try:
        tools = agent.get_tool_info()
        helps = []
        for tool in tools:
            helps.append(HelpItem(
                command=f"/use {tool['name']}",
                description=tool.get("description", ""),
                example=f"Example: 'Use {tool['name']} to ...'",
            ))
        return HelpsResponse(
            helps=helps,
            tips=[
                "Ask natural language questions — the agent will select tools automatically.",
                "For comparisons, mention both subjects explicitly (e.g., 'Washington vs New York').",
                "Use date ranges like 'January 2024' or 'last week' — the agent parses time hints.",
                "After search_events, you can ask for event details using the fingerprint ID.",
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list helps: {e}")
