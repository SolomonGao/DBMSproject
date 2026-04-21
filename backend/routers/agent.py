"""
Agent Routes — Chat API

Conversational endpoints powered by LangGraph ReAct Agent.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.dependencies import get_agent
from backend.agents.gdelt_agent import GDELTAgent
from backend.schemas.responses import (
    ChatRequest, ChatResponse, ToolsResponse, ToolInfo,
    HelpsResponse, HelpItem,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: GDELTAgent = Depends(get_agent),
):
    """
    Natural language chat with tool-calling capabilities.
    
    The agent can:
    - Search events by keywords, time, location
    - Retrieve dashboard statistics
    - Analyze time series trends
    - Explore geographic heatmaps
    
    Conversation memory is maintained via session_id.
    """
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


@router.get("/tools", response_model=ToolsResponse)
async def list_tools(
    agent: GDELTAgent = Depends(get_agent),
):
    """List available tools the agent can use."""
    try:
        tools = agent.get_tool_info()
        return ToolsResponse(
            tools=[ToolInfo(**t) for t in tools]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {e}")


@router.get("/helps", response_model=HelpsResponse)
async def list_helps(
    agent: GDELTAgent = Depends(get_agent),
):
    """List available slash commands and usage tips."""
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
