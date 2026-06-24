"""
Authentication Service
Business logic for user registration and authentication.
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.models.pg.user import User
from app.schemas.user import UserCreate


# ============================================================
# User Registration
# ============================================================
async def register_user(
    db: AsyncSession,
    user_data: UserCreate,
) -> User:
    """
    Register a new user.
    
    Args:
        db: Database session
        user_data: User registration data (from API)
    
    Returns:
        Created User object
    
    Raises:
        ValueError: If email already exists
    """
    # 1. Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise ValueError(f"Email {user_data.email} already registered")
    
    # 2. Hash the password
    hashed_pw = hash_password(user_data.password)
    
    # 3. Create User model
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_pw,
        full_name=user_data.full_name,
        is_active=True,
        is_verified=False,
        role="user",
    )
    
    # 4. Save to DB
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


# ============================================================
# User Authentication
# ============================================================
async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
    
    Returns:
        User object if credentials valid, None otherwise
    """
    # 1. Find user by email
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    # 2. User not found
    if not user:
        return None
    
    # 3. Verify password
    if not verify_password(password, user.hashed_password):
        return None
    
    # 4. Check if user is active
    if not user.is_active:
        return None
    
    return user


# ============================================================
# Get User by ID
# ============================================================
async def get_user_by_id(
    db: AsyncSession,
    user_id: UUID,
) -> User | None:
    """
    Get a user by their ID.
    
    Args:
        db: Database session
        user_id: UUID of the user
    
    Returns:
        User object or None if not found
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()