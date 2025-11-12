"""
FastAPI endpoints configuration.
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


def get_api_config() -> Dict[str, Any]:
    """
    Get API configuration settings.
    
    Returns:
        Dictionary with API configuration
    """
    return {
        "title": os.getenv("API_TITLE", "Time Card Sign-Off API"),
        "description": os.getenv("API_DESCRIPTION", "API for time card sign-off automation"),
        "version": os.getenv("API_VERSION", "1.0.0"),
        "host": os.getenv("API_HOST", "0.0.0.0"),
        "port": int(os.getenv("API_PORT", "8000")),
        "reload": os.getenv("API_RELOAD", "false").lower() == "true",
    }

