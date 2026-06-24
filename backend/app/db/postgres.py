"""
PostgreSQL Connection Manager
Handles async PostgreSQL connections using SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import settings


# ============================================================
# Async Engine (Connection Pool)
# ============================================================
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,                # Set to True to see SQL queries
    pool_size=10,              # Keep 10 connections ready
    max_overflow=5,            # Allow 5 extra if needed
    pool_pre_ping=True,        # Check connection health
    pool_recycle=3600,         # Recycle connections every hour
)


# ============================================================
# Session Factory
# ============================================================
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ============================================================
# Base Model
# ============================================================
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ============================================================
# Health Check
# ============================================================
async def check_postgres_health() -> dict:
    """Verify PostgreSQL is accessible."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar()
        return {
            "status": "healthy",
            "service": "postgresql",
            "version": version.split(",")[0] if version else "unknown",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "postgresql",
            "error": str(e),
        }


# ============================================================
# Lifecycle
# ============================================================
async def close_postgres():
    """Close all DB connections on app shutdown."""
    await engine.dispose()

   # ============================================================
# FastAPI Dependency
# ============================================================
async def get_db():
    """
    FastAPI dependency that provides a database session.
    
    Usage in endpoints:
        @app.get("/endpoint")
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close() 