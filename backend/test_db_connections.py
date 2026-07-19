"""
External database connection integration tests.

These tests require running PostgreSQL, MongoDB, and Redis services.
"""

import pytest

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


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]


async def test_postgres():
    """Verify PostgreSQL connectivity."""

    try:
        result = await check_postgres_health()

        assert result["status"] == "healthy"
        assert result["service"] == "postgresql"
    finally:
        await close_postgres()


async def test_mongo():
    """Verify MongoDB connectivity."""

    try:
        await connect_to_mongo()

        result = await check_mongo_health()

        assert result["status"] == "healthy"
        assert result["service"] == "mongodb"
    finally:
        await close_mongo()


async def test_redis():
    """Verify Redis connectivity."""

    try:
        await connect_to_redis()

        result = await check_redis_health()

        assert result["status"] == "healthy"
        assert result["service"] == "redis"
    finally:
        await close_redis()