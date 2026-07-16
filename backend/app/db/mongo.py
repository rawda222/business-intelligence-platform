"""
MongoDB Connection Manager

Uses Motor and Beanie for asynchronous MongoDB access.
"""

from beanie import init_beanie
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
)

from app.core.config import settings


# ============================================================
# Global MongoDB Client
# ============================================================
class MongoManager:
    """Store the shared MongoDB client and database."""

    client: AsyncIOMotorClient | None = None

    database: AsyncIOMotorDatabase | None = None


mongo_manager = MongoManager()


# ============================================================
# Connection Functions
# ============================================================
async def connect_to_mongo():
    """Initialize MongoDB and all registered Beanie models."""

    from app.models.mongo.customer_review import (
        CustomerReviewDocument,
    )
    from app.models.mongo.post_metric_snapshot import (
        PostMetricSnapshotDocument,
    )
    from app.models.mongo.social_comment import (
        SocialCommentDocument,
    )
    from app.models.mongo.social_post import (
        SocialPostDocument,
    )
    from app.models.mongo.strategy_report import (
        StrategyReportDocument,
    )
    from app.models.mongo.swot_report import (
        SWOTReportDocument,
    )

    document_models = [
        SWOTReportDocument,
        StrategyReportDocument,
        SocialPostDocument,
        SocialCommentDocument,
        CustomerReviewDocument,
        PostMetricSnapshotDocument,
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
    """Close the shared MongoDB client."""

    if mongo_manager.client:
        mongo_manager.client.close()

        mongo_manager.client = None
        mongo_manager.database = None

        print("[+] MongoDB closed")


# ============================================================
# Health Check
# ============================================================
async def check_mongo_health() -> dict:
    """Verify that MongoDB is accessible."""

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
            "version": info.get(
                "version",
                "unknown",
            ),
            "database": settings.MONGO_DB_NAME,
        }

    except Exception as error:
        return {
            "status": "unhealthy",
            "service": "mongodb",
            "error": str(error),
        }