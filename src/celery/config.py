"""
Celery configuration for background task processing.
"""
import os
import logging
from typing import Dict, Any
from celery.schedules import crontab
from datetime import timedelta

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def get_celery_config() -> Dict[str, Any]:
    """
    Get Celery configuration from environment variables.
    
    Returns:
        Dictionary with Celery configuration settings
    """
    # Redis broker URL (Railway Redis addon)
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError(
            "REDIS_URL environment variable is required for Celery broker"
        )
    
    # Get worker concurrency (defaults to 1 for safe operation)
    worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", "1"))
    
    config = {
        # Broker settings
        'broker_url': redis_url,
        'broker_connection_retry_on_startup': True,
        'broker_transport_options': {
            'visibility_timeout': 900, # 15 mintes for task to be visible to worker
        },
        
        # Result backend settings (disabled - we don't need return values)
        'task_ignore_result': True,
        'result_backend': None,
        
        # Serialization
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        
        # Timezone - use America/Los_Angeles for scheduled tasks
        'timezone': 'America/Los_Angeles',
        'enable_utc': False,  # Use local timezone, not UTC
        
        # Task acknowledgment
        'task_acks_late': True,  # Acknowledge tasks after execution
        'task_reject_on_worker_lost': True,  # Reject tasks if worker dies
        
        # Worker settings
        'worker_prefetch_multiplier': 1,  # Only prefetch one task at a time
        'worker_max_tasks_per_child': 10,  # Restart worker after 10 tasks (memory management)
        'worker_concurrency': worker_concurrency,
        
        # TODO: IS Task execution settings long enough?
        'task_time_limit': 300,  # Hard time limit: 5 minutes
        'task_soft_time_limit': 240,  # Soft time limit: 4 minutes (raises SoftTimeLimitExceeded)
        'task_track_started': True,  # Track when tasks start (for timing)
        
        # Retry settings
        'task_autoretry_for': (
            ConnectionError,
            TimeoutError,
            OSError,
            IOError,
        ),
        'task_retry_backoff': True,  # Use exponential backoff
        'task_retry_backoff_max': 600,  # Max backoff: 10 minutes
        'task_retry_jitter': True,  # Add jitter to retry delays (randomized delay between retries so not all retries happen at the same time)
        'task_max_retries': 3,  # Maximum 3 retries
        
        # Queue settings
        'task_default_queue': 'default',
        'task_default_exchange': 'default',
        'task_default_exchange_type': 'direct',
        'task_default_routing_key': 'default',
        
        # Logging
        'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # Import settings
        'imports': (
            'src.celery.tasks',
        ),
        
        # Beat schedule - periodic tasks
        'beat_schedule': {
            'enqueue-signoffs-weekly-sun-0830': {
                'task': 'src.celery.tasks.enqueue_all_signoffs_if_needed',
                'schedule': crontab(minute=30, hour=8, day_of_week='sun'),
            },
            # TEST TASK: Remove this after verifying beat is working
            'test-beat-working': {
                'task': 'src.celery.tasks.test_beat_working',
                'schedule': timedelta(minutes=5),  # Runs every 5 minutes for testing
            },
        },
    }
    
    logger.info("Celery configuration loaded")
    logger.info(f"Broker: Redis at {redis_url.split('@')[-1] if '@' in redis_url else 'configured'}")
    logger.info(f"Result backend: None (disabled)")
    logger.info(f"Timezone: America/Los_Angeles (enable_utc=False)")
    logger.info(f"Worker concurrency: {worker_concurrency}")
    logger.info(f"Beat schedule: enqueue-signoffs-weekly-sun-0830 (Sunday 8:30am LA time)")
    
    return config