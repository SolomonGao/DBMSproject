"""API v1 routes."""

from fastapi import APIRouter

from gdelt_api.api.v1.endpoints import chat, events, health

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
