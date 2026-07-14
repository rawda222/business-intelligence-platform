"""
Alembic Environment Configuration

Connects to PostgreSQL using an async SQLAlchemy engine.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.postgres import Base

# Import all PostgreSQL models so Alembic can detect them.
from app.models.pg import (  # noqa: F401
    User,
    Business,
    Report,
    Initiative,
    SocialAccount,
)


# ============================================================
# Alembic Config
# ============================================================
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ============================================================
# Offline Mode
# ============================================================
def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# Online Mode
# ============================================================
def do_run_migrations(connection: Connection) -> None:
    """Run migrations using an existing database connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async connection and run Alembic migrations."""

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    asyncio.run(run_async_migrations())


# ============================================================
# Main
# ============================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()