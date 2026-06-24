"""
Common Schemas
Shared Pydantic schemas used across multiple modules.
"""
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict


# ============================================================
# Generic Type for Pagination
# ============================================================
T = TypeVar("T")


# ============================================================
# Base Schema
# ============================================================
class BaseSchema(BaseModel):
    """
    Base schema for all Pydantic models.
    Configures common behaviors.
    """
    model_config = ConfigDict(
        from_attributes=True,      # Allow loading from SQLAlchemy models
        populate_by_name=True,     # Allow field aliases
        str_strip_whitespace=True, # Auto-strip whitespace
    )


# ============================================================
# Timestamp Mixin
# ============================================================
class TimestampSchema(BaseSchema):
    """Schema with created_at and updated_at timestamps."""
    created_at: datetime
    updated_at: datetime | None = None


# ============================================================
# ID Mixin
# ============================================================
class IDSchema(BaseSchema):
    """Schema with UUID id field."""
    id: UUID


# ============================================================
# Pagination Response
# ============================================================
class PaginatedResponse(BaseSchema, Generic[T]):
    """
    Generic paginated response.
    
    Usage:
        PaginatedResponse[UserResponse]
    """
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================
# Success Response
# ============================================================
class SuccessResponse(BaseSchema):
    """Generic success response."""
    success: bool = True
    message: str


# ============================================================
# Error Response
# ============================================================
class ErrorDetail(BaseSchema):
    """Error detail."""
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseSchema):
    """Generic error response."""
    success: bool = False
    errors: list[ErrorDetail]