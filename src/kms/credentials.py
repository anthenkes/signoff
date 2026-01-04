"""
Utility functions for decrypting user credentials from the database.
Used by celery worker to retrieve and decrypt credentials for timecard automation.
"""
from typing import Optional, Tuple
import logging
from sqlalchemy.orm import Session

from src.db.models import User, Credential
from .service import KMSDecryptService

logger = logging.getLogger(__name__)


def decrypt_user_credentials(
    db: Session,
    user_email: Optional[str] = None,
    user_id: Optional[int] = None
) -> Tuple[str, str]:
    """
    Decrypt credentials for a user from the database.
    
    Args:
        db: Database session
        user_email: User's email address (optional, if user_id not provided)
        user_id: User's database ID (optional, if user_email not provided)
    
    Returns:
        Tuple of (username, password) as plaintext strings
    
    Raises:
        ValueError: If user not found or credentials not found
        Exception: If decryption fails
    """
    # Get user
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    elif user_email:
        user = db.query(User).filter(User.email == user_email.lower()).first()
    else:
        raise ValueError("Either user_email or user_id must be provided")
    
    if not user:
        raise ValueError(f"User not found: {user_email or user_id}")
    
    # Get credential record
    credential = db.query(Credential).filter(
        Credential.user_db_id == user.id,
        Credential.site == "timecard_portal"
    ).first()
    
    if not credential:
        raise ValueError(f"No credentials found for user: {user.email}")
    
    # Initialize KMS decrypt service
    kms_service = KMSDecryptService()
    
    try:
        # Decrypt the wrapped DEK
        plaintext_dek = kms_service.decrypt_dek(credential.dek_wrapped)
        
        try:
            # Decrypt username and password
            username = kms_service.decrypt_with_dek(
                credential.enc_username,
                credential.nonce_username,
                plaintext_dek
            )
            password = kms_service.decrypt_with_dek(
                credential.enc_password,
                credential.nonce_password,
                plaintext_dek
            )
            
            # Clear plaintext DEK from memory
            plaintext_dek = b'\x00' * len(plaintext_dek)
            del plaintext_dek
            
            logger.info(f"Successfully decrypted credentials for user: {user.email}")
            
            return username, password
        
        finally:
            # Ensure DEK is cleared even if decryption fails
            try:
                plaintext_dek = b'\x00' * len(plaintext_dek)
                del plaintext_dek
            except:
                pass
    
    except Exception as e:
        logger.error(f"Failed to decrypt credentials for user {user.email}: {e}")
        raise


def get_user_credentials_for_signoff(
    db: Session,
    user_email: Optional[str] = None,
    user_id: Optional[int] = None
) -> dict:
    """
    Get decrypted credentials for a user, formatted for use in signoff automation.
    
    Args:
        db: Database session
        user_email: User's email address (optional)
        user_id: User's database ID (optional)
    
    Returns:
        Dictionary with username, password, and domain for signoff
    
    Raises:
        ValueError: If user or credentials not found
        Exception: If decryption fails
    """
    username, password = decrypt_user_credentials(db, user_email=user_email, user_id=user_id)
    
    # Get user for domain if needed
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    elif user_email:
        user = db.query(User).filter(User.email == user_email.lower()).first()
    else:
        user = None
    
    # Default domain (can be customized based on your needs)
    domain = "MC Network"  # Default domain
    
    return {
        "username": username,
        "password": password,
        "domain": domain
    }

