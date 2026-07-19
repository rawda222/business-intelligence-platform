"""
Business Intelligence Platform - Main Application

Includes:
- Full AI pipeline
- Multi-tenant business management
- Social-account management
- Development CORS configuration
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import trends

from app.api.v1 import (
    analysis,
    auth,
    businesses,
    creative_themes,
    full_pipeline,
    reports,
    social_accounts,
    swot,
    swot_updates,
    strategy,
)
from app.core.config import settings
from app.db.mongo import (
    check_mongo_health,
    close_mongo,
    connect_to_mongo,
)
from app.db.postgres import (
    check_postgres_health,
    close_postgres,
)
from app.db.redis_client import (
    check_redis_health,
    close_redis,
    connect_to_redis,
)


# ============================================================
# Application Lifecycle
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and close external application resources."""

    print("\n" + "=" * 60)
    print(f"  Starting {settings.APP_NAME}")
    print("=" * 60)

    await connect_to_mongo()
    await connect_to_redis()

    print("[+] All connections established\n")

    yield

    print("\n  Shutting down...")

    await close_mongo()
    await close_redis()
    await close_postgres()


# ============================================================
# FastAPI Application
# ============================================================
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Multi-tenant AI-powered Business Intelligence Platform"
    ),
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


# ============================================================
# CORS Middleware - Development Configuration
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ============================================================
# API Routers
# ============================================================
app.include_router(
    auth.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    businesses.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    creative_themes.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    social_accounts.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    swot.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    swot_updates.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    strategy.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    analysis.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    full_pipeline.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    reports.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    trends.router,
    prefix=settings.API_V1_PREFIX,
)

# ============================================================
# Root Endpoint
# ============================================================
@app.get("/")
async def root():
    """Return basic application information."""

    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "status": "running",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


# ============================================================
# Health Endpoints
# ============================================================
@app.get("/health")
async def health_check():
    """Basic application liveness check."""

    return {
        "status": "healthy",
        "service": "bi-platform-api",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/deep")
async def deep_health_check():
    """Verify PostgreSQL, MongoDB, and Redis connectivity."""

    postgres_health = await check_postgres_health()
    mongo_health = await check_mongo_health()
    redis_health = await check_redis_health()

    all_healthy = all(
        [
            postgres_health["status"] == "healthy",
            mongo_health["status"] == "healthy",
            redis_health["status"] == "healthy",
        ]
    )

    return {
        "status": (
            "healthy"
            if all_healthy
            else "degraded"
        ),
        "service": "bi-platform-api",
        "environment": settings.ENVIRONMENT,
        "databases": {
            "postgresql": postgres_health,
            "mongodb": mongo_health,
            "redis": redis_health,
        },
    }


# ============================================================
# Application Information
# ============================================================
@app.get("/info")
async def info():
    """Return enabled application capabilities."""

    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "features": [
            "JWT Authentication",
            "Business Management (CRUD)",
            "Social Account Management",
            "AI-powered SWOT (Vertex AI Gemini)",
            "Strategy Agent (Vertex AI Gemini)",
            (
                "Full Pipeline "
                "(Normalize -> Themes -> SWOT -> Strategy)"
            ),
            "MongoDB Reports Storage",
        ],
    }
