"""
Database configuration and session management.

This module provides SQLAlchemy database engine, session management, and base model classes.
It handles database connection pooling, SSL configuration for production, and provides
a dependency injection function for FastAPI route handlers.

Key Features:
- Automatic SSL mode handling for localhost connections
- Connection pooling (pool_size: 10, max_overflow: 20)
- TimestampMixin for automatic created_at/updated_at fields
- Database initialization function for startup
- Session dependency for FastAPI routes

Configuration:
- DATABASE_URL: PostgreSQL connection string (from environment)
- DATABASE_POOL_SIZE: Connection pool size (default: 10)
- DATABASE_MAX_OVERFLOW: Maximum pool overflow (default: 20)
- Supports SQLite for testing (automatic SSL handling skipped)
- SSL mode automatically disabled for localhost connections

**Documentation References:**
- URL Configuration: See `app/config/database_url.py` for URL parsing utilities
- Models: See `app/models/database.py` for database models
- Alembic: See `alembic/env.py` for migration configuration
"""
import os
from typing import Generator, Optional

from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, DateTime, Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, sessionmaker as SessionMaker

from sqlalchemy.sql import func

from app.config.database_url import get_database_url
from app.utils.logger import get_logger

# Load .env file before reading environment variables
load_dotenv()

logger = get_logger(__name__)

# Database URL from environment with SSL handling
# load_env=False since we already loaded it above
DATABASE_URL = get_database_url(
    default="postgresql://user:password@localhost:5432/marb_risk_engine",
    load_env=False,
)

# Base class for models (must be created before models are imported)
Base = declarative_base()


class TimestampMixin:
    """
    Mixin class for common timestamp fields.
    
    Provides automatic created_at and updated_at timestamp columns
    for all models that inherit from this mixin.
    
    Usage:
        class MyModel(Base, TimestampMixin):
            # Model fields
            pass
    """
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


def create_database_engine(
    database_url: Optional[str] = None,
    pool_size: Optional[int] = None,
    max_overflow: Optional[int] = None,
    pool_pre_ping: bool = True,
    echo: bool = False,
) -> Engine:
    """
    Create SQLAlchemy database engine with connection pooling.
    
    Args:
        database_url: Database connection URL (defaults to DATABASE_URL from environment)
        pool_size: Connection pool size (defaults to DATABASE_POOL_SIZE env var or 10)
        max_overflow: Maximum pool overflow (defaults to DATABASE_MAX_OVERFLOW env var or 20)
        pool_pre_ping: Enable connection health checks (default: True)
        echo: Enable SQL query logging (default: False)
        
    Returns:
        Configured SQLAlchemy Engine instance
    """
    url = database_url or DATABASE_URL
    pool_size = pool_size or int(os.getenv("DATABASE_POOL_SIZE", "10"))
    max_overflow = max_overflow or int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        echo=echo,
    )


def create_session_factory(
    engine: Optional[Engine] = None,
    autocommit: bool = False,
    autoflush: bool = False,
) -> SessionMaker:
    """
    Create SQLAlchemy session factory.
    
    Args:
        engine: Database engine to bind sessions to (defaults to module-level engine)
        autocommit: Enable autocommit mode (default: False)
        autoflush: Enable autoflush mode (default: False)
        
    Returns:
        Configured sessionmaker instance
    """
    if engine is None:
        engine = _engine
    
    return sessionmaker(autocommit=autocommit, autoflush=autoflush, bind=engine)


# Create engine (module-level for backward compatibility)
_engine = create_database_engine()
engine = _engine  # Public export

# Session factory (module-level for backward compatibility)
_SessionLocal = create_session_factory()
SessionLocal = _SessionLocal  # Public export


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.
    
    This function is used as a FastAPI dependency to provide database sessions
    to route handlers. The session is automatically closed after the request.
    
    Yields:
        Database session instance
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_all_models():
    """
    Get all database models for registration.
    
    This function imports all models to ensure they're registered with Base.metadata.
    Models are imported from app.models.database module.
    
    Returns:
        List of model classes (for reference, not used directly)
    """
    # Import all models to ensure they're registered with Base.metadata
    from app.models.database import (  # noqa: F401
        Claim,
        Remittance,
        ClaimEpisode,
        Payer,
        DenialPattern,
        RiskScore,
        Provider,
        Plan,
        PracticeConfig,
        ParserLog,
        AuditLog,
    )
    
    # Return list for potential future use (e.g., introspection)
    return [
        Claim,
        Remittance,
        ClaimEpisode,
        Payer,
        DenialPattern,
        RiskScore,
        Provider,
        Plan,
        PracticeConfig,
        ParserLog,
        AuditLog,
    ]


async def init_db() -> None:
    """
    Initialize database (create tables if needed).
    
    This function:
    1. Imports all database models to register them with Base.metadata
    2. Creates all tables defined in the models
    
    Should be called during application startup (see app/core/application.py).
    
    Raises:
        Exception: If database initialization fails
    """
    try:
        # Import all models to ensure they're registered
        get_all_models()
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise
