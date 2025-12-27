"""
Utility functions for time card sign-off automation.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING, Union
from functools import wraps
import time

if TYPE_CHECKING:
    from signoff_models import SignoffResult, SignoffUser
    from db.models import User as DBUser


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""
    COLORS = {
        "DEBUG": "\033[94m",      # Blue
        "INFO": "\033[92m",       # Green
        "WARNING": "\033[93m",    # Yellow
        "ERROR": "\033[91m",      # Red
        "CRITICAL": "\033[91m",   # Red
        "RESET": "\033[0m",       # Reset to default color
    }

    def format(self, record):
        log_message = super().format(record)
        # Only add colors to console output, not file output
        if hasattr(record, 'no_color') and record.no_color:
            return log_message
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        return f"{color}{log_message}{self.COLORS['RESET']}"


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Set up logging configuration with colored output.
    
    Args:
        verbose: If True, set log level to DEBUG
        log_file: Optional path to log file
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory if logging to file
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        stream_handler = logging.StreamHandler(sys.stdout)
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        stream_handler.setFormatter(colored_formatter)
        
        handlers = [file_handler, stream_handler]
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        stream_handler.setFormatter(colored_formatter)
        handlers = [stream_handler]
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def is_bi_weekly_sunday() -> bool:
    """
    Check if today is a bi-weekly Sunday (every 2 weeks from anchor date).
    
    Uses December 21, 2025 as the anchor date. This function returns True
    if today is a Sunday and falls exactly on a 2-week interval from that
    anchor date (i.e., 0, 2, 4, 6... weeks from anchor).
    
    Examples:
        - December 21, 2025 (anchor): True
        - January 4, 2026 (2 weeks later): True
        - January 18, 2026 (4 weeks later): True
        - January 11, 2026 (3 weeks later): False
    
    Returns:
        True if today is a bi-weekly Sunday, False otherwise
    """
    # Anchor date: December 21, 2025 (a Sunday)
    anchor_date = datetime(2025, 12, 21).date()
    
    today = datetime.now().date()
    
    # Check if today is Sunday (0 = Monday, 6 = Sunday)
    if today.weekday() != 6:  # Not Sunday
        return False
    
    # Calculate days since anchor date
    days_since_anchor = (today - anchor_date).days
    
    # If the date is before the anchor, return False
    if days_since_anchor < 0:
        return False
    
    # Return True if it's exactly a multiple of 14 days (2 weeks) from anchor
    # This means: anchor (0 days), +2 weeks (14 days), +4 weeks (28 days), etc.
    return days_since_anchor % 14 == 0


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying a function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    
    Example:
        @retry(max_attempts=3, delay=1.0)
        def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger = logging.getLogger(__name__)
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            raise last_exception
        return wrapper
    return decorator


def format_result_message(result: "SignoffResult") -> str:
    """
    Format a sign-off result into a readable message.
    
    Args:
        result: The SignoffResult object
    
    Returns:
        Formatted message string
    """
    status = "SUCCESS" if result.success else "FAILED"
    user_name = result.user.name or result.user.username
    timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"[{status}] {user_name} - {timestamp}"
    
    if result.message:
        message += f": {result.message}"
    
    if result.error:
        message += f" (Error: {result.error})"
    
    return message


def ensure_directory(path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory
    
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_screenshot_path(user: Union["SignoffUser", "DBUser"], suffix: str = "") -> str:
    """
    Generate a screenshot path for a user.
    
    Args:
        user: The User object
        suffix: Optional suffix for the filename
    
    Returns:
        Path string for the screenshot
    """
    screenshots_dir = ensure_directory("screenshots")
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Use full name if available, otherwise fall back to username
    if hasattr(user, 'name') and user.name:
        name_safe = user.name.replace(" ", "_").replace("/", "_")
    elif hasattr(user, 'first_name') and hasattr(user, 'last_name'):
        # Handle database User model with first_name and last_name
        first = user.first_name or ""
        last = user.last_name or ""
        name_safe = f"{first}_{last}".strip("_").replace(" ", "_").replace("/", "_")
        if not name_safe:
            name_safe = getattr(user, 'username', getattr(user, 'email', 'unknown')).replace(" ", "_").replace("/", "_")
    else:
        name_safe = getattr(user, 'username', getattr(user, 'email', 'unknown')).replace(" ", "_").replace("/", "_")
    
    suffix_str = f"_{suffix}" if suffix else ""
    filename = f"{name_safe}{suffix_str}_{date_str}.png"
    return str(screenshots_dir / filename)


def get_screenshot_identifier(user: Union["SignoffUser", "DBUser"]) -> str:
    """
    Generate a sanitized identifier for a user's screenshot filename/key.
    Used for both local file paths and S3 bucket keys to ensure consistency.
    
    Args:
        user: The User object
    
    Returns:
        Sanitized identifier string (e.g., "user_at_example_com")
    """
    # Use email as the identifier for consistency (email is unique and stable)
    # Fall back to username or name if email not available
    if hasattr(user, 'email') and user.email:
        identifier = user.email.replace("@", "_at_").replace(".", "_")
    elif hasattr(user, 'name') and user.name:
        identifier = user.name.replace(" ", "_").replace("/", "_").replace("@", "_at_").replace(".", "_")
    elif hasattr(user, 'first_name') and hasattr(user, 'last_name'):
        first = user.first_name or ""
        last = user.last_name or ""
        identifier = f"{first}_{last}".strip("_").replace(" ", "_").replace("/", "_")
        if not identifier:
            identifier = "unknown"
    else:
        identifier = "unknown"
    
    return identifier


def get_persistent_screenshot_path(user: Union["SignoffUser", "DBUser"]) -> str:
    """
    Generate a persistent screenshot path for a user that gets replaced each run.
    Used for storing the confirmed signoff screenshot (one per user, replaced bi-weekly).
    
    Args:
        user: The User object
    
    Returns:
        Path string for the screenshot (same filename each time, so it replaces)
    """
    screenshots_dir = ensure_directory("screenshots")
    identifier = get_screenshot_identifier(user)
    
    # Use a fixed filename without date - this will replace the previous screenshot
    filename = f"{identifier}_signoff_confirmed.png"
    return str(screenshots_dir / filename)


def get_screenshot_s3_key(user: Union["SignoffUser", "DBUser"]) -> str:
    """
    Generate an S3 key for a user's screenshot in the bucket.
    Uses the same naming convention as local persistent screenshots for consistency.
    
    Args:
        user: The User object
    
    Returns:
        S3 key string (e.g., "screenshots/user_at_example_com_signoff_confirmed.png")
    """
    identifier = get_screenshot_identifier(user)
    return f"screenshots/{identifier}_signoff_confirmed.png"

