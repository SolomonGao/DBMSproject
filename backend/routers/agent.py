"""
Agent Routes — Chat API

Conversational endpoints powered by LangGraph ReAct Agent.
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.dependencies import get_agent
from backend.agents.gdelt_agent import GDELTAgent
from backend.schemas.responses import ChatRequest, ChatResponse, ToolsResponse, ToolInfo

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
