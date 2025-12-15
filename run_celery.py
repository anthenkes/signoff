#!/usr/bin/env python3
"""
Startup script for running the Celery worker.
This is used for Railway deployment.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path to allow imports like 'from src.celery import ...'
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Add src directory to Python path for backward compatibility with existing imports
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Initialize database before starting Celery
from db import init_db

# Initialize database for failure isolation
# Can rely on lazy loading when tasks access SessionLocal but will fail if unable to connect to database
init_db()

# Import celery_app after path is set up and database is initialized
# This ensures the app is loaded and tasks are registered
# We use the full module path to avoid conflicts with the celery package
from src.celery import celery_app

if __name__ == "__main__":
    # Start Celery worker using the worker_main method
    # This is the programmatic way to start a Celery worker
    # It's equivalent to: celery -A src.celery worker --loglevel=info
    
    # Set up sys.argv for worker_main
    original_argv = sys.argv
    sys.argv = ['celery', 'worker', '--loglevel=info']
    
    try:
        celery_app.worker_main()
    finally:
        sys.argv = original_argv
