"""
Database configuration for PostgreSQL with SQLAlchemy.
"""
import os
from typing import Dict, Any
import logging

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    
    Returns:
        Dictionary with database configuration
    
    Raises:
        ValueError: If required database configuration is missing
    """
    # PostgreSQL connection string
    # Format: postgresql://user:password@host:port/database
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        # Try to construct from individual components
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        
        if db_user and db_password and db_name:
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            raise ValueError(
                "Database configuration missing. Either set DATABASE_URL or "
                "set DB_USER, DB_PASSWORD, and DB_NAME environment variables."
            )
    
    return {
        "database_url": database_url,
        "echo": os.getenv("DB_ECHO", "false").lower() == "true",  # SQLAlchemy echo mode
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
    }

