"""
FastAPI Dependencies
Reusable dependencies for authentication and authorization.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.postgres import get_db
from app.models.pg.user import User
from app.services.auth_service import get_user_by_id


# ============================================================
# HTTP Bearer Security Scheme
# ============================================================
# This makes Swagger UI show a clean "Authorize" button
# that accepts JWT tokens directly (no username/password fields)
bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="Paste your access_token here (without 'Bearer' prefix)",
)


# ============================================================
# Get Current User from JWT Token
# ============================================================
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode JWT token and return the current user.
    
    Usage in endpoints:
        @app.get("/me")
        async def my_endpoint(user: User = Depends(get_current_user)):
            return user
    
    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Extract the actual token from credentials
    token = credentials.credentials
    
    # 1. Decode the token
    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id_str is None:
            raise credentials_exception
        
        # Make sure it's an access token, not refresh
        if token_type != "access":
            raise credentials_exception
        
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception
    
    # 2. Get user from DB
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    # 3. Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    return user