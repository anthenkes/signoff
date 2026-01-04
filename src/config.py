"""
Base/shared configuration management for time card sign-off automation.
"""
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.signoff_models import SignoffUser
import logging

# Try to load python-dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv is optional

logger = logging.getLogger(__name__)


def load_users(config_path: Optional[str] = None) -> List[SignoffUser]:
    """
    Load users from JSON configuration file or environment variables.
    
    Args:
        config_path: Path to users.json file. If None, looks for users.json in src directory.
    
    Returns:
        List of SignoffUser objects
    """
    users = []
    
    # Try to load from config file first
    if config_path is None:
        config_path = Path(__file__).parent / "users.json"
    
    config_file = Path(config_path)
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                
            if isinstance(data, list):
                for user_data in data:
                    users.append(SignoffUser(
                        username=user_data.get('username', ''),
                        password=user_data.get('password', ''),
                        email=user_data.get('email', ''),
                        domain=user_data.get('domain', 'MC Network'),
                        name=user_data.get('name'),
                        employee_id=user_data.get('employee_id')
                    ))
            elif isinstance(data, dict) and 'users' in data:
                for user_data in data['users']:
                    users.append(SignoffUser(
                        username=user_data.get('username', ''),
                        password=user_data.get('password', ''),
                        email=user_data.get('email', ''),
                        domain=user_data.get('domain', 'MC Network'),
                        name=user_data.get('name'),
                        employee_id=user_data.get('employee_id')
                    ))
            
            logger.info(f"Loaded {len(users)} users from {config_file}")
        except Exception as e:
            logger.error(f"Error loading users from {config_file}: {e}")
            raise
    else:
        logger.warning(f"Config file not found: {config_file}. Trying environment variables.")
        
        # Fallback to environment variables (single user)
        username = os.getenv("APIHC_USERNAME")
        password = os.getenv("APIHC_PASSWORD")
        email = os.getenv("APIHC_EMAIL")
        domain = os.getenv("APIHC_DOMAIN", "MC Network")
        
        if username and password and email:
            users.append(SignoffUser(
                username=username,
                password=password,
                email=email,
                domain=domain
            ))
            logger.info("Loaded user from environment variables")
        else:
            raise ValueError(
                "No users configuration found. Either create users.json or set "
                "APIHC_USERNAME, APIHC_PASSWORD, and APIHC_EMAIL environment variables."
            )
    
    if not users:
        raise ValueError("No users found in configuration")
    
    return users


def get_app_config() -> Dict[str, Any]:
    """
    Get application configuration settings.
    
    Returns:
        Dictionary with application configuration
    """
    return {
        "base_url": os.getenv("APIHC_BASE_URL", "https://llca419.apihealthcare.com"),
        "default_domain": os.getenv("APIHC_DOMAIN", "MC Network"),
        "default_timeout": int(os.getenv("APIHC_TIMEOUT", "30000")),
        "headless": os.getenv("APIHC_HEADLESS", "false").lower() == "true",
        "slow_mo": int(os.getenv("APIHC_SLOW_MO", "0")),
    }


def validate_config() -> bool:
    """
    Validate that required configuration exists.
    
    Returns:
        True if configuration is valid
    
    Raises:
        ValueError: If configuration is invalid
    """
    try:
        # Try to load users (will raise if invalid)
        users = load_users()
        if not users:
            raise ValueError("No users configured")
        
        # Try to get email config (will raise if invalid)
        from src.mail.config import get_email_config
        email_config = get_email_config()
        
        # Get app config (has defaults, should always work)
        app_config = get_app_config()
        
        logger.info("Configuration validated successfully")
        logger.info(f"Base URL: {app_config['base_url']}")
        logger.info(f"Email from: {email_config['from_email']}")
        logger.info(f"Number of users: {len(users)}")
        
        return True
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise

