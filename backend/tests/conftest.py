"""
Shared Pytest Configuration

Provides automatic cleanup for the async SQLAlchemy engine after
every test.

This prevents pooled asyncpg connections created in one pytest
event loop from being reused in another event loop.
"""

import pytest_asyncio

from app.db.postgres import engine


@pytest_asyncio.fixture(autouse=True)
async def dispose_database_engine_after_test():
    """
    Dispose all pooled database connections after each test.

    pytest-asyncio may create a separate event loop for each test.
    Async PostgreSQL connections must not be reused across different
    event loops, especially on Windows with ProactorEventLoop.
    """

    yield

    await engine.dispose()