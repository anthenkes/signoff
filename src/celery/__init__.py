"""
Celery worker application initialization.
"""
import sys

# Temporarily remove src from path to ensure we import the installed celery package
# not the local src/celery directory
_src_path = None
_src_path_index = None
for i, path in enumerate(sys.path):
    if path.endswith('src') or path.endswith('src/'):
        _src_path = path
        _src_path_index = i
        break

if _src_path_index is not None:
    sys.path.pop(_src_path_index)

try:
    from celery import Celery
finally:
    # Restore src to path after importing celery
    if _src_path is not None and _src_path_index is not None:
        sys.path.insert(_src_path_index, _src_path)

from .config import get_celery_config

# Create Celery app instance
celery_app = Celery('signoff')

# Load configuration
celery_app.config_from_object(get_celery_config())

# Auto-discover tasks from this package
celery_app.autodiscover_tasks(['src.celery'])

# Export celery_app for use in tasks and other modules
__all__ = ['celery_app']
