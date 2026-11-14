"""
Async database engine — uses aiosqlite so DB I/O never blocks the event loop.

OPTIMIZATION: Replaced synchronous create_engine/sessionmaker with async
equivalents. This is the single biggest win for real-time performance:
disk I/O now runs in aiosqlite's background thread, not on the asyncio loop.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Convert sqlite:///./fogguard.db → sqlite+aiosqlite:///./fogguard.db
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("sqlite:///"):
    SQLALCHEMY_DATABASE_URL = _raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    SQLALCHEMY_DATABASE_URL = _raw_url

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    # aiosqlite handles thread-safety internally — no check_same_thread needed
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Avoid lazy-load issues after commit
)

Base = declarative_base()


async def get_db():
    """FastAPI dependency — yields an AsyncSession, auto-closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables (runs DDL synchronously inside the async engine)."""
    from app.models import sensor  # noqa: F401 — registers models with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
