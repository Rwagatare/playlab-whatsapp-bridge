"""Alembic migration environment.

This file tells Alembic how to connect to the database and which
tables to manage. It reads DATABASE_URL from the .env file and
uses async mode since we use asyncpg.
"""

import asyncio
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base so Alembic knows about all our tables.
from app.db.base import Base
import app.db.models  # noqa: F401 — registers models on Base.metadata

load_dotenv()

config = context.config
target_metadata = Base.metadata


def get_url() -> str:
    """Read DATABASE_URL from environment."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required for migrations")
    return url


def run_migrations_offline() -> None:
    """Generate SQL scripts without connecting to the database."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database using async engine."""
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
