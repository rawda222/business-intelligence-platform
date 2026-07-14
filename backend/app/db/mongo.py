"""
MongoDB Connection Manager
Uses Motor + Beanie for async ODM.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie

from app.core.config import settings


# ============================================================
# Global MongoDB Client
# ============================================================
class MongoManager:
    client: AsyncIOMotorClient | None = None
    database: AsyncIOMotorDatabase | None = None


mongo_manager = MongoManager()


# ============================================================
# Connection Functions
# ============================================================
async def connect_to_mongo():
    """Initialize MongoDB connection and Beanie ODM on app startup."""

    from app.models.mongo.social_post import SocialPostDocument
    from app.models.mongo.strategy_report import StrategyReportDocument
    from app.models.mongo.swot_report import SWOTReportDocument

    document_models = [
        SWOTReportDocument,
        StrategyReportDocument,
        SocialPostDocument,
    ]

    mongo_manager.client = AsyncIOMotorClient(
        settings.MONGO_URL,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=10,
        minPoolSize=1,
    )

    mongo_manager.database = mongo_manager.client[
        settings.MONGO_DB_NAME
    ]

    await init_beanie(
        database=mongo_manager.database,
        document_models=document_models,
    )

    print(
        f"[+] Connected to MongoDB: "
        f"{settings.MONGO_DB_NAME}"
    )

    print(
        f"[+] Beanie initialized with "
        f"{len(document_models)} document models"
    )

async def close_mongo():
    """Close MongoDB connection."""
    if mongo_manager.client:
        mongo_manager.client.close()
        print("[+] MongoDB closed")


# ============================================================
# Health Check
# ============================================================
async def check_mongo_health() -> dict:
    """Verify MongoDB is accessible."""
    try:
        if not mongo_manager.client:
            return {
                "status": "unhealthy",
                "service": "mongodb",
                "error": "Not connected",
            }
        
        info = await mongo_manager.client.server_info()
        return {
            "status": "healthy",
            "service": "mongodb",
            "version": info.get("version", "unknown"),
            "database": settings.MONGO_DB_NAME,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "mongodb",
            "error": str(e),
        }