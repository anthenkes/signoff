from datetime import datetime, timezone
import logging
from playwright.sync_api import sync_playwright
from . import celery_app
from db import SessionLocal, User  # SQLAlchemy models
from db.models import TimecardRunStatus  # Enum for status
from kms.credentials import get_user_credentials_for_signoff
from signoff_models import SignoffUser  # Dataclass for signoff automation workflow
from signoff_timecard import sign_off_for_user
from config import get_app_config

logger = logging.getLogger(__name__)

@celery_app.task
def signoff_user_timecard(user_id: int):
    """Do the actual signoff for one user."""
    db = SessionLocal()
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

        # 1. Decrypt credentials using KMS
        try:
            creds_dict = get_user_credentials_for_signoff(db, user_id=user_id)
        except ValueError as e:
            logger.error(f"Failed to get credentials for user {user.email}: {e}")
            return
        except Exception as e:
            logger.error(f"Error decrypting credentials for user {user.email}: {e}")
            raise

        # 2. Create User dataclass for signoff automation
        signoff_user = SignoffUser(
            username=creds_dict["username"],
            password=creds_dict["password"],
            email=user.email,
            domain=creds_dict.get("domain", "MC Network"),
            name=f"{user.first_name} {user.last_name}".strip() if user.first_name or user.last_name else None,
            employee_id=user.user_id
        )

        # 3. Get app config for base_url and other settings
        app_config = get_app_config()
        base_url = app_config.get("base_url", "https://timecard.example.com")
        headless = app_config.get("headless", True)
        slow_mo = app_config.get("slow_mo", 0)

        # 4. Run Playwright automation
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
                
                # 5. Update DB with result
                user.last_timecard_signoff_at = datetime.now(timezone.utc)
                if result.success:
                    user.auto_signed_off_count += 1
                    user.last_timecard_check_status = TimecardRunStatus.LOGIN_SUCCESS_SIGNED_OFF
                else:
                    user.failed_login_count += 1
                    user.last_timecard_check_status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
                
                db.commit()
                logger.info(f"Signoff completed for user {user.email}: {result.message}")
                
            finally:
                browser.close()

    except Exception as e:
        db.rollback()
        logger.error(f"Error in signoff task for user_id {user_id}: {e}", exc_info=True)
        # Update user status on error
        try:
            user.last_timecard_check_status = TimecardRunStatus.LOGIN_FAILED_UNKNOWN_ERROR
            user.failed_login_count += 1
            db.commit()
        except:
            pass
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
