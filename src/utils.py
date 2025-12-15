"""
Utility functions for time card sign-off automation.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from functools import wraps
import time

if TYPE_CHECKING:
    from signoff_models import SignoffResult, SignoffUser


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
    Check if today is a bi-weekly Sunday (every other Sunday).
    
    Uses a simple algorithm: checks if the day of year is divisible by 14
    and the weekday is Sunday (0).
    
    Returns:
        True if today is a bi-weekly Sunday, False otherwise
    """
    today = datetime.now()
    
    # Check if today is Sunday (0 = Monday, 6 = Sunday)
    if today.weekday() != 6:  # Not Sunday
        return False
    
    # Get the first Sunday of the year to establish a baseline
    # Find first Sunday of current year
    jan_1 = datetime(today.year, 1, 1)
    days_until_first_sunday = (6 - jan_1.weekday()) % 7
    first_sunday = jan_1 + timedelta(days=days_until_first_sunday)
    
    # Calculate days since first Sunday
    days_since_first_sunday = (today - first_sunday).days
    
    # Check if it's an even number of weeks (bi-weekly)
    # Every other Sunday means weeks % 2 == 0
    weeks_since_first_sunday = days_since_first_sunday // 7
    
    return weeks_since_first_sunday % 2 == 0


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


def get_screenshot_path(user: "User", suffix: str = "") -> str:
    """
    Generate a screenshot path for a user.
    
    Args:
        user: The User object
        suffix: Optional suffix for the filename
    
    Returns:
        Path string for the screenshot
    """
    screenshots_dir = ensure_directory("screenshots")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    username_safe = user.username.replace(" ", "_").replace("/", "_")
    suffix_str = f"_{suffix}" if suffix else ""
    filename = f"{username_safe}{suffix_str}_{timestamp}.png"
    return str(screenshots_dir / filename)

