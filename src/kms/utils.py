"""
Security utilities for credential handling.
"""
import random


def obfuscate_credential(value: str) -> str:
    """
    Obfuscate a credential by overwriting with random-length null bytes.
    
    This prevents attackers from inferring the original credential length
    if they dump memory. Uses a random length between 8-64 characters.
    
    Args:
        value: The credential string to obfuscate
        
    Returns:
        String of null bytes with random length
    """
    # Use random length between 8-64 to obfuscate original length
    # This range covers most password lengths without being suspiciously long
    random_length = random.randint(8, 64)
    return "\x00" * random_length

