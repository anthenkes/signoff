"""
Data models for the time card sign-off automation workflow.

These are dataclass models used during the Playwright automation process.
They contain plaintext credentials temporarily during the signoff process.

For database models (SQLAlchemy), see db.models.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SignoffUser:
    """
    User model for signoff automation workflow.
    
    Contains plaintext credentials temporarily during the automation process.
    This is separate from db.models.User which stores encrypted credentials.
    """
    username: str
    password: str
    email: str
    domain: str = "MC Network"
    name: Optional[str] = None
    employee_id: Optional[str] = None


@dataclass
class SignoffResult:
    """
    Result of a sign-off automation operation.
    
    Contains the outcome of the Playwright automation workflow.
    """
    user: SignoffUser
    success: bool
    message: str
    timestamp: datetime
    screenshot_path: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set if not provided."""
        if not isinstance(self.timestamp, datetime):
            self.timestamp = datetime.now()
