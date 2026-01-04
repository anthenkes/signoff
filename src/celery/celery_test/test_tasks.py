"""
Test tasks for verifying Celery configuration and credential decryption.
These tasks do NOT run signoff automation - only test infrastructure.
"""
import logging
from .. import celery_app
from src.db import SessionLocal
from src.db.models import User
from src.kms.credentials import decrypt_user_credentials

logger = logging.getLogger(__name__)


@celery_app.task
def test_decrypt_credentials(user_email: str):
    """
    Test task to verify Celery configuration and credential decryption.
    Does NOT run signoff automation - only tests decryption.
    
    Args:
        user_email: Email address of the user to test
    
    Returns:
        Dictionary with test results and masked credentials
    """
    db = SessionLocal()
    try:
        logger.info(f"Testing credential decryption for: {user_email}")
        
        # Test database connection
        user = db.query(User).filter(User.email == user_email.lower()).first()
        if not user:
            return {
                "success": False,
                "error": f"User not found: {user_email}",
                "tests": {
                    "database_connection": True,
                    "user_lookup": False,
                    "credential_decryption": False
                }
            }
        
        # Test credential decryption
        try:
            username, password = decrypt_user_credentials(db, user_email=user_email)
            
            # Return masked results
            return {
                "success": True,
                "email": user_email,
                "user_id": user.id,
                "username": username,  # Show full username for testing
                "masked_username": f"{username[:2]}***{username[-2:]}" if len(username) > 4 else "***",
                "password_length": len(password),
                "password_preview": f"{password[:1]}***{password[-1:]}" if len(password) > 2 else "***",
                "tests": {
                    "database_connection": True,
                    "user_lookup": True,
                    "credential_decryption": True,
                    "kms_decryption": True
                },
                "message": "All tests passed! Celery configuration is correct."
            }
        
        except Exception as decrypt_error:
            logger.error(f"Decryption test failed for {user_email}: {decrypt_error}", exc_info=True)
            return {
                "success": False,
                "error": f"Decryption failed: {str(decrypt_error)}",
                "email": user_email,
                "user_id": user.id,
                "tests": {
                    "database_connection": True,
                    "user_lookup": True,
                    "credential_decryption": False,
                    "kms_decryption": False
                }
            }
    
    except Exception as e:
        logger.error(f"Test task failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "tests": {
                "database_connection": False,
                "user_lookup": False,
                "credential_decryption": False
            }
        }
    finally:
        db.close()

