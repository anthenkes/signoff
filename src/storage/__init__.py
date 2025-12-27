"""
Storage module for Railway Bucket operations (S3-compatible object storage).
"""
from .bucket_service import BucketService, get_bucket_service

__all__ = [
    "BucketService",
    "get_bucket_service",
]

