from datetime import datetime, timezone
import logging
from playwright.sync_api import sync_playwright
from . import celery_app
from db import SessionLocal, User  # SQLAlchemy models
from db.models import TimecardRunStatus, TimecardRun, Credential  # Enum for status and models
from kms.credentials import get_user_credentials_for_signoff
from signoff_models import SignoffUser  # Dataclass for signoff automation workflow
from signoff_timecard import sign_off_for_user
from config import get_app_config

logger = logging.getLogger(__name__)

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
            return

        # 2. Create TimecardRun record at the start
        timecard_run = TimecardRun(
            user_db_id=user.id,
            credential_id=credential.id,
            started_at=datetime.now(timezone.utc),
            status=TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR,  # Default, will update on completion
            login_success=False,
            signed_off_performed=False,
            already_signed_off_detected=False
        )
        db.add(timecard_run)
        db.commit()  # Commit early to get the ID
        logger.info(f"Created TimecardRun record {timecard_run.id} for user {user.email}")

        # 3. Decrypt credentials using KMS
        try:
            creds_dict = get_user_credentials_for_signoff(db, user_id=user_id)
        except ValueError as e:
            logger.error(f"Failed to get credentials for user {user.email}: {e}")
            timecard_run.completed_at = datetime.now(timezone.utc)
            timecard_run.status = TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
            timecard_run.error_reason = str(e)
            db.commit()
            return
        except Exception as e:
            logger.error(f"Error decrypting credentials for user {user.email}: {e}")
            timecard_run.completed_at = datetime.now(timezone.utc)
            timecard_run.status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
            timecard_run.error_reason = f"Decryption error: {str(e)}"
            db.commit()
            raise

        # 4. Create User dataclass for signoff automation
        signoff_user = SignoffUser(
            username=creds_dict["username"],
            password=creds_dict["password"],
            email=user.email,
            domain=creds_dict.get("domain", "MC Network"),
            name=f"{user.first_name} {user.last_name}".strip() if user.first_name or user.last_name else None,
            employee_id=user.user_id
        )

        # 5. Get app config for base_url and other settings
        app_config = get_app_config()
        base_url = app_config.get("base_url", "https://timecard.example.com")
        headless = app_config.get("headless", True)
        slow_mo = app_config.get("slow_mo", 0)

        # 6. Run Playwright automation
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
                
                # 7. Determine status from result
                error_lower = (result.error or "").lower()
                message_lower = (result.message or "").lower()
                
                if result.success:
                    # Check if already signed off (based on message)
                    if "already" in message_lower or "already signed" in message_lower:
                        run_status = TimecardRunStatus.LOGIN_SUCCESS_ALREADY_SIGNED
                        timecard_run.already_signed_off_detected = True
                        user.already_signed_off_count += 1
                    else:
                        run_status = TimecardRunStatus.LOGIN_SUCCESS_SIGNED_OFF
                        timecard_run.signed_off_performed = True
                        user.auto_signed_off_count += 1
                    timecard_run.login_success = True
                    user.last_timecard_signoff_at = datetime.now(timezone.utc)
                else:
                    # Determine failure type from error message
                    if any(term in error_lower for term in ["credential", "password", "login", "authentication", "unauthorized"]):
                        run_status = TimecardRunStatus.LOGIN_FAILED_BAD_CREDENTIALS
                    elif any(term in error_lower for term in ["timeout", "network", "connection", "site", "server"]):
                        run_status = TimecardRunStatus.LOGIN_FAILED_SITE_ERROR
                    else:
                        run_status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
                    user.failed_login_count += 1
                
                # 8. Update TimecardRun record
                timecard_run.completed_at = datetime.now(timezone.utc)
                timecard_run.status = run_status
                timecard_run.error_reason = result.error[:255] if result.error else None  # Truncate to fit String(255)
                
                # 9. Update User record
                user.last_timecard_check_status = run_status
                
                db.commit()
                logger.info(f"Signoff completed for user {user.email}: {result.message}")
                
            finally:
                browser.close()

    except Exception as e:
        db.rollback()
        logger.error(f"Error in signoff task for user_id {user_id}: {e}", exc_info=True)
        # Update TimecardRun and User status on error
        try:
            if timecard_run is not None:
                timecard_run.completed_at = datetime.now(timezone.utc)
                timecard_run.status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
                timecard_run.error_reason = f"Exception: {str(e)[:255]}"  # Truncate to fit String(255)
            if user is not None:
                user.last_timecard_check_status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
                user.failed_login_count += 1
            db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update records on error: {update_error}")
        raise
    finally:
        db.close()


@celery_app.task
def enqueue_all_signoffs_if_needed():
    """
    Runs on a schedule (e.g., weekly).
    If it's a 'signoff Sunday', enqueue signoff jobs for all eligible users.
    """
    if not is_signoff_sunday():
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
        for user in users:
            # Check if user has credentials
            if user.credentials:
                eligible_users.append(user)
            else:
                logger.warning(f"User {user.email} has no credentials stored")

        logger.info(f"Enqueuing signoff tasks for {len(eligible_users)} eligible users")
        for user in eligible_users:
            signoff_user_timecard.delay(user.id)

    except Exception as e:
        logger.error(f"Error in enqueue_all_signoffs_if_needed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def is_signoff_sunday() -> bool:
    """
    Decide if this is a 'signoff Sunday'.
    Options:
      - Check calendar parity (e.g., every 2 weeks from a known anchor date).
      - Or, store last_global_signoff_date in a settings table and require >= 14 days.
    """
    today = datetime.now(timezone.utc).date()
    # Example: every other Sunday based on week number parity
    # Adjust to your real pay-period logic.
    return today.weekday() == 6 and (today.isocalendar().week % 2 == 0)
