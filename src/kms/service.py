"""
AWS KMS service for encryption and decryption operations.
"""
import boto3
from botocore.exceptions import ClientError
from typing import Tuple
import logging

from .config import get_kms_config
from .crypto import encrypt_aes_gcm, decrypt_aes_gcm

logger = logging.getLogger(__name__)


class KMSEncryptService:
    """
    Service for web server - can generate data keys and encrypt data.
    Cannot decrypt.
    """
    
    def __init__(self):
        """Initialize the KMS encrypt service with AWS credentials."""
        config = get_kms_config(mode="encrypt")
        self.kms_client = boto3.client(
            'kms',
            aws_access_key_id=config["access_key_id"],
            aws_secret_access_key=config["secret_access_key"],
            region_name=config["region"]
        )
        self.kms_key_id = config["kms_key_id"]
    
    def generate_data_key(self) -> Tuple[bytes, bytes]:
        """
        Generate a data encryption key (DEK) using AWS KMS.
        
        Returns:
            Tuple of (plaintext_dek, wrapped_dek)
            - plaintext_dek: The DEK in plaintext (32 bytes for AES-256)
            - wrapped_dek: The DEK encrypted by KMS (ciphertext blob)
        
        Raises:
            ClientError: If KMS operation fails
        """
        try:
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'  # Generate a 256-bit key
            )
            
            plaintext_dek = response['Plaintext']
            wrapped_dek = response['CiphertextBlob']
            
            logger.info(f"Generated data key using KMS key: {self.kms_key_id}")
            
            return plaintext_dek, wrapped_dek
        
        except ClientError as e:
            logger.error(f"Failed to generate data key: {e}")
            raise
    
    def encrypt_with_dek(self, plaintext: str, dek: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt data using AES-GCM with a plaintext DEK.
        
        Args:
            plaintext: The data to encrypt
            dek: The plaintext data encryption key
        
        Returns:
            Tuple of (ciphertext, nonce)
        """
        return encrypt_aes_gcm(plaintext, dek)


class KMSDecryptService:
    """
    Service for celery worker - can decrypt data keys and decrypt data.
    Cannot generate new keys.
    """
    
    def __init__(self):
        """Initialize the KMS decrypt service with AWS credentials."""
        config = get_kms_config(mode="decrypt")
        self.kms_client = boto3.client(
            'kms',
            aws_access_key_id=config["access_key_id"],
            aws_secret_access_key=config["secret_access_key"],
            region_name=config["region"]
        )
        self.kms_key_id = config["kms_key_id"]
    
    def decrypt_dek(self, wrapped_dek: bytes) -> bytes:
        """
        Decrypt a wrapped data encryption key using AWS KMS.
        
        Args:
            wrapped_dek: The encrypted DEK (ciphertext blob from KMS)
        
        Returns:
            The plaintext DEK (32 bytes for AES-256)
        
        Raises:
            ClientError: If KMS operation fails
        """
        try:
            response = self.kms_client.decrypt(
                CiphertextBlob=wrapped_dek
            )
            
            plaintext_dek = response['Plaintext']
            
            logger.info(f"Decrypted data key using KMS key: {self.kms_key_id}")
            
            return plaintext_dek
        
        except ClientError as e:
            logger.error(f"Failed to decrypt data key: {e}")
            raise
    
    def decrypt_with_dek(self, ciphertext: bytes, nonce: bytes, dek: bytes) -> str:
        """
        Decrypt data using AES-GCM with a plaintext DEK.
        
        Args:
            ciphertext: The encrypted data
            nonce: The nonce used during encryption
            dek: The plaintext data encryption key
        
        Returns:
            The decrypted plaintext string
        """
        return decrypt_aes_gcm(ciphertext, nonce, dek)

