"""
Authentication Schemas
Schemas for login, tokens, and authentication flows.
"""
from datetime import datetime
from uuid import UUID
from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema
from app.schemas.user import UserResponse


# ============================================================
# Input: Login Request
# ============================================================
class LoginRequest(BaseSchema):
    """
    Login credentials.
    Used in: POST /auth/login
    """
    email: EmailStr
    password: str = Field(..., min_length=1)


# ============================================================
# Output: Token Response
# ============================================================
class TokenResponse(BaseSchema):
    """
    JWT token response after successful login.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


# ============================================================
# Input: Refresh Token
# ============================================================
class RefreshTokenRequest(BaseSchema):
    """
    Refresh token request to get new access token.
    Used in: POST /auth/refresh
    """
    refresh_token: str


# ============================================================
# Internal: Token Payload
# ============================================================
class TokenPayload(BaseSchema):
    """
    Decoded JWT token payload.
    Internal use only.
    """
    sub: str  # user_id as string
    exp: datetime
    type: str  # "access" or "refresh"