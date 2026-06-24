"""
User Schemas
Pydantic schemas for User API operations.
"""
from datetime import datetime
from uuid import UUID
from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


# ============================================================
# Base User Schema (shared fields)
# ============================================================
class UserBase(BaseSchema):
    """Base user fields shared across operations."""
    email: EmailStr
    full_name: str | None = Field(None, max_length=255)


# ============================================================
# Input: Create User (registration)
# ============================================================
class UserCreate(UserBase):
    """
    Schema for creating a new user.
    Used in: POST /auth/register
    """
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (will be hashed)",
    )


# ============================================================
# Input: Update User
# ============================================================
class UserUpdate(BaseSchema):
    """
    Schema for updating user details.
    All fields optional - partial update.
    Used in: PATCH /users/me
    """
    full_name: str | None = Field(None, max_length=255)
    email: EmailStr | None = None


# ============================================================
# Input: Change Password
# ============================================================
class UserChangePassword(BaseSchema):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ============================================================
# Output: User Response (safe to expose)
# ============================================================
class UserResponse(UserBase, IDSchema, TimestampSchema):
    """
    Schema for returning user data.
    Excludes sensitive fields like hashed_password.
    
    Used in: GET /users/me, POST /auth/register response
    """
    is_active: bool
    is_verified: bool
    role: str


# ============================================================
# Output: User in DB (internal use)
# ============================================================
class UserInDB(UserResponse):
    """
    Internal schema with hashed_password.
    NEVER return this from API endpoints.
    """
    hashed_password: str