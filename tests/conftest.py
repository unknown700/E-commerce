import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

# Settings come from .env. On a machine without .env (for example CI) use defaults.
if not Path(".env").exists():
    os.environ.setdefault("BOT_TOKEN", "123456:TEST")
    os.environ.setdefault("POSTGRES_USER", "shop")
    os.environ.setdefault("POSTGRES_PASSWORD", "shop_pass")
    os.environ.setdefault("POSTGRES_DB", "shop_db")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("ADMIN_IDS", "1")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import models  # noqa: E402,F401  (registers all tables)
from app.database.base import Base  # noqa: E402

TEST_DB = "shop_test"
assert TEST_DB != settings.postgres_db, "tests must never use the real database"


def _url(database: str) -> str:
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{database}"
    )


TEST_URL = _url(TEST_DB)


async def _prepare_database() -> None:
    admin = create_async_engine(
        _url("postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    async with admin.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    await admin.dispose()

    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    asyncio.run(_prepare_database())


@pytest_asyncio.fixture
async def session():
    """A session inside a transaction that is rolled back after every test."""
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield db_session
        finally:
            await db_session.close()
            await transaction.rollback()
    await engine.dispose()