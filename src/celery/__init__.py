"""
Celery worker application initialization.
"""
from celery import Celery
from .config import get_celery_config

# Create Celery app instance
celery_app = Celery('signoff')

# Load configuration
celery_app.conf.update(get_celery_config())

# Export celery_app for use in tasks and other modules
__all__ = ['celery_app']
