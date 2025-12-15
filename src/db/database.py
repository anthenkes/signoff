"""
Database connection and session management using SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Lazy initialization - these will be set when init_db() is called
_engine: Optional[create_engine] = None
_SessionLocal: Optional[sessionmaker] = None


def init_db():
    """
    Initialize database connection. Call this before using the database.
    
    Raises:
        ValueError: If database configuration is missing
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        return  # Already initialized
    
    from .config import get_db_config
    db_config = get_db_config()
    
    # Create SQLAlchemy engine
    _engine = create_engine(
        db_config["database_url"],
        echo=db_config["echo"],
        pool_size=db_config["pool_size"],
        max_overflow=db_config["max_overflow"],
        pool_pre_ping=db_config["pool_pre_ping"],
    )
    
    # Create session factory
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    logger.info("Database initialized successfully")


def get_engine():
    """Get the database engine, initializing if necessary."""
    if _engine is None:
        init_db()
    return _engine


def get_session_local():
    """Get the session factory, initializing if necessary."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


# For direct access (will initialize on first use)
def __getattr__(name):
    if name == "engine":
        return get_engine()
    elif name == "SessionLocal":
        return get_session_local()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def get_db():
    """
    Dependency function for FastAPI to get database session.
    
    Yields:
        Database session
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

