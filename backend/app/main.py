"""
Business Intelligence Platform - Main Application
With Full Pipeline (Normalize → Themes → SWOT v7 → Strategy)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # ✅ NEW

from app.core.config import settings
from app.db.mongo import connect_to_mongo, close_mongo, check_mongo_health
from app.db.redis_client import connect_to_redis, close_redis, check_redis_health
from app.db.postgres import check_postgres_health, close_postgres

# Routers
from app.api.v1 import auth, businesses, swot, analysis, full_pipeline


# ============================================================
# Lifespan Manager
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
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
# FastAPI App
# ============================================================
app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant AI-powered Business Intelligence Platform",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# ============================================================
# ✅ CORS Middleware (LINK to Frontend on :3000)
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Include Routers
# ============================================================
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(businesses.router, prefix=settings.API_V1_PREFIX)
app.include_router(swot.router, prefix=settings.API_V1_PREFIX)
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)
app.include_router(full_pipeline.router, prefix=settings.API_V1_PREFIX)


# ============================================================
# Root Endpoints
# ============================================================
@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "status": "running",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "bi-platform-api",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health/deep")
async def deep_health_check():
    postgres_health = await check_postgres_health()
    mongo_health = await check_mongo_health()
    redis_health = await check_redis_health()

    all_healthy = all([
        postgres_health["status"] == "healthy",
        mongo_health["status"] == "healthy",
        redis_health["status"] == "healthy",
    ])

    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": "bi-platform-api",
        "environment": settings.ENVIRONMENT,
        "databases": {
            "postgresql": postgres_health,
            "mongodb": mongo_health,
            "redis": redis_health,
        },
    }


@app.get("/info")
async def info():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "features": [
            "JWT Authentication",
            "Business Management (CRUD)",
            "AI-powered SWOT v7 (Vertex AI Gemini)",
            "Strategy Agent v1 (Vertex AI Gemini)",
            "Full Pipeline (Normalize -> Themes -> SWOT -> Strategy)",
            "MongoDB Reports Storage",
        ],
    }