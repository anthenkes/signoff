"""
Data models for the time card sign-off automation.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Represents a user with their credentials and email."""
    username: str
    password: str
    email: str
    domain: str = "System Authentication"
    name: Optional[str] = None
    employee_id: Optional[str] = None


@dataclass
class SignOffResult:
    """Represents the result of a sign-off operation."""
    user: User
    success: bool
    message: str
    timestamp: datetime
    screenshot_path: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set if not provided."""
        if not isinstance(self.timestamp, datetime):
            self.timestamp = datetime.now()

