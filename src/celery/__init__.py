"""
Celery worker application initialization.
"""
from celery import Celery
from .config import get_celery_config

# Create Celery app instance
celery_app = Celery('signoff')

# Load configuration
celery_app.config_from_object(get_celery_config())

# Auto-discover tasks from this package
celery_app.autodiscover_tasks(['src.celery'])
