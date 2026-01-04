"""
Railway Bucket service for S3-compatible object storage operations.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING
import base64

if TYPE_CHECKING:
    from src.signoff_models import SignoffUser
    from src.db.models import User as DBUser

logger = logging.getLogger(__name__)

# Try to import boto3
try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 package not available. Bucket storage functionality will be disabled.")


class BucketService:
    """Service for interacting with Railway Buckets (S3-compatible storage)."""
    
    def __init__(self):
        """Initialize the bucket service with Railway Bucket credentials."""
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 package is not installed. Install with: pip install boto3")
        
        # Get Railway Bucket credentials from environment variables
        self.bucket_name = os.getenv('BUCKET')
        self.endpoint_url = os.getenv('ENDPOINT')  # https://storage.railway.app
        self.access_key_id = os.getenv('ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('SECRET_ACCESS_KEY')
        self.region = os.getenv('REGION', 'auto')
        
        # Validate required credentials
        if not all([self.bucket_name, self.endpoint_url, self.access_key_id, self.secret_access_key]):
            missing = [k for k, v in {
                'BUCKET': self.bucket_name,
                'ENDPOINT': self.endpoint_url,
                'ACCESS_KEY_ID': self.access_key_id,
                'SECRET_ACCESS_KEY': self.secret_access_key
            }.items() if not v]
            raise ValueError(
                f"Missing required Railway Bucket credentials: {', '.join(missing)}. "
                f"Please configure Variable References from your Railway Bucket service."
            )
        
        # Create S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
            config=Config(signature_version='s3v4')
        )
        
        logger.info(f"Bucket service initialized for bucket: {self.bucket_name}")
    
    def upload_file(self, local_path: str, s3_key: str, content_type: Optional[str] = None) -> bool:
        """
        Upload a file to the Railway Bucket.
        
        Args:
            local_path: Path to local file to upload
            s3_key: S3 key (path) where file will be stored
            content_type: Optional content type (e.g., 'image/png')
        
        Returns:
            True if upload successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args if extra_args else None
            )
            logger.info(f"File uploaded to bucket: {s3_key}")
            return True
        except FileNotFoundError:
            logger.error(f"Local file not found: {local_path}")
            return False
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to upload file to bucket: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return False
    
    def download_file(self, s3_key: str, local_path: Optional[str] = None) -> Optional[bytes]:
        """
        Download a file from the Railway Bucket.
        
        Args:
            s3_key: S3 key (path) of file to download
            local_path: Optional local path to save file. If None, returns bytes.
        
        Returns:
            File content as bytes if local_path is None, None if file not found or error
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            file_content = response['Body'].read()
            
            if local_path:
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(file_content)
                logger.info(f"File downloaded from bucket to: {local_path}")
                return file_content
            else:
                logger.info(f"File downloaded from bucket: {s3_key}")
                return file_content
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"File not found in bucket: {s3_key}")
            return None
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to download file from bucket: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            return None
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in the Railway Bucket.
        
        Args:
            s3_key: S3 key (path) of file to check
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error checking file existence: {e}")
            return False
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from the Railway Bucket.
        
        Args:
            s3_key: S3 key (path) of file to delete
        
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"File deleted from bucket: {s3_key}")
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to delete file from bucket: {e}")
            return False
    
    def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to a file.
        
        Args:
            s3_key: S3 key (path) of file
            expires_in: URL expiration time in seconds (default: 1 hour, max: 90 days)
        
        Returns:
            Presigned URL string, or None if error
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            logger.debug(f"Generated presigned URL for {s3_key} (expires in {expires_in}s)")
            return url
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
    
    def upload_screenshot(self, local_path: str, user: Union["SignoffUser", "DBUser"]) -> Optional[str]:
        """
        Upload a screenshot to the bucket with a standard naming convention.
        Replaces any existing screenshot for the user.
        
        Uses the same naming convention as local persistent screenshots for consistency.
        
        Args:
            local_path: Path to local screenshot file
            user: The User object (SignoffUser or DBUser)
        
        Returns:
            S3 key if successful, None otherwise
        """
        from utils import get_screenshot_s3_key
        
        # Use consistent key - this will replace previous screenshot
        s3_key = get_screenshot_s3_key(user)
        
        if self.upload_file(local_path, s3_key, content_type='image/png'):
            return s3_key
        return None
    
    def get_screenshot(self, user: Union["SignoffUser", "DBUser"]) -> Optional[bytes]:
        """
        Retrieve a screenshot from the bucket.
        
        Args:
            user: The User object (SignoffUser or DBUser)
        
        Returns:
            Screenshot file as bytes, or None if not found
        """
        from utils import get_screenshot_s3_key
        
        s3_key = get_screenshot_s3_key(user)
        return self.download_file(s3_key)
    
    def get_screenshot_base64(self, user: Union["SignoffUser", "DBUser"]) -> Optional[str]:
        """
        Retrieve a screenshot from the bucket as base64-encoded string (for email attachments).
        
        Args:
            user: The User object (SignoffUser or DBUser)
        
        Returns:
            Base64-encoded screenshot string, or None if not found
        """
        screenshot_bytes = self.get_screenshot(user)
        if screenshot_bytes:
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        return None


def get_bucket_service() -> Optional[BucketService]:
    """
    Get a BucketService instance if credentials are available.
    
    Returns:
        BucketService instance if available, None otherwise
    """
    try:
        return BucketService()
    except (ImportError, ValueError) as e:
        logger.debug(f"Bucket service not available: {e}")
        return None

