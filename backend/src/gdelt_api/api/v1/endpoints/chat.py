"""Chat endpoints."""

from fastapi import APIRouter, Depends, status

from gdelt_api.api.dependencies import get_chat_service
from gdelt_api.models.chat import ChatRequest, ChatResponse
from gdelt_api.models.common import APIResponse
from gdelt_api.services import ChatService

router = APIRouter()


@router.post(
    "",
    response_model=APIResponse[ChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Send chat message",
    description="Send a chat message and get AI response with potential tool calls.",
)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> APIResponse[ChatResponse]:
    """Process a chat request.
    
    The AI will analyze the message and may use available tools
    to query the GDELT database and generate a response.
    """
    response = await chat_service.chat(request)
    
    return APIResponse(
        success=True,
        data=response,
        meta={
            "tool_calls_count": len(response.tool_calls),
            "message_count": len(response.messages),
        },
    )
