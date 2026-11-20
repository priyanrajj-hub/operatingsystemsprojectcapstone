"""
Asynchronous database engine configuration and session management for AI-DAX.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from persistence.models import Base

logger = logging.getLogger("aidax.persistence.database")


def create_engine_and_sessionmaker(
    database_url: str = "sqlite+aiosqlite:///data/aidax.db",
    echo: bool = False,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Initialize an asynchronous database engine and session factory."""
    if database_url.startswith("sqlite+aiosqlite:///"):
        db_path = database_url.replace("sqlite+aiosqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        database_url,
        echo=echo,
        future=True,
    )

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_maker


async def init_db(engine: AsyncEngine) -> None:
    """Create all database tables asynchronously if they do not exist."""
    logger.info("Initializing database schemas...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schemas initialized successfully.")


class DatabaseManager:
    """Singleton-style database manager providing async sessions across the application."""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///data/aidax.db") -> None:
        self.database_url = database_url
        self.engine, self.session_maker = create_engine_and_sessionmaker(database_url)

    async def initialize(self) -> None:
        """Initialize database schema tables."""
        await init_db(self.engine)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async generator yielding an active database session with automatic commit/rollback."""
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
