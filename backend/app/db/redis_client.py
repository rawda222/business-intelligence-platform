"""
Redis Connection Manager
Handles async Redis connections for caching and pub/sub.
"""
import redis.asyncio as redis

from app.core.config import settings


# ============================================================
# Global Redis Client
# ============================================================
class RedisManager:
    """Manages Redis client lifecycle."""
    client: redis.Redis | None = None


redis_manager = RedisManager()


# ============================================================
# Connection Functions
# ============================================================
async def connect_to_redis():
    """Initialize Redis connection on app startup."""
    redis_manager.client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await redis_manager.client.ping()
    print(f"[+] Connected to Redis")


async def close_redis():
    """Close Redis connection."""
    if redis_manager.client:
        await redis_manager.client.aclose()
        print("[+] Redis closed")


# ============================================================
# Health Check
# ============================================================
async def check_redis_health() -> dict:
    """Verify Redis is accessible."""
    try:
        if not redis_manager.client:
            return {"status": "unhealthy", "service": "redis", "error": "Not connected"}
        
        await redis_manager.client.ping()
        info = await redis_manager.client.info("server")
        return {
            "status": "healthy",
            "service": "redis",
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "redis",
            "error": str(e),
        }