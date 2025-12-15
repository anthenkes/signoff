"""
Cookie-based authentication utilities for credentials form access.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Cookie name
COOKIE_NAME = "credentials_auth"
# Cookie expiration: 30 minutes
COOKIE_EXPIRATION_MINUTES = 30


def get_cookie_secret() -> str:
    """
    Get the secret key for signing cookies from environment variables.
    
    Returns:
        The secret key
    
    Raises:
        ValueError: If COOKIE_SECRET_KEY is not set
    """
    secret = os.getenv("COOKIE_SECRET_KEY")
    if not secret:
        raise ValueError("COOKIE_SECRET_KEY environment variable is required")
    return secret


def create_credentials_cookie(email: str) -> str:
    """
    Create a signed cookie token for credentials form access.
    
    Args:
        email: The user's email address
    
    Returns:
        A signed token string that can be used as a cookie value
    """
    secret = get_cookie_secret()
    serializer = URLSafeTimedSerializer(secret)
    
    # Create payload with email and expiration timestamp
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=COOKIE_EXPIRATION_MINUTES)
    payload = {
        "email": email,
        "expires_at": expires_at.isoformat()
    }
    
    # Sign the payload
    token = serializer.dumps(payload)
    
    logger.info(f"Created credentials cookie for email: {email}")
    return token


def verify_credentials_cookie(token: str) -> str:
    """
    Verify and extract email from a credentials cookie token.
    
    Args:
        token: The signed token from the cookie
    
    Returns:
        The user's email address
    
    Raises:
        ValueError: If token is invalid or expired
    """
    secret = get_cookie_secret()
    serializer = URLSafeTimedSerializer(secret)
    
    try:
        # Verify and load the payload
        payload = serializer.loads(token, max_age=COOKIE_EXPIRATION_MINUTES * 60)
        
        email = payload.get("email")
        if not email:
            raise ValueError("Invalid cookie: missing email")
        
        # Check expiration
        expires_at_str = payload.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires_at:
                raise ValueError("Cookie has expired")
        
        return email
    
    except SignatureExpired:
        raise ValueError("Cookie has expired")
    except BadSignature:
        raise ValueError("Invalid cookie signature")
    except Exception as e:
        logger.error(f"Error verifying cookie: {e}")
        raise ValueError("Invalid cookie")

