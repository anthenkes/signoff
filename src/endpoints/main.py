"""
FastAPI application main file.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPHeader
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from typing import Optional
from contextlib import asynccontextmanager
import os
import logging
import secrets
import traceback
from datetime import datetime, timedelta, timezone

from .config import get_api_config
from db.database import init_db, get_db, Base, get_engine
from db.models import MagicLink, User, Credential
from kms.service import KMSEncryptService
from auth.cookies import (
    create_credentials_cookie, 
    verify_credentials_cookie, 
    COOKIE_NAME,
    COOKIE_EXPIRATION_MINUTES
)
from mail.email_service import EmailService

logger = logging.getLogger(__name__)

# Get API configuration
api_config = get_api_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    try:
        init_db()
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized and tables created")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown (if needed in the future)
    pass


# Create FastAPI app with lifespan
app = FastAPI(
    title=api_config["title"],
    description=api_config["description"],
    version=api_config["version"],
    lifespan=lifespan,
)

# CORS middleware - allow frontend origins
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [
    frontend_url,
    "http://localhost:3000",  # Default Next.js dev server
    "http://127.0.0.1:3000",
]

# Allow all origins in development if FRONTEND_URL is not set
if os.getenv("ENVIRONMENT", "development") == "development":
    allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal route protection
def get_internal_secret() -> Optional[str]:
    """Get the internal secret from environment variable."""
    return os.getenv("INTERNAL_SECRET", "change-me-in-production")


def get_internal_secret_header(request: Request) -> Optional[str]:
    """Dependency function to get the internal secret header from request."""
    return request.headers.get("X-Internal-Secret")


def verify_internal_access(secret: Optional[str] = Depends(get_internal_secret_header)):
    """Verify that the request has the internal secret header."""
    expected_secret = get_internal_secret()
    if secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is internal only."
        )
    return True


@app.middleware("http")
async def protect_internal_routes(request: Request, call_next):
    """Middleware to protect internal routes."""
    path = request.url.path
    
    # Public routes that don't need protection
    public_routes = [
        "/api/validate-magic-link", 
        "/docs", 
        "/openapi.json", 
        "/redoc"
    ]
    
    # Routes protected by cookie authentication (not public, but don't need internal secret)
    cookie_protected_routes = [
        "/api/credentials",
        "/api/submit-credentials"
    ]
    
    # If it's not a public route or cookie-protected route, check for internal secret
    is_public = any(path.startswith(route) for route in public_routes)
    is_cookie_protected = any(path.startswith(route) for route in cookie_protected_routes)
    
    if not is_public and not is_cookie_protected:
        secret = request.headers.get("X-Internal-Secret")
        expected_secret = get_internal_secret()
        
        if secret != expected_secret:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied. This endpoint is internal only."}
            )
    
    response = await call_next(request)
    return response




# Pydantic models for magic link and credentials
class MagicLinkRequest(BaseModel):
    """Request model for creating a magic link."""
    email: EmailStr = Field(..., description="Email address to send magic link to")


class MagicLinkResponse(BaseModel):
    """Response model for magic link creation."""
    success: bool
    message: str
    token: Optional[str] = None
    link: Optional[str] = None
    expires_at: Optional[datetime] = None


class CredentialsRequest(BaseModel):
    """Request model for credentials submission. Includes user info and credentials."""
    # User information
    user_id: str = Field(..., min_length=1, max_length=255, description="User ID (unique identifier)")
    first_name: Optional[str] = Field(None, max_length=255, description="First name (optional)")
    last_name: Optional[str] = Field(None, max_length=255, description="Last name (optional)")
    
    # Third-party credentials (encrypted)
    username: str = Field(..., min_length=1, max_length=255, description="Timecard username")
    password: str = Field(..., min_length=1, description="Timecard password")


class CredentialsResponse(BaseModel):
    """Response model for credentials submission."""
    success: bool
    message: str


# Internal endpoint to generate magic link
@app.post("/api/magic-link", response_model=MagicLinkResponse)
async def create_magic_link(
    request: MagicLinkRequest,
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to generate a magic link and send email to user.
    Requires internal secret.
    """
    try:
        # Generate a secure token
        token = secrets.token_urlsafe(32)
        
        # Set expiration to 24 hours from now
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Create magic link record
        magic_link = MagicLink(
            token=token,
            email=request.email,
            expires_at=expires_at,
            used=False
        )
        
        db.add(magic_link)
        db.commit()
        db.refresh(magic_link)
        
        # Get base URL from request or environment (frontend URL)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        link = f"{frontend_url}/credentials?token={token}"
        
        logger.info(f"Magic link created: email={request.email}, expires_at={expires_at}")
        
        # Send email with magic link
        email_sent = False
        email_service = None
        try:
            email_service = EmailService()
            email_sent = email_service.send_magic_link(request.email, link)
        except ImportError:
            logger.warning("Resend package not available. Email not sent.")
            # Try to send admin alert
            try:
                if email_service:
                    email_service.send_admin_alert(
                        "Resend Package Not Available",
                        f"Failed to send magic link email to {request.email} because Resend package is not installed.",
                        "ImportError: Resend package not available"
                    )
            except:
                pass
        except Exception as e:
            # Don't fail the request if email fails, just log it
            error_traceback = traceback.format_exc()
            logger.error(f"Failed to send magic link email to {request.email}: {e}", exc_info=True)
            # Send admin alert about email failure
            try:
                if email_service:
                    email_service.send_admin_alert(
                        "Magic Link Email Send Failed",
                        f"Failed to send magic link email to {request.email}. Magic link was created successfully: {link}",
                        error_traceback
                    )
            except Exception as alert_error:
                logger.error(f"Failed to send admin alert: {alert_error}")
        
        message = "Magic link created and email sent successfully" if email_sent else "Magic link created successfully (email sending failed)"
        
        return MagicLinkResponse(
            success=True,
            message=message,
            token=token,
            link=link,
            expires_at=expires_at
        )
    except Exception as e:
        db.rollback()
        error_traceback = traceback.format_exc()
        logger.error(f"Error creating magic link: {e}", exc_info=True)
        
        # Send admin alert about magic link creation failure
        try:
            email_service = EmailService()
            email_service.send_admin_alert(
                "Magic Link Creation Failed",
                f"Failed to create magic link for email: {request.email}",
                error_traceback
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert: {alert_error}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the magic link."
        )


# Public API endpoint to validate magic link and set cookie
@app.get("/api/validate-magic-link")
async def validate_magic_link(
    token: str = Query(..., description="Magic link token"),
    db: Session = Depends(get_db)
):
    """
    Public API endpoint to validate a magic link token.
    Sets a cookie and redirects to credentials form if valid.
    """
    # Validate the magic link
    magic_link = db.query(MagicLink).filter(MagicLink.token == token).first()
    
    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid magic link token."
        )
    
    if magic_link.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This magic link has already been used."
        )
    
    if datetime.now(timezone.utc) > magic_link.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This magic link has expired."
        )
    
    # Create credentials cookie
    cookie_token = create_credentials_cookie(magic_link.email)
    
    # Mark magic link as used
    magic_link.used = True
    magic_link.used_at = datetime.now(timezone.utc)
    db.commit()
    
    # Get frontend URL for redirect
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect_url = f"{frontend_url}/credentials"
    
    # Create redirect response with cookie
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    
    # Set cookie with 30 minute expiration
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie_token,
        max_age=COOKIE_EXPIRATION_MINUTES * 60,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        path="/"
    )
    
    logger.info(f"Magic link validated and cookie set for email: {magic_link.email}")
    
    return response


# Internal routes (protected by middleware)
@app.get("/")
async def root():
    """Root endpoint - internal only."""
    return {"message": "Time Card Sign-Off API", "version": api_config["version"]}


@app.get("/health")
async def health():
    """Health check endpoint - internal only."""
    return {"status": "healthy"}


def verify_credentials_cookie_dependency(request: Request) -> str:
    """
    Dependency function to verify credentials cookie and return email.
    
    Raises:
        HTTPException: If cookie is missing, invalid, or expired
    """
    cookie_value = request.cookies.get(COOKIE_NAME)
    
    if not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please verify your magic link."
        )
    
    try:
        email = verify_credentials_cookie(cookie_value)
        return email
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# Public endpoint to get credentials form (protected by cookie)
@app.get("/api/credentials")
async def get_credentials_form(
    email: str = Depends(verify_credentials_cookie_dependency)
):
    """
    Get credentials form page. Protected by cookie authentication.
    User must have validated magic link to access this endpoint.
    """
    return {
        "authenticated": True,
        "email": email,
        "message": "You can now submit your credentials"
    }


# Public endpoint to submit credentials (protected by cookie)
@app.post("/api/submit-credentials", response_model=CredentialsResponse)
async def submit_credentials(
    credentials: CredentialsRequest,
    email: str = Depends(verify_credentials_cookie_dependency),
    db: Session = Depends(get_db)
):
    """
    Submit user information and encrypted credentials. Protected by cookie authentication.
    Creates or updates User record with user info, then encrypts and stores credentials.
    """
    try:
        # Verify email from cookie matches the user being created/updated
        # Get or create user with email from cookie
        user = db.query(User).filter(User.email == email.lower()).first()
        
        if not user:
            # Create new user
            # Check if user_id is already taken
            existing_user_id = db.query(User).filter(User.user_id == credentials.user_id).first()
            if existing_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User ID '{credentials.user_id}' is already taken."
                )
            
            user = User(
                email=email.lower(),
                user_id=credentials.user_id,
                first_name=credentials.first_name,
                last_name=credentials.last_name
            )
            db.add(user)
            db.flush()  # Get user.id
            logger.info(f"Created new user: {email} with user_id: {credentials.user_id}")
        else:
            # Update existing user info (but not email or user_id)
            if credentials.user_id != user.user_id:
                # Check if new user_id is available
                existing_user_id = db.query(User).filter(User.user_id == credentials.user_id).first()
                if existing_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"User ID '{credentials.user_id}' is already taken."
                    )
                user.user_id = credentials.user_id
            
            user.first_name = credentials.first_name
            user.last_name = credentials.last_name
            user.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated user info: {email}")
        
        # Initialize KMS encrypt service
        kms_service = KMSEncryptService()
        
        # Generate data encryption key
        plaintext_dek, wrapped_dek = kms_service.generate_data_key()
        
        try:
            # Encrypt username and password
            enc_username, nonce_username = kms_service.encrypt_with_dek(
                credentials.username, 
                plaintext_dek
            )
            enc_password, nonce_password = kms_service.encrypt_with_dek(
                credentials.password, 
                plaintext_dek
            )
            
            # Get KMS key ID
            kms_key_id = kms_service.kms_key_id
            
            # Clear plaintext DEK from memory
            plaintext_dek = b'\x00' * len(plaintext_dek)
            del plaintext_dek
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Error encrypting credentials: {e}", exc_info=True)
            db.rollback()
            
            # Send admin alert about encryption failure
            try:
                email_service = EmailService()
                email_service.send_admin_alert(
                    "Credential Encryption Failed",
                    f"Failed to encrypt credentials for user: {email}",
                    error_traceback
                )
            except Exception as alert_error:
                logger.error(f"Failed to send admin alert: {alert_error}")
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encrypt credentials. Please try again."
            )
        
        # Check if credential already exists for this user
        existing_credential = db.query(Credential).filter(
            Credential.user_db_id == user.id,
            Credential.site == "timecard_portal"
        ).first()
        
        if existing_credential:
            # Update existing credential
            existing_credential.enc_username = enc_username
            existing_credential.nonce_username = nonce_username
            existing_credential.enc_password = enc_password
            existing_credential.nonce_password = nonce_password
            existing_credential.dek_wrapped = wrapped_dek
            existing_credential.kms_key_id = kms_key_id
            existing_credential.dek_version = existing_credential.dek_version + 1
            existing_credential.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Updated credentials for user: {email}")
        else:
            # Create new credential record
            credential = Credential(
                user_db_id=user.id,
                user_id=user.user_id,
                site="timecard_portal",
                enc_username=enc_username,
                nonce_username=nonce_username,
                enc_password=enc_password,
                nonce_password=nonce_password,
                dek_wrapped=wrapped_dek,
                kms_key_id=kms_key_id,
                dek_version=1
            )
            db.add(credential)
            logger.info(f"Created new credentials for user: {email}")
        
        # Update user's needs_password flag
        user.needs_password = False
        
        db.commit()
        
        return CredentialsResponse(
            success=True,
            message="Your credentials have been securely stored."
        )
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        error_traceback = traceback.format_exc()
        db.rollback()
        logger.error(f"Error submitting credentials: {e}", exc_info=True)
        
        # Send admin alert about credential submission failure
        try:
            email_service = EmailService()
            email_service.send_admin_alert(
                "Credential Submission Failed",
                f"Failed to submit credentials for user: {email}",
                error_traceback
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert: {alert_error}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while storing your credentials. Please try again later."
        )

