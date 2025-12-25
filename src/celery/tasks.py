from datetime import datetime, timezone
import logging
from playwright.sync_api import sync_playwright
from . import celery_app
from db import SessionLocal  # SQLAlchemy session
from db.models import User, TimecardRunStatus, TimecardRun, Credential  # SQLAlchemy models
from kms.credentials import get_user_credentials_for_signoff
from signoff_models import SignoffUser  # Dataclass for signoff automation workflow
from signoff_timecard import sign_off_for_user
from config import get_app_config
from utils import is_bi_weekly_sunday

logger = logging.getLogger(__name__)

# Try to import EmailService for admin alerts
try:
    from mail.email_service import EmailService
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    logger.warning("EmailService not available. Admin alerts will not be sent.")


def categorize_error_status(error_message: str, error_type: str | None = None) -> TimecardRunStatus:
    """
    Categorize an error message into the appropriate TimecardRunStatus.
    
    This function checks for specific error prefixes from signoff_timecard.py first
    (which uses login_page.py error detection), then falls back to pattern matching.
    
    Args:
        error_message: The error message string
        error_type: Optional exception type name (for exception handling cases)
    
    Returns:
        The appropriate TimecardRunStatus enum value
    """
    error_lower = error_message.lower()
    error_type_lower = (error_type or "").lower()
    
    # Check for specific error prefixes from signoff_timecard.py first (most accurate)
    # These prefixes are added by signoff_timecard.py based on login_page.py error detection
    if error_lower.startswith("login error:") or error_lower.startswith("credential error:"):
        # Login/credential errors detected from login page or categorized as credential errors
        return TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
    elif error_lower.startswith("site error:") or error_lower.startswith("site timeout:"):
        # Site/network errors
        return TimecardRunStatus.LOGIN_FAILED_SITE_ERROR
    elif error_lower.startswith("automation error:"):
        # Automation errors (element not found, page structure changed)
        return TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
    
    # Fallback to pattern matching for errors without specific prefixes
    # Check exception type first (for exception handling cases)
    if error_type_lower and any(term in error_type_lower for term in ["timeout", "playwright", "browser"]):
        return TimecardRunStatus.LOGIN_FAILED_SITE_ERROR
    
    # Check error message patterns
    if any(term in error_lower for term in ["credential", "password", "login", "authentication", "unauthorized", "invalid", "user does not exist", "401", "403"]):
        return TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
    elif any(term in error_lower for term in ["timeout", "network", "connection", "site", "server", "502", "503", "504", "500", "playwright", "browser"]):
        return TimecardRunStatus.LOGIN_FAILED_SITE_ERROR
    
    # Database errors and other internal errors remain as unknown
    return TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR


@celery_app.task
def signoff_user_timecard(user_id: int):
    """Do the actual signoff for one user."""
    db = SessionLocal()
    timecard_run = None
    user = None
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User with id {user_id} not found")
            return

        # Skip if flagged for password update
        if user.needs_password:
            logger.info(f"Skipping user {user.email} - needs password update")
            return

        # Optionally: Guard against double-runs (check last_signoff_date)
        # if user.last_timecard_signoff_at and recently_run(...):
        #     return

        # 1. Get credential record (needed for TimecardRun)
        credential = (
            db.query(Credential)
            .filter(
                Credential.user_db_id == user.id,
                Credential.site == "timecard_portal"
            )
            .first()
        )
        
        if not credential:
            logger.error(f"No credentials found for user {user.email}")
            # Set last_timecard_check_at even when credentials are missing
            user.last_timecard_check_at = datetime.now(timezone.utc)
            user.last_timecard_check_status = TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
            db.commit()
            
            # Send admin alert about missing credentials
            if EMAIL_SERVICE_AVAILABLE:
                try:
                    email_service = EmailService()
                    email_service.send_admin_alert(
                        "User Missing Credentials",
                        f"User {user.email} (ID: {user.id}) was queued for signoff but has no credentials stored. "
                        f"The signoff task was skipped. Please ensure credentials are set up for this user.",
                        f"User ID: {user.id}\nUser Email: {user.email}\nUser Name: {user.first_name} {user.last_name}"
                    )
                except Exception as alert_error:
                    logger.error(f"Failed to send admin alert for missing credentials: {alert_error}")
            
            return

        # 2. Set last_timecard_check_at (attempt timestamp) - tracks when we tried to log in
        check_timestamp = datetime.now(timezone.utc)
        user.last_timecard_check_at = check_timestamp
        
        # 3. Create TimecardRun record at the start
        # Store the credential's dek_version to detect race conditions
        stored_dek_version = credential.dek_version
        timecard_run = TimecardRun(
            user_db_id=user.id,
            credential_id=credential.id,
            credential_dek_version=stored_dek_version,
            started_at=check_timestamp,
            status=TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR,  # Default, will update on completion
            login_success=False,
            signed_off_performed=False,
            already_signed_off_detected=False
        )
        db.add(timecard_run)
        db.commit()  # Commit early to get the ID
        logger.info(f"Created TimecardRun record {timecard_run.id} for user {user.email}")

        # 4. Decrypt credentials using KMS
        # Check for race condition: credentials may have been updated after TimecardRun was created
        try:
            # Refresh credential from database to get latest version
            db.refresh(credential)
            current_dek_version = credential.dek_version
            
            if current_dek_version != stored_dek_version:
                logger.warning(
                    f"Credential version changed during signoff run for user {user.email}. "
                    f"TimecardRun was created with dek_version={stored_dek_version}, "
                    f"but current version is {current_dek_version}. "
                    f"Using current credentials (credentials were updated mid-run)."
                )
                # Update TimecardRun to reflect the version actually used
                timecard_run.credential_dek_version = current_dek_version
                db.commit()
            
            creds_dict = get_user_credentials_for_signoff(db, user_id=user_id)
        except ValueError as e:
            logger.error(f"Failed to get credentials for user {user.email}: {e}")
            # Ensure last_timecard_check_at is set even on early failure
            if user.last_timecard_check_at is None:
                user.last_timecard_check_at = datetime.now(timezone.utc)
            timecard_run.completed_at = datetime.now(timezone.utc)
            timecard_run.status = TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
            timecard_run.error_reason = str(e)
            db.commit()
            return
        except Exception as e:
            logger.error(f"Error decrypting credentials for user {user.email}: {e}")
            # Ensure last_timecard_check_at is set even on early failure
            if user.last_timecard_check_at is None:
                user.last_timecard_check_at = datetime.now(timezone.utc)
            timecard_run.completed_at = datetime.now(timezone.utc)
            timecard_run.status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
            timecard_run.error_reason = f"Decryption error: {str(e)}"
            db.commit()
            raise

        # 5. Create User dataclass for signoff automation
        signoff_user = SignoffUser(
            username=creds_dict["username"],
            password=creds_dict["password"],
            email=user.email,
            domain=creds_dict.get("domain", "MC Network"),
            name=f"{user.first_name} {user.last_name}".strip() if user.first_name or user.last_name else None,
            employee_id=user.user_id
        )

        # 6. Get app config for base_url and other settings
        app_config = get_app_config()
        base_url = app_config.get("base_url", "https://timecard.example.com")
        headless = app_config.get("headless", True)
        slow_mo = app_config.get("slow_mo", 0)

        # 7. Run Playwright automation
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
            try:
                result = sign_off_for_user(
                    user=signoff_user,
                    browser=browser,
                    base_url=base_url,
                    headless=headless,
                    slow_mo=slow_mo
                )
                
                # 8. Determine status from result
                message_lower = (result.message or "").lower()
                
                if result.success:
                    # Check if already signed off (based on message)
                    # TODO: add the emailing of the screenshot here
                    if "already" in message_lower or "already signed" in message_lower:
                        run_status = TimecardRunStatus.LOGIN_SUCCESS_ALREADY_SIGNED
                        timecard_run.already_signed_off_detected = True
                        user.already_signed_off_count += 1
                    else:
                        run_status = TimecardRunStatus.LOGIN_SUCCESS_SIGNED_OFF
                        timecard_run.signed_off_performed = True
                        user.auto_signed_off_count += 1
                    timecard_run.login_success = True
                    success_timestamp = datetime.now(timezone.utc)
                    user.last_timecard_signoff_at = success_timestamp
                    credential.last_success_at = success_timestamp
                else:
                    # Determine failure type from error message
                    run_status = categorize_error_status(result.error or "")
                    user.failed_login_count += 1
                
                # 9. Update TimecardRun record
                timecard_run.completed_at = datetime.now(timezone.utc)
                timecard_run.status = run_status
                timecard_run.error_reason = result.error[:255] if result.error else None  # Truncate to fit String(255)
                
                # 10. Update User record
                user.last_timecard_check_status = run_status
                # Note: last_timecard_check_at was already set at the start of the attempt
                
                db.commit()
                logger.info(f"Signoff completed for user {user.email}: {result.message}")
                
            finally:
                browser.close()

    except Exception as e:
        db.rollback()
        logger.error(f"Error in signoff task for user_id {user_id}: {e}", exc_info=True)
        
        # Determine error type based on exception class and message
        error_msg = str(e)
        error_type = type(e).__name__
        run_status = categorize_error_status(error_msg, error_type)
        
        # Update TimecardRun and User status on error
        # Note: After rollback, we need to re-query objects since they're detached from the session
        try:
            if timecard_run is not None:
                # Re-query timecard_run after rollback since it's detached from the session
                timecard_run = db.query(TimecardRun).filter(TimecardRun.id == timecard_run.id).first()
                if timecard_run:
                    timecard_run.completed_at = datetime.now(timezone.utc)
                    timecard_run.status = run_status
                    timecard_run.error_reason = f"Exception: {str(e)[:255]}"  # Truncate to fit String(255)
            if user is not None:
                # Re-query user after rollback since it's detached from the session
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Ensure last_timecard_check_at is set even on exception
                    if user.last_timecard_check_at is None:
                        user.last_timecard_check_at = datetime.now(timezone.utc)
                    user.last_timecard_check_status = run_status
                    user.failed_login_count += 1
            db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update records on error: {update_error}")
            db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def enqueue_all_signoffs_if_needed():
    """
    Runs on a schedule (e.g., weekly).
    If it's a 'signoff Sunday', enqueue signoff jobs for all eligible users.
    """
    if not is_bi_weekly_sunday():
        logger.info("Not a signoff Sunday, skipping enqueue")
        return

    db = SessionLocal()
    try:
        # Only users who:
        # - do NOT need password update
        # - have credentials stored
        users = (
            db.query(User)
            .filter(
                User.needs_password == False,
            )
            .all()
        )

        # Filter users who have credentials
        eligible_users = []
        users_without_credentials = []
        for user in users:
            # Check if user has credentials
            if user.credentials:
                eligible_users.append(user)
            else:
                logger.warning(f"User {user.email} has no credentials stored")
                users_without_credentials.append(user)
        
        # Send admin alert if there are users without credentials
        if users_without_credentials and EMAIL_SERVICE_AVAILABLE:
            try:
                email_service = EmailService()
                user_list = ", ".join([f"{u.email} (ID: {u.id})" for u in users_without_credentials])
                email_service.send_admin_alert(
                    "Users Missing Credentials During Enqueue",
                    f"Found {len(users_without_credentials)} user(s) without credentials during signoff enqueue. "
                    f"These users were skipped and will not receive automated signoffs.",
                    f"Users without credentials:\n{user_list}\n\nTotal eligible users enqueued: {len(eligible_users)}"
                )
            except Exception as alert_error:
                logger.error(f"Failed to send admin alert for users without credentials: {alert_error}")

        logger.info(f"Enqueuing signoff tasks for {len(eligible_users)} eligible users")
        for user in eligible_users:
            signoff_user_timecard.delay(user.id)

    except Exception as e:
        logger.error(f"Error in enqueue_all_signoffs_if_needed: {e}", exc_info=True)
        raise
    finally:
        db.close()
