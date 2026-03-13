"""Common response models."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error detail model."""
    
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    detail: dict[str, Any] | None = Field(None, description="Additional error details")
    status: int = Field(..., description="HTTP status code")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    
    success: bool = Field(True, description="Whether the request was successful")
    data: T | None = Field(None, description="Response data")
    error: ErrorDetail | None = Field(None, description="Error information")
    meta: dict[str, Any] | None = Field(None, description="Response metadata")


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total: int = Field(0, description="Total number of items")
    total_pages: int = Field(0, description="Total number of pages")
    has_next: bool = Field(False, description="Whether there is a next page")
    has_prev: bool = Field(False, description="Whether there is a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    items: list[T] = Field(default_factory=list, description="List of items")
    pagination: PaginationMeta = Field(default_factory=PaginationMeta)
