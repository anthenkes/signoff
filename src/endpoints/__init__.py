"""
FastAPI endpoints module.
"""
from .main import app
from .config import get_api_config

__all__ = [
    "app",
    "get_api_config",
]

