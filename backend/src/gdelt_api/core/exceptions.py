"""Custom exceptions for GDELT API."""

from http import HTTPStatus
from typing import Any


class GDELTAPIError(Exception):
    """Base exception for GDELT API."""
    
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    detail: str = "An internal error occurred"
    
    def __init__(
        self,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.detail
        self.error_detail = detail or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "detail": self.error_detail,
                "status": self.status_code,
            }
        }


class NotFoundError(GDELTAPIError):
    """Resource not found exception."""
    
    status_code = HTTPStatus.NOT_FOUND
    error_code = "NOT_FOUND"
    detail = "Resource not found"


class ValidationError(GDELTAPIError):
    """Validation error exception."""
    
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    detail = "Validation failed"


class AuthenticationError(GDELTAPIError):
    """Authentication error exception."""
    
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "AUTHENTICATION_ERROR"
    detail = "Authentication failed"


class AuthorizationError(GDELTAPIError):
    """Authorization error exception."""
    
    status_code = HTTPStatus.FORBIDDEN
    error_code = "AUTHORIZATION_ERROR"
    detail = "Not authorized"


class ConflictError(GDELTAPIError):
    """Resource conflict exception."""
    
    status_code = HTTPStatus.CONFLICT
    error_code = "CONFLICT"
    detail = "Resource conflict"


class RateLimitError(GDELTAPIError):
    """Rate limit exceeded exception."""
    
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    detail = "Rate limit exceeded"


class LLMError(GDELTAPIError):
    """LLM API error exception."""
    
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "LLM_ERROR"
    detail = "LLM service error"


class MCPError(GDELTAPIError):
    """MCP server error exception."""
    
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "MCP_ERROR"
    detail = "MCP server error"


class DatabaseError(GDELTAPIError):
    """Database error exception."""
    
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "DATABASE_ERROR"
    detail = "Database error"


class ServiceUnavailableError(GDELTAPIError):
    """Service unavailable exception."""
    
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "SERVICE_UNAVAILABLE"
    detail = "Service temporarily unavailable"
