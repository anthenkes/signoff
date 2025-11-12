"""
Email configuration for Resend API.
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


def get_email_config() -> Dict[str, Any]:
    """
    Get email configuration from environment variables.
    
    Returns:
        Dictionary with email configuration
    
    Raises:
        ValueError: If required email configuration is missing
    """
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL")
    
    if not api_key:
        raise ValueError("RESEND_API_KEY environment variable is required")
    
    if not from_email:
        raise ValueError("RESEND_FROM_EMAIL environment variable is required")
    
    return {
        "api_key": api_key,
        "from_email": from_email,
        "from_name": os.getenv("RESEND_FROM_NAME", "Time Card Automation")
    }

