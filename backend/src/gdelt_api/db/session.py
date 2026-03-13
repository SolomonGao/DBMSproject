"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gdelt_api.config import get_settings
from gdelt_api.core.logging import get_logger
from gdelt_api.db.base import Base

logger = get_logger(__name__)

# Global engine and session factory
_engine = None
_AsyncSessionLocal = None


async def init_db() -> None:
    """Initialize database connection."""
    global _engine, _AsyncSessionLocal
    
    settings = get_settings()
    
    logger.info(
        "initializing_database",
        host=settings.database.host,
        database=settings.database.name,
    )
    
    _engine = create_async_engine(
        settings.database.async_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        echo=settings.debug,  # Log SQL in debug mode
    )
    
    _AsyncSessionLocal = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    logger.info("database_initialized")


async def close_db() -> None:
    """Close database connection."""
    global _engine
    
    if _engine:
        await _engine.dispose()
        logger.info("database_closed")


async def create_tables() -> None:
    """Create all tables (for development/testing)."""
    global _engine
    
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("tables_created")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session as async context manager."""
    global _AsyncSessionLocal
    
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    session = _AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# For FastAPI dependency injection
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency."""
    global _AsyncSessionLocal
    
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    session = _AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()


AsyncSessionLocal = get_session
