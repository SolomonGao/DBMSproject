"""Unit tests for models."""

import pytest
from pydantic import ValidationError

from gdelt_api.models.chat import ChatRequest, Message


class TestMessage:
    """Test Message model."""
    
    def test_valid_message(self) -> None:
        """Test creating a valid message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_empty_content_raises(self) -> None:
        """Test that empty content raises validation error."""
        with pytest.raises(ValidationError):
            Message(role="user", content="")
    
    def test_whitespace_content_raises(self) -> None:
        """Test that whitespace-only content raises validation error."""
        with pytest.raises(ValidationError):
            Message(role="user", content="   ")


class TestChatRequest:
    """Test ChatRequest model."""
    
    def test_valid_request(self) -> None:
        """Test creating a valid chat request."""
        req = ChatRequest(
            messages=[
                Message(role="user", content="Hello")
            ]
        )
        assert len(req.messages) == 1
    
    def test_no_user_message_raises(self) -> None:
        """Test that request without user message raises error."""
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[
                    Message(role="assistant", content="Hi")
                ]
            )
    
    def test_temperature_out_of_range(self) -> None:
        """Test temperature validation."""
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[Message(role="user", content="Hello")],
                temperature=3.0,  # Must be <= 2.0
            )
