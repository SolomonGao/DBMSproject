"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_endpoint(client: AsyncClient) -> None:
    """Test health check endpoint."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "healthy"


@pytest.mark.integration
async def test_chat_endpoint_validation(client: AsyncClient) -> None:
    """Test chat endpoint validation."""
    # Missing required field
    response = await client.post("/api/v1/chat", json={})
    assert response.status_code == 422
    
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.integration
async def test_chat_endpoint_empty_messages(client: AsyncClient) -> None:
    """Test chat endpoint with empty messages."""
    response = await client.post(
        "/api/v1/chat",
        json={"messages": []}
    )
    assert response.status_code == 422
