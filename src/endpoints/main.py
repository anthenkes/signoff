"""
FastAPI application main file.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPHeader
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from typing import Optional
from contextlib import asynccontextmanager
import os
import logging
import secrets
from datetime import datetime, timedelta, timezone

from .config import get_api_config
from db.database import init_db, get_db, Base, get_engine
from db.models import MagicLink, Signup

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
    """Middleware to protect internal routes (all except /signup and /submit-signup)."""
    path = request.url.path
    
    # Public routes that don't need protection
    public_routes = ["/api/validate-magic-link", "/submit-signup", "/docs", "/openapi.json", "/redoc"]
    
    # If it's not a public route, check for internal secret
    if not any(path.startswith(route) for route in public_routes):
        secret = request.headers.get("X-Internal-Secret")
        expected_secret = get_internal_secret()
        
        if secret != expected_secret:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied. This endpoint is internal only."}
            )
    
    response = await call_next(request)
    return response




# Pydantic models for magic link and signup
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


class SignupRequest(BaseModel):
    """Request model for signup submission."""
    token: str = Field(..., description="Magic link token")
    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    username: Optional[str] = Field(None, max_length=255, description="Username (optional)")
    employee_id: Optional[str] = Field(None, max_length=255, description="Employee ID (optional)")


class SignupResponse(BaseModel):
    """Response model for signup submission."""
    success: bool
    message: str
    signup_id: Optional[int] = None


# Internal endpoint to generate magic link
@app.post("/api/magic-link", response_model=MagicLinkResponse)
async def create_magic_link(
    request: MagicLinkRequest,
    db: Session = Depends(get_db)
):
    """Internal endpoint to generate a magic link. Requires internal secret."""
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
        link = f"{frontend_url}/signup?token={token}"
        
        logger.info(f"Magic link created: email={request.email}, expires_at={expires_at}")
        
        return MagicLinkResponse(
            success=True,
            message="Magic link created successfully",
            token=token,
            link=link,
            expires_at=expires_at
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating magic link: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the magic link."
        )


# Public API endpoint to validate magic link
@app.get("/api/validate-magic-link")
async def validate_magic_link(
    token: str = Query(..., description="Magic link token"),
    db: Session = Depends(get_db)
):
    """Public API endpoint to validate a magic link token."""
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
    
    return {
        "valid": True,
        "email": magic_link.email
    }


# Public endpoint to process signup submission
@app.post("/submit-signup", response_model=SignupResponse)
async def submit_signup(
    signup: SignupRequest,
    db: Session = Depends(get_db)
):
    """Public endpoint to process signup submission. Validates magic link and saves signup."""
    try:
        # Validate the magic link
        magic_link = db.query(MagicLink).filter(MagicLink.token == signup.token).first()
        
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
        
        # Verify email matches
        if signup.email.lower() != magic_link.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address does not match the magic link."
            )
        
        # Create signup record
        db_signup = Signup(
            name=signup.name,
            email=signup.email,
            username=signup.username,
            employee_id=signup.employee_id,
            magic_link_id=magic_link.id
        )
        
        db.add(db_signup)
        
        # Mark magic link as used
        magic_link.used = True
        magic_link.used_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(db_signup)
        
        logger.info(f"Signup completed: ID={db_signup.id}, Email={signup.email}")
        
        return SignupResponse(
            success=True,
            message="Thank you! Your signup has been completed successfully.",
            signup_id=db_signup.id
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your signup. Please try again later."
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

