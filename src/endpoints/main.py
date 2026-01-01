"""
FastAPI application main file.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from typing import Optional
from contextlib import asynccontextmanager
import os
import logging
import secrets
import traceback
from datetime import datetime, timedelta, timezone
import hashlib
from playwright.sync_api import sync_playwright
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .config import get_api_config
from config import get_app_config
from db.database import init_db, get_db, get_engine
from db.models import MagicLink, MagicLinkType, User, Credential, Base
from kms.service import KMSEncryptService
from kms.utils import obfuscate_credential
from play.pages.login_page import LoginPage
from play.pages.dashboard_page import DashboardPage
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

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Initialize rate limiter with separate Redis instance/database (isolated from Celery)
# Use RATE_LIMIT_REDIS_URL if provided, otherwise fall back to in-memory
# This prevents attackers from accessing Celery if they compromise rate limiting Redis
rate_limit_redis_url = os.getenv("RATE_LIMIT_REDIS_URL")
if rate_limit_redis_url:
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=rate_limit_redis_url,
            default_limits=["200/hour", "50/minute"]
        )
        logger.info("Rate limiter initialized with dedicated Redis backend (isolated from Celery)")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis-backed rate limiter: {e}. Using in-memory fallback.")
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["200/hour", "50/minute"]
        )
        logger.warning("WARNING: Using in-memory rate limiting. This will NOT work correctly with multiple web instances!")
else:
    # Fallback to in-memory storage if dedicated Redis not available
    # WARNING: This won't work correctly if Railway scales to multiple web instances
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/hour", "50/minute"]
    )
    logger.warning(
        "Rate limiter initialized with in-memory storage. "
        "This will NOT work correctly with multiple web instances. "
        "Set RATE_LIMIT_REDIS_URL for proper multi-instance support."
    )


async def validate_timecard_login(username: str, password: str) -> tuple[bool, str]:
    """
    Attempt a real login against the timecard portal to validate credentials.
    
    Returns:
        Tuple of (is_valid, error_message). error_message is empty on success.
    """
    app_config = get_app_config()
    base_url = app_config.get("base_url")
    domain = app_config.get("default_domain", "MC Network")
    headless = app_config.get("headless", True)
    slow_mo = app_config.get("slow_mo", 0)
    timeout = app_config.get("default_timeout", 30000)

    def _attempt_login() -> tuple[bool, str]:
        context = None
        browser = None
        # Store credentials in local variables for immediate clearing
        local_username = username
        local_password = password
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(timeout)

                login_page = LoginPage(page)
                login_page.goto(base_url)
                login_page.wait_for_page_load()
                login_page.login(local_username, local_password, domain)

                # Clear credentials immediately after login attempt
                local_username = obfuscate_credential(local_username)
                local_password = obfuscate_credential(local_password)

                dashboard_page = DashboardPage(page)
                dashboard_page.wait_for_dashboard_load()
                return True, ""
        except Exception as e:
            logger.warning(f"Credential validation failed during portal login: {e}")
            # Clear credentials on error as well
            try:
                local_username = obfuscate_credential(local_username)
                local_password = obfuscate_credential(local_password)
            except Exception:
                pass
            return False, "Invalid username or password. Please double-check and try again."
        finally:
            # Final credential clearing (defense in depth)
            try:
                local_username = obfuscate_credential(local_username)
                local_password = obfuscate_credential(local_password)
            except Exception:
                pass
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
            except Exception:
                pass

    try:
        return await run_in_threadpool(_attempt_login)
    except Exception as e:
        logger.error(f"Error validating credentials with timecard portal: {e}", exc_info=True)
        return False, "Unable to validate credentials right now. Please try again."


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
if os.getenv("ENVIRONMENT", "development") == "production":
    app = FastAPI(
        title=api_config["title"],
        description=api_config["description"],
        version=api_config["version"],
        lifespan=lifespan,
        docs_url=None, # Disable docs in production
        redoc_url=None, # Disable redoc in production
        openapi_url=None, # Disable openapi in production
    )
else:
    app = FastAPI(
        title=api_config["title"],
        description=api_config["description"],
        version=api_config["version"],
        lifespan=lifespan,
    )

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        "/api/delete-account",
        "/docs", 
        "/openapi.json", 
        "/redoc"
    ]
    
    # Routes protected by cookie authentication (not public, but don't need internal secret)
    cookie_protected_routes = [
        "/api/credentials",
        "/api/submit-credentials",
        "/api/confirm-delete-account",
        "/form",
        "/delete-account"
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
    first_name: str = Field(..., min_length=1, max_length=255, description="First name")
    last_name: str = Field(..., min_length=1, max_length=255, description="Last name")
    
    # Third-party credentials (encrypted)
    username: str = Field(..., min_length=1, max_length=255, description="Timecard username")
    password: str = Field(..., min_length=1, description="Timecard password")


class CredentialsResponse(BaseModel):
    """Response model for credentials submission."""
    success: bool
    message: str


# Internal endpoint to generate magic link
# TODO: Will make this Railway Console CLI script in the future to create a magic link for a user.
# Also need to make sure that the toke is hashed and not storing the raw token in the db
@app.post("/api/magic-link", response_model=MagicLinkResponse)
@limiter.limit("20/hour")  # Limit magic link creation
async def create_magic_link(
    request: Request,
    magic_link_request: MagicLinkRequest,
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to generate a magic link and send email to user.
    Requires internal secret.
    """
    try:
        # Generate a secure token
        token = secrets.token_urlsafe(32)

        # Hash the token
        hashed_token = hashlib.sha256(token.encode()).hexdigest()

        # Set expiration to 24 hours from now
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Create magic link record
        magic_link = MagicLink(
            token=hashed_token,
            email=magic_link_request.email,
            link_type=MagicLinkType.CREDENTIALS,
            expires_at=expires_at,
            used=False
        )
        
        db.add(magic_link)
        db.commit()
        db.refresh(magic_link)
        
        # Get base URL from environment (backend URL for API endpoint)
        backend_url = os.getenv("BACKEND_URL", os.getenv("API_URL", "http://localhost:8000"))
        link = f"{backend_url}/api/validate-magic-link?token={token}"
        
        logger.info(f"Magic link created: email={magic_link_request.email}, expires_at={expires_at}")
        
        # Send email with magic link
        email_sent = False
        email_service = None
        try:
            email_service = EmailService()
            email_sent = email_service.send_magic_link(magic_link_request.email, link, db)
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
                f"Failed to create magic link for email: {magic_link_request.email}",
                error_traceback
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert: {alert_error}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the magic link."
        )


def generate_deletion_magic_link(email: str, db: Session) -> str:
    """
    Generate or retrieve an existing deletion magic link for a user.
    Reuses existing unused, non-expired links to avoid creating duplicates.
    
    Args:
        email: The user's email address
        db: Database session
    
    Returns:
        The full deletion magic link URL
    """
    email_lower = email.lower()
    now = datetime.now(timezone.utc)
    
    # Check for existing unused, non-expired deletion link
    existing_link = db.query(MagicLink).filter(
        MagicLink.email == email_lower,
        MagicLink.link_type == MagicLinkType.DELETION,
        MagicLink.used == False,
        MagicLink.expires_at > now
    ).first()
    
    if existing_link:
        # Reuse existing link - we need to return the original token
        # But we only have the hash stored, so we need to generate a new one
        # Actually, we can't get the original token back from the hash
        # So we'll create a new one and mark the old one as used, or just create new ones
        # For simplicity, let's just create a new one each time but clean up old unused ones
        logger.info(f"Found existing deletion link for {email}, but cannot retrieve original token. Creating new one.")
        # Mark old one as used to clean up
        existing_link.used = True
        existing_link.used_at = now
        db.commit()
    
    # Generate a secure token
    token = secrets.token_urlsafe(32)
    
    # Hash the token
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    
    # Set expiration to 30 days from now (longer than credentials link since it's permanent)
    expires_at = now + timedelta(days=30)
    
    # Create magic link record for deletion
    magic_link = MagicLink(
        token=hashed_token,
        email=email_lower,
        link_type=MagicLinkType.DELETION,
        expires_at=expires_at,
        used=False
    )
    
    db.add(magic_link)
    db.commit()
    
    # Get base URL from environment
    backend_url = os.getenv("BACKEND_URL", os.getenv("API_URL", "http://localhost:8000"))
    link = f"{backend_url}/api/validate-magic-link?token={token}"
    
    logger.info(f"Deletion magic link created: email={email}, expires_at={expires_at}")
    
    return link


# Public API endpoint to validate magic link and set cookie
@app.get("/api/validate-magic-link")
@limiter.limit("10/hour")  # Limit magic link validation attempts
async def validate_magic_link(
    request: Request,
    token: str = Query(..., description="Magic link token"),
    db: Session = Depends(get_db)
):
    """
    Public API endpoint to validate a magic link token.
    Sets a cookie and redirects to credentials form if valid.
    """
    # Hase incoming token
    hashed_token = hashlib.sha256(token.encode()).hexdigest()

    # Validate the magic link
    magic_link = db.query(MagicLink).filter(MagicLink.token == hashed_token).first()
    
    if not magic_link:
        raise HTTPException(
            status_code=status.HTTP_400_NOT_FOUND,
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
    
    # Redirect based on link type
    if magic_link.link_type == MagicLinkType.DELETION:
        redirect_url = "/delete-account"
    else:
        redirect_url = "/form"
    
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
    
    logger.info(f"Magic link validated and cookie set for email: {magic_link.email}, type: {magic_link.link_type}")
    
    return response


# Cookie-protected endpoint to render deletion confirmation page
@app.get("/delete-account", response_class=HTMLResponse)
@limiter.limit("10/hour")  # Limit deletion page access
async def get_delete_account_page(
    request: Request,
    email: str = Depends(verify_credentials_cookie_dependency)
):
    """
    Render account deletion confirmation page. Protected by cookie authentication.
    User must have validated deletion magic link to access this endpoint.
    """
    return templates.TemplateResponse(
        "delete_account.html",
        {
            "request": request,
            "email": email
        }
    )


# Cookie-protected endpoint to confirm and execute account deletion
@app.post("/api/confirm-delete-account", response_class=HTMLResponse)
@limiter.limit("5/hour")  # Strict limit on deletion confirmations
async def confirm_delete_account(
    request: Request,
    email: str = Depends(verify_credentials_cookie_dependency),
    db: Session = Depends(get_db)
):
    """
    Confirm and execute account deletion. Protected by cookie authentication.
    """
    try:
        # Find the user
        user = db.query(User).filter(User.email == email.lower()).first()
        
        if not user:
            # User doesn't exist, but don't reveal this for security
            logger.warning(f"Deletion attempt for non-existent email: {email}")
            return templates.TemplateResponse(
                "success.html",
                {
                    "request": request,
                    "message": "Account deletion completed. If an account existed, it has been removed."
                }
            )
        
        # Log the deletion attempt
        client_ip = get_remote_address(request)
        user_agent = request.headers.get("user-agent", "Unknown")
        user_id = user.user_id
        
        logger.info(
            f"ACCOUNT_DELETION: email={email}, ip={client_ip}, "
            f"user_agent={user_agent}, user_id={user_id}, "
            f"timestamp={datetime.now(timezone.utc).isoformat()}"
        )
        
        # Delete user (cascade will delete credentials due to relationship)
        # Also need to delete any magic links for this email
        db.query(MagicLink).filter(MagicLink.email == email.lower()).delete()
        
        # Delete user (this will cascade delete credentials)
        db.delete(user)
        db.commit()
        
        logger.info(f"Account deleted successfully: {email}")
        
        # Send admin alert about account deletion
        try:
            email_service = EmailService()
            email_service.send_admin_alert(
                "Account Deletion",
                f"User {email} deleted their account",
                f"Email: {email}\nIP: {client_ip}\nUser Agent: {user_agent}\nTime: {datetime.now(timezone.utc).isoformat()}\nUser ID: {user_id}"
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert for account deletion: {alert_error}")
        
        # Clear the cookie after deletion
        response = templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "message": "Your account and all associated data have been permanently deleted."
            }
        )
        response.delete_cookie(key=COOKIE_NAME, path="/")
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        error_traceback = traceback.format_exc()
        db.rollback()
        logger.error(f"Error deleting account: {e}", exc_info=True)
        
        # Send admin alert about deletion failure
        try:
            email_service = EmailService()
            email_service.send_admin_alert(
                "Account Deletion Failed",
                f"Failed to delete account for email: {email}",
                error_traceback
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert: {alert_error}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting your account. Please contact support."
        )


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
            detail="Authentication required. Please verify."
        )
    
    try:
        email = verify_credentials_cookie(cookie_value)
        return email
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


# Public endpoint to render credentials form (protected by cookie)
@app.get("/form", response_class=HTMLResponse)
@limiter.limit("30/hour")  # Limit form access
async def get_credentials_form(
    request: Request,
    email: str = Depends(verify_credentials_cookie_dependency)
):
    """
    Render credentials form HTML page. Protected by cookie authentication.
    User must have validated magic link to access this endpoint.
    """
    return templates.TemplateResponse("form.html", {"request": request, "email": email})


# Public endpoint to submit credentials (protected by cookie)
@app.post("/api/submit-credentials", response_class=HTMLResponse)
@limiter.limit("5/hour")  # Strict limit on credential submissions
async def submit_credentials(
    request: Request,
    email: str = Depends(verify_credentials_cookie_dependency),
    db: Session = Depends(get_db)
):
    """
    Submit user information and encrypted credentials. Protected by cookie authentication.
    Creates or updates User record with user info, then encrypts and stores credentials.
    Rate limited to 5 submissions per hour per IP address.
    """
    # Audit logging for credential updates
    client_ip = get_remote_address(request)
    user_agent = request.headers.get("user-agent", "Unknown")
    logger.info(
        f"CREDENTIAL_UPDATE_ATTEMPT: email={email}, ip={client_ip}, "
        f"user_agent={user_agent}, timestamp={datetime.now(timezone.utc).isoformat()}"
    )
    # Parse form data
    form_data = await request.form()
    try:
        first_name = (form_data.get("first_name") or "").strip()
        last_name = (form_data.get("last_name") or "").strip()
        if not first_name or not last_name:
            return templates.TemplateResponse(
                "form.html",
                {
                    "request": request,
                    "email": email,
                    "error": "First name and last name are required."
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        credentials = CredentialsRequest(
            first_name=first_name,
            last_name=last_name,
            username=form_data.get("username", ""),
            password=form_data.get("password", "")
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Validation Error",
                "message": str(e),
                "back_link": "/form"
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Validate credentials against the timecard portal before encryption
        login_ok, login_error = await validate_timecard_login(
            credentials.username,
            credentials.password
        )
        if not login_ok:
            logger.info(f"Credential validation failed for email {email}: {login_error}")
            return templates.TemplateResponse(
                "form.html",
                {
                    "request": request,
                    "email": email,
                    "error": login_error
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Verify email from cookie matches the user being created/updated
        # Get or create user with email from cookie
        user = db.query(User).filter(User.email == email.lower()).first()
        
        if not user:
            user = User(
                email=email.lower(),
                first_name=credentials.first_name,
                last_name=credentials.last_name
            )
            db.add(user)
            db.flush()  # Get user.id
            logger.info(f"Created new user: {email} with user_id: {user.user_id}")
        else:
            # Update existing user info (but not email or user_id)
            user.first_name = credentials.first_name
            user.last_name = credentials.last_name
            user.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated user info: {email}")
        
        # Initialize KMS encrypt service
        kms_service = KMSEncryptService()
        
        # Generate data encryption key
        plaintext_dek, wrapped_dek = kms_service.generate_data_key()
        
        try:
            # Encrypt username and password (using original credentials before clearing)
            # Note: credentials are cleared immediately after encryption completes
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
            
            # Clear credentials from memory immediately after encryption
            credentials.username = obfuscate_credential(credentials.username)
            credentials.password = obfuscate_credential(credentials.password)
            
        except Exception as e:
            # Clear credentials on encryption error as well
            try:
                credentials.username = obfuscate_credential(credentials.username)
                credentials.password = obfuscate_credential(credentials.password)
            except Exception:
                pass
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
        
        credential_id = None
        is_new_credential = False
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
            credential_id = existing_credential.id
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
            db.flush()  # Flush to get the credential ID
            credential_id = credential.id
            is_new_credential = True
            logger.info(f"Created new credentials for user: {email}")
        
        # Update user's needs_password flag
        user.needs_password = False
        
        db.commit()
        
        # Audit log successful credential create/update
        action_type = "CREATE" if is_new_credential else "UPDATE"
        logger.info(
            f"CREDENTIAL_{action_type}_SUCCESS: email={email}, ip={client_ip}, "
            f"user_id={user.user_id}, credential_id={credential_id}, "
            f"timestamp={datetime.now(timezone.utc).isoformat()}"
        )
        
        # Send admin alert about credential create/update
        try:
            email_service = EmailService()
            action_text = "created" if is_new_credential else "updated"
            email_service.send_admin_alert(
                f"Credential {action_text.title()}",
                f"User {email} {action_text} their credentials",
                f"Action: {action_text.upper()}\nEmail: {email}\nIP: {client_ip}\nUser Agent: {user_agent}\nTime: {datetime.now(timezone.utc).isoformat()}\nUser ID: {user.user_id}\nCredential ID: {credential_id}"
            )
        except Exception as alert_error:
            logger.error(f"Failed to send admin alert for credential {action_text}: {alert_error}")
        
        # Send confirmation email to user with deletion link
        try:
            email_service = EmailService()
            email_sent = email_service.send_credentials_confirmation(
                email=email,
                first_name=user.first_name,
                db_session=db
            )
            if email_sent:
                logger.info(f"Credentials confirmation email sent to {email}")
            else:
                logger.warning(f"Failed to send credentials confirmation email to {email}")
        except Exception as email_error:
            logger.error(f"Error sending credentials confirmation email to {email}: {email_error}")
            # Don't fail the request if email fails
        
        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "message": "Your credentials have been securely stored."
            }
        )
    
    except HTTPException as e:
        db.rollback()
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Error",
                "message": e.detail,
                "back_link": "/form"
            },
            status_code=e.status_code
        )
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
        
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Error",
                "message": "An error occurred while storing your credentials. Please try again later.",
                "back_link": "/form"
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        # Safety: Ensure credentials are obfuscated even if any exception occurs
        # This is defense in depth - credentials may already be obfuscated if encryption succeeded
        try:
            # Check if credentials exists (it should, but be defensive)
            if 'credentials' in locals() and credentials is not None:
                if hasattr(credentials, 'username') and credentials.username:
                    credentials.username = obfuscate_credential(credentials.username)
                if hasattr(credentials, 'password') and credentials.password:
                    credentials.password = obfuscate_credential(credentials.password)
        except Exception:
            # Best effort - don't fail if obfuscation fails
            pass

