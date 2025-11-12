"""
Email module for sending notifications via Resend API.
"""
from .email_service import EmailService
from .config import get_email_config

__all__ = [
    "EmailService",
    "get_email_config",
]

