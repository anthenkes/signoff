"""
AWS KMS configuration for loading credentials and key ID from environment variables.
"""
import os
from typing import Dict, Any, Optional
import logging

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def get_kms_config(mode: str = "encrypt") -> Dict[str, Any]:
    """
    Get AWS KMS configuration from environment variables.
    
    Args:
        mode: Either "encrypt" (for web server) or "decrypt" (for celery worker)
    
    Returns:
        Dictionary with KMS configuration including credentials and key ID
    
    Raises:
        ValueError: If required configuration is missing
    """
    # Determine which credentials to use based on mode
    if mode == "encrypt":
        access_key_id = os.getenv("AWS_ACCESS_KEY_ID_ENCRYPT")
        secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY_ENCRYPT")
    elif mode == "decrypt":
        access_key_id = os.getenv("AWS_ACCESS_KEY_ID_DECRYPT")
        secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY_DECRYPT")
    else:
        raise ValueError(f"Invalid mode: {mode}. Must be 'encrypt' or 'decrypt'")
    
    # Fallback to standard AWS credentials if mode-specific ones not set
    if not access_key_id:
        access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    if not secret_access_key:
        secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # Get KMS key ID
    kms_key_id = os.getenv("AWS_KMS_KEY_ID")
    
    # Get AWS region
    aws_region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
    
    # Validate required fields
    if not access_key_id:
        raise ValueError(
            f"AWS_ACCESS_KEY_ID_{mode.upper()} or AWS_ACCESS_KEY_ID environment variable is required"
        )
    
    if not secret_access_key:
        raise ValueError(
            f"AWS_SECRET_ACCESS_KEY_{mode.upper()} or AWS_SECRET_ACCESS_KEY environment variable is required"
        )
    
    if not kms_key_id:
        raise ValueError("AWS_KMS_KEY_ID environment variable is required")
    
    if not aws_region:
        raise ValueError("AWS_DEFAULT_REGION or AWS_REGION environment variable is required")
    
    return {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
        "kms_key_id": kms_key_id,
        "region": aws_region,
    }


def get_kms_key_id() -> str:
    """
    Get the KMS key ID from environment variables.
    
    Returns:
        The KMS key ID or ARN
    
    Raises:
        ValueError: If AWS_KMS_KEY_ID is not set
    """
    kms_key_id = os.getenv("AWS_KMS_KEY_ID")
    if not kms_key_id:
        raise ValueError("AWS_KMS_KEY_ID environment variable is required")
    return kms_key_id

