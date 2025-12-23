#!/usr/bin/env python3
"""
Test script to verify Celery configuration and credential decryption.
This script can be run directly to test decryption without running the Celery worker.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_decrypt_sync():
    """Test decryption synchronously (without Celery)."""
    from db import SessionLocal
    from kms.credentials import decrypt_user_credentials
    
    email = os.getenv("TEST_EMAIL", "yittymilk@gmail.com")
    
    print(f"Testing credential decryption for: {email}")
    print("=" * 50)
    
    db = SessionLocal()
    try:
        username, password = decrypt_user_credentials(db, user_email=email)
        
        print(f"✓ Success!")
        print(f"  Username: {username}")
        print(f"  Password length: {len(password)}")
        print(f"  Password preview: {password[:1]}***{password[-1:]}")
        print("\n✓ All tests passed! Decryption is working correctly.")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_decrypt_celery():
    """Test decryption via Celery task (requires Celery worker to be running)."""
    from src.celery.celery_test.test_tasks import test_decrypt_credentials
    
    email = os.getenv("TEST_EMAIL", "yittymilk@gmail.com")
    
    print(f"Testing Celery task for: {email}")
    print("=" * 50)
    print("Note: This requires a Celery worker to be running.")
    print("Start worker with: python run_celery.py")
    print()
    
    try:
        # Call the task asynchronously
        result = test_decrypt_credentials.delay(email)
        
        # Wait for result (with timeout)
        print("Waiting for task to complete...")
        task_result = result.get(timeout=30)
        
        print(f"Success: {task_result.get('success')}")
        if task_result.get('success'):
            print(f"Username: {task_result.get('username')}")
            print(f"Password length: {task_result.get('password_length')}")
            print(f"Tests passed: {task_result.get('tests')}")
            print(f"Message: {task_result.get('message')}")
        else:
            print(f"Error: {task_result.get('error')}")
            print(f"Tests: {task_result.get('tests')}")
        
        return task_result.get('success', False)
    except Exception as e:
        print(f"✗ Error calling Celery task: {e}")
        print("\nMake sure:")
        print("  1. Celery worker is running: python run_celery.py")
        print("  2. Redis is running")
        print("  3. Database is accessible")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Celery credential decryption")
    parser.add_argument(
        "--mode",
        choices=["sync", "celery", "both"],
        default="sync",
        help="Test mode: sync (direct), celery (via worker), or both"
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Email address to test (default: yittymilk@gmail.com)"
    )
    
    args = parser.parse_args()
    
    if args.email:
        os.environ["TEST_EMAIL"] = args.email
    
    if args.mode in ["sync", "both"]:
        print("=" * 50)
        print("SYNC MODE: Testing decryption directly (no Celery)")
        print("=" * 50)
        test_decrypt_sync()
        print()
    
    if args.mode in ["celery", "both"]:
        print("=" * 50)
        print("CELERY MODE: Testing decryption via Celery task")
        print("=" * 50)
        test_decrypt_celery()

