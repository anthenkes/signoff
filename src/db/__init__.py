"""
Database module for PostgreSQL with SQLAlchemy.
"""
from .models import Base
from .database import init_db, get_engine, get_session_local
from .config import get_db_config

# For backward compatibility, expose these as properties
# They will initialize the database on first access
def __getattr__(name):
    if name == "engine":
        return get_engine()
    elif name == "SessionLocal":
        return get_session_local()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "Base",
    "init_db",
    "get_engine",
    "get_session_local",
    "get_db_config",
    "engine",  # Available via __getattr__
    "SessionLocal",  # Available via __getattr__
]

