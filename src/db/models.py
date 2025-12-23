"""
SQLAlchemy database models.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Integer, 
    String, 
    DateTime, 
    func,
    ForeignKey,
    LargeBinary,
    Text,
    Enum,
    Boolean,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column, 
    relationship,
)

class Base(DeclarativeBase):
    """Base class for all models."""

    """ 
    Can put things like:
    - Audit fields (created_at, updated_at)
    - Common Declaravtive Methods (as_dict, from_dict, to_dict)
    - MetaData for naming conventions for alembic migrations
    - Generic fields (id, created_at, updated_at)
    - Relationships (back_populates, foreign_keys, etc.)
    """
    pass

class TimecardRunStatus(str, enum.Enum):
    LOGIN_SUCCESS_SIGNED_OFF = "login_success_signed_off"
    LOGIN_SUCCESS_ALREADY_SIGNED = "login_success_already_signed"
    LOGIN_FAILED_BAD_CREDENTIALS = "login_failed_bad_credentials"
    LOGIN_FAILED_SITE_ERROR = "login_failed_site_error"
    LOGIN_FAILED_UNKNOWN_ERROR = "login_failed_unknown_error"


class MagicLink(Base):
    """Magic link for email-based authentication."""
    __tablename__ = "magic_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    """App user (your own auth / profile). No external credential stuff here."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        # Public stable identifier (not the DB PK). Generated server-side.
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
    )

    # Profile Information
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Bookkeeping
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Timecard Automation Summary Fields

    last_timecard_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    ) # Last time system 'tried' to log in

    last_timecard_signoff_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    ) # Last time system actually signed off

    last_timecard_check_status: Mapped[TimecardRunStatus | None] = mapped_column(
        Enum(TimecardRunStatus), nullable=True
    ) # Last timecard check status

    # If true -> send user email w/ magic link to update stored credentials
    needs_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Counters
    auto_signed_off_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    already_signed_off_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationship to encrypted timecard credentials
    credentials: Mapped[list["Credential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )



class Credential(Base):
    """Encrypted external login (timecard credentials) for a user."""
    __tablename__ = "credentials"

    # Credential record id
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Link back to User.id
    user_db_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    # Optional: also store the public user_id string for easier AAD/debug
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Only one site for now; still nice to have for future flexibility
    site: Mapped[str] = mapped_column(
        String(255), nullable=False, default="timecard_portal"
    )

    # Encrypted fields (AES-GCM ciphertext + nonce)
    enc_username: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce_username: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    enc_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Per-record DEK
    dek_wrapped: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kms_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dek_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Bookkeeping
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship back to User
    user: Mapped[User] = relationship(back_populates="credentials")




class TimecardRun(Base):
    """Record of a timecard run (login attempt + signoff attempt)."""
    __tablename__ = "timecard_runs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    user_db_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("credentials.id"), nullable=False, index=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[TimecardRunStatus] = mapped_column(
        Enum(TimecardRunStatus), nullable=False
    )

    # Optional: store a short machine-parsable error code / message
    error_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Optional: exactly what the run did
    login_success: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    signed_off_performed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    already_signed_off_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    
    # Track which version of credentials was used (for race condition detection; very unlikely with current password update flow)
    credential_dek_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship()
    credential: Mapped["Credential"] = relationship()
