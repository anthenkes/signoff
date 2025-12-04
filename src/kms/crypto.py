"""
AES-GCM encryption and decryption utilities.
"""
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import secrets
import logging

logger = logging.getLogger(__name__)

# Standard nonce size for GCM is 12 bytes (96 bits)
NONCE_SIZE = 12
# AES-256 requires 32-byte keys
KEY_SIZE = 32


def encrypt_aes_gcm(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-GCM.
    
    Args:
        plaintext: The plaintext string to encrypt
        key: The encryption key (must be 32 bytes for AES-256)
    
    Returns:
        Tuple of (ciphertext, nonce)
    
    Raises:
        ValueError: If key size is incorrect
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes for AES-256, got {len(key)} bytes")
    
    # Generate a random nonce
    nonce = secrets.token_bytes(NONCE_SIZE)
    
    # Create AES-GCM cipher
    aesgcm = AESGCM(key)
    
    # Encrypt the plaintext
    # AESGCM.encrypt expects bytes, and returns ciphertext
    plaintext_bytes = plaintext.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    
    return ciphertext, nonce


def decrypt_aes_gcm(ciphertext: bytes, nonce: bytes, key: bytes) -> str:
    """
    Decrypt ciphertext using AES-GCM.
    
    Args:
        ciphertext: The encrypted data
        nonce: The nonce used during encryption
        key: The decryption key (must be 32 bytes for AES-256)
    
    Returns:
        The decrypted plaintext string
    
    Raises:
        ValueError: If key size is incorrect
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key, corrupted data, etc.)
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"Key must be {KEY_SIZE} bytes for AES-256, got {len(key)} bytes")
    
    if len(nonce) != NONCE_SIZE:
        raise ValueError(f"Nonce must be {NONCE_SIZE} bytes, got {len(nonce)} bytes")
    
    # Create AES-GCM cipher
    aesgcm = AESGCM(key)
    
    # Decrypt the ciphertext
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    
    # Convert back to string
    return plaintext_bytes.decode('utf-8')

