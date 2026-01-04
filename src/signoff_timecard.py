#!/usr/bin/env python3
"""
Main automation script for signing off time cards.
Handles login, navigation, sign-off confirmation, and email notifications.
"""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, Page

from src.config import load_users, get_app_config, validate_config
from src.signoff_models import SignoffUser, SignoffResult
from src.mail.email_service import EmailService
from src.utils import setup_logging, format_result_message, get_screenshot_path, get_persistent_screenshot_path
from src.play.pages.login_page import LoginPage
from src.play.pages.dashboard_page import DashboardPage
from src.play.pages.employee_page import EmployeePage
from src.play.pages.signoff_confirmation_page import SignOffConfirmationPage
from src.kms.utils import obfuscate_credential
from src.storage import get_bucket_service

logger = logging.getLogger(__name__)


def sign_off_for_user(user: SignoffUser, browser: Browser, base_url: str, headless: bool, slow_mo: int) -> SignoffResult:
    """
    Perform sign-off workflow for a single user.
    
    Args:
        user: The User object to sign off for
        browser: Playwright Browser instance
        base_url: Base URL for the application
        headless: Whether to run browser in headless mode
        slow_mo: Slow motion delay in milliseconds
    
    Returns:
        SignoffResult object with the outcome
    """
    context = None
    page = None
    confirmation_page = None
    screenshot_path = None
    
    try:
        logger.info(f"Starting sign-off process for user: {user.email}")
        
        # Create browser context
        context = browser.new_context()
        context.set_default_timeout(30000)
        page = context.new_page()
        
        # Navigate to login page
        login_page = LoginPage(page)
        login_page.goto(base_url)
        login_page.wait_for_page_load()
        
        # Perform login
        logger.info(f"Logging in for user: {user.email}")
        login_page.login(
            username=user.username,
            password=user.password,
            domain=user.domain
        )
        
        # Wait a moment for the page to process the login
        page.wait_for_timeout(2000)
        
        # Check for login errors before proceeding
        if login_page.has_login_error():
            error_message = login_page.get_login_error_message() or "Login failed - invalid credentials"
            logger.error(f"Login error detected for {user.email}: {error_message}")
            screenshot_path = get_screenshot_path(user, "login_error")
            page.screenshot(path=screenshot_path, full_page=True)
            
            result = SignoffResult(
                user=user,
                success=False,
                message=f"Login failed: {error_message}",
                timestamp=datetime.now(),
                screenshot_path=screenshot_path,
                error=f"Login error: {error_message}"
            )
            # Clear plaintext credentials
            try:
                user.password = obfuscate_credential(user.password)
                user.username = obfuscate_credential(user.username)
            except Exception:
                pass
            return result
        
        # Wait for dashboard to load (this waits for specific elements)
        dashboard_page = DashboardPage(page)
        dashboard_page.wait_for_dashboard_load()
        logger.info("Login successful, navigated to dashboard")
        
        # Navigate to Employee page
        dashboard_page.navigate_to_employee()
        
        # Click Employee sign Off button
        employee_page = EmployeePage(page)
        employee_page.wait_for_employee_page_load()
        
        # Check if user has already signed off
        if employee_page.is_already_signed_off():
            logger.info(f"User {user.email} has already signed off their timecard")
            
            # Capture blue thumbs up icon screenshot (confirmation of signoff)
            screenshot_path = None
            try:
                # Use the specialized method to capture blue thumbs up icon with tooltip
                screenshot_path = employee_page.capture_blue_thumbs_up_tooltip()
                logger.info(f"Blue thumbs up icon screenshot saved to {screenshot_path}")
                
                # Move to persistent location and upload to Railway Bucket if available
                persistent_path = get_persistent_screenshot_path(user)
                if screenshot_path != persistent_path:
                    # Remove old screenshot if it exists, then move new one
                    if Path(persistent_path).exists():
                        Path(persistent_path).unlink()
                    # Move screenshot to persistent location
                    Path(screenshot_path).rename(persistent_path)
                    screenshot_path = persistent_path
                
                # Upload to Railway Bucket if available
                bucket_service = get_bucket_service()
                if bucket_service:
                    try:
                        s3_key = bucket_service.upload_screenshot(screenshot_path, user)
                        if s3_key:
                            logger.info(f"Screenshot uploaded to bucket: {s3_key}")
                            # Optionally delete local file to save space
                            Path(screenshot_path).unlink(missing_ok=True)
                            screenshot_path = None  # Local file deleted, stored in bucket
                    except Exception as upload_error:
                        logger.warning(f"Failed to upload screenshot to bucket: {upload_error}")
                        # Keep local file as fallback
                else:
                    logger.debug("Bucket service not available, keeping local screenshot")
            except Exception as screenshot_error:
                logger.error(f"Failed to capture blue thumbs up screenshot: {screenshot_error}")
                # Try fallback: take full page screenshot
                try:
                    screenshot_path = get_persistent_screenshot_path(user)
                    page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"Fallback screenshot saved to {screenshot_path}")
                except Exception as fallback_error:
                    logger.error(f"Failed to take fallback screenshot: {fallback_error}")
                    screenshot_path = None
            
            result = SignoffResult(
                user=user,
                success=True,
                message="Already signed off - no action needed",
                timestamp=datetime.now(),
                screenshot_path=screenshot_path
            )
            # Clear plaintext credentials
            try:
                user.password = obfuscate_credential(user.password)
                user.username = obfuscate_credential(user.username)
            except Exception:
                pass
            return result
        
        if not employee_page.is_sign_off_button_visible():
            raise Exception("Employee sign Off button is not visible")
        
        logger.info("Clicking Employee sign Off button")
        confirmation_page_obj = employee_page.click_employee_sign_off()
        
        # Handle confirmation in new window
        confirmation_page = SignOffConfirmationPage(confirmation_page_obj)
        confirmation_page.wait_for_confirmation_load()
        
        logger.info("Confirming sign-off in new window")
        confirmation_page.confirm_sign_off()
        
        # After clicking approve, the confirmation window closes and returns to employee page
        # Wait a moment for the window to close
        confirmation_page_obj.wait_for_timeout(1000)
        
        # Verify success by checking if the confirmation window closed
        # (If it's closed, the sign-off was successful)
        try:
            # Try to check if the window is still open by checking for the approve button
            # If the window closed, this will fail, which indicates success
            confirmation_page.approve_button.is_visible(timeout=1000)
            # If we get here, the window is still open - this might indicate an issue
            logger.warning(f"Confirmation window still open after approve click for {user.email}")
            success = False
            message = "Sign-off confirmation window did not close"
            screenshot_path = get_screenshot_path(user, "signoff_issue")
            confirmation_page.take_screenshot(screenshot_path.split("/")[-1])
        except Exception:
            # Window closed - this is expected and indicates success
            logger.info(f"Confirmation window closed - sign-off successful for {user.email}")
            
            # Wait for employee page to update (button changes to "Un-Sign Off" and blue thumbs up appears)
            # This ensures we capture the blue thumbs up icon
            try:
                page.wait_for_timeout(2000)  # Give page time to update
                # Wait for the Un-Sign Off button to appear (confirms signoff state)
                frame_locator = employee_page._get_employee_actions_frame_locator()
                unsign_off_button = frame_locator.locator("#formContentPlaceHolder_employeeUnsignOffApiButton")
                unsign_off_button.wait_for(state="visible", timeout=10000)
                logger.info("Employee page updated - Un-Sign Off button visible")
                
                # Wait for blue thumbs up icon to appear
                if employee_page.is_blue_thumbs_up():
                    logger.info("Blue thumbs up icon is visible - ready to capture screenshot")
                else:
                    logger.warning("Blue thumbs up icon not yet visible, waiting...")
                    page.wait_for_timeout(1000)  # Additional wait for icon to appear
            except Exception as wait_error:
                logger.warning(f"Could not verify employee page update: {wait_error}")
                # Continue anyway - page may have updated
            
            # Capture blue thumbs up icon screenshot (confirmation of signoff)
            screenshot_path = None
            try:
                # Use the specialized method to capture blue thumbs up icon with tooltip
                screenshot_path = employee_page.capture_blue_thumbs_up_tooltip()
                logger.info(f"Blue thumbs up icon screenshot saved to {screenshot_path}")
                
                # Move to persistent location and upload to Railway Bucket if available
                persistent_path = get_persistent_screenshot_path(user)
                if screenshot_path != persistent_path:
                    # Remove old screenshot if it exists, then move new one
                    if Path(persistent_path).exists():
                        Path(persistent_path).unlink()
                    # Move screenshot to persistent location
                    Path(screenshot_path).rename(persistent_path)
                    screenshot_path = persistent_path
                
                # Upload to Railway Bucket if available
                bucket_service = get_bucket_service()
                if bucket_service:
                    try:
                        s3_key = bucket_service.upload_screenshot(screenshot_path, user)
                        if s3_key:
                            logger.info(f"Screenshot uploaded to bucket: {s3_key}")
                            # Optionally delete local file to save space
                            Path(screenshot_path).unlink(missing_ok=True)
                            screenshot_path = None  # Local file deleted, stored in bucket
                    except Exception as upload_error:
                        logger.warning(f"Failed to upload screenshot to bucket: {upload_error}")
                        # Keep local file as fallback
                else:
                    logger.debug("Bucket service not available, keeping local screenshot")
            except Exception as screenshot_error:
                logger.error(f"Failed to capture blue thumbs up screenshot: {screenshot_error}")
                # Try fallback: take full page screenshot
                try:
                    screenshot_path = get_persistent_screenshot_path(user)
                    page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"Fallback screenshot saved to {screenshot_path}")
                except Exception as fallback_error:
                    logger.error(f"Failed to take fallback screenshot: {fallback_error}")
                    screenshot_path = None
            
            success = True
            message = "Sign-off completed"
        
        # If window didn't close automatically, close it manually
        try:
            if not confirmation_page_obj.is_closed():
                confirmation_page_obj.close()
        except Exception:
            # Window already closed, ignore
            pass
        
        result = SignoffResult(
            user=user,
            success=success,
            message=message,
            timestamp=datetime.now(),
            screenshot_path=screenshot_path
        )
        
        # Clear plaintext credentials from user object after login (success or failure)
        # This helps minimize the time plaintext credentials exist in memory
        # Uses random-length obfuscation to prevent length inference
        try:
            user.password = obfuscate_credential(user.password)
            user.username = obfuscate_credential(user.username)
        except Exception:
            pass  # Best effort - don't fail if clearing fails
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Error during sign-off for {user.email}: {error_msg}", exc_info=True)
        
        # Take screenshot on error
        screenshot_path = None
        try:
            if page:
                screenshot_path = get_screenshot_path(user, "error")
                page.screenshot(path=screenshot_path, full_page=True)
        except Exception as screenshot_error:
            logger.error(f"Failed to take screenshot: {screenshot_error}")
        
        # Check for login errors if we're still on the login page
        login_error_detected = False
        login_error_message = None
        try:
            if page and not page.is_closed():
                # Check if we're still on the login page
                current_url = page.url
                if "Login.aspx" in current_url:
                    login_page = LoginPage(page)
                    if login_page.has_login_error():
                        login_error_detected = True
                        login_error_message = login_page.get_login_error_message()
        except Exception:
            pass  # Best effort - if we can't check, continue with generic error
        
        # Categorize the error type
        error_msg_lower = error_msg.lower()
        error_type_lower = error_type.lower()
        
        # Determine error category for better tracking
        if login_error_detected and login_error_message:
            # Login/credential error detected from page
            categorized_error = f"Login error: {login_error_message}"
        elif any(term in error_type_lower for term in ["timeout", "timeouterror"]):
            # Timeout errors (site/network issues)
            categorized_error = f"Site timeout: {error_msg}"
        elif any(term in error_msg_lower for term in ["timeout", "network", "connection", "502", "503", "504", "500"]):
            # Network/site errors
            categorized_error = f"Site error: {error_msg}"
        elif any(term in error_msg_lower for term in ["credential", "password", "login", "authentication", "unauthorized", "invalid", "user does not exist"]):
            # Credential/authentication errors
            categorized_error = f"Credential error: {error_msg}"
        elif any(term in error_msg_lower for term in ["not found", "not visible", "element", "locator", "selector"]):
            # Automation errors (element not found, page structure changed)
            categorized_error = f"Automation error: {error_msg}"
        else:
            # Unknown/generic errors
            categorized_error = f"Error: {error_msg}"
        
        result = SignoffResult(
            user=user,
            success=False,
            message=f"Sign-off failed: {categorized_error}",
            timestamp=datetime.now(),
            screenshot_path=screenshot_path,
            error=categorized_error
        )
        
        # Clear plaintext credentials from user object on error
        # Uses random-length obfuscation to prevent length inference
        try:
            user.password = obfuscate_credential(user.password)
            user.username = obfuscate_credential(user.username)
        except Exception:
            pass  # Best effort - don't fail if clearing fails
        
        return result
    
    finally:
        # Clean up browser resources and ensure credentials are cleared
        # This runs regardless of success or failure
        try:
            if confirmation_page:
                confirmation_page.page.close()
            if context:
                context.close()
            
            # Clear plaintext credentials (defense in depth - may already be cleared)
            # This ensures credentials are cleared even if previous clearing failed
            # Note: We overwrite (not delete) because these are required dataclass fields
            # Overwriting ensures the memory is cleared even if the object persists
            # Uses random-length obfuscation to prevent length inference
            try:
                if hasattr(user, 'password'):
                    # Check if password is not already cleared (not all null bytes)
                    if user.password and not all(c == '\x00' for c in user.password):
                        # Overwrite with random-length null bytes (obfuscates original length)
                        user.password = obfuscate_credential(user.password)
                if hasattr(user, 'username'):
                    # Check if username is not already cleared (not all null bytes)
                    if user.username and not all(c == '\x00' for c in user.username):
                        # Overwrite with random-length null bytes (obfuscates original length)
                        user.username = obfuscate_credential(user.username)
            except Exception:
                pass  # Best effort - credentials may already be cleared or attribute may not exist
                
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Automate time card sign-off for multiple users")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--user", type=str, help="Process only a specific user (by username)")
    parser.add_argument("--config", type=str, help="Path to users.json configuration file")
    parser.add_argument("--log-file", type=str, help="Path to log file")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        validate_config()
        
        # Load users
        users = load_users(config_path=args.config)
        
        # Filter to specific user if requested
        if args.user:
            users = [u for u in users if u.username == args.user]
            if not users:
                logger.error(f"User '{args.user}' not found in configuration")
                sys.exit(1)
        
        # Get app configuration
        app_config = get_app_config()
        base_url = app_config["base_url"]
        headless = args.headless or app_config["headless"]
        slow_mo = app_config["slow_mo"]
        
        logger.info(f"Processing {len(users)} user(s)")
        logger.info(f"Base URL: {base_url}")
        logger.info(f"Headless mode: {headless}")
        
        # Initialize email service
        try:
            email_service = EmailService()
            logger.info("Email service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            logger.warning("Continuing without email notifications")
            email_service = None
        
        # Process each user
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
            
            try:
                for user in users:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"Processing user: {user.email}")
                    logger.info(f"{'='*60}")
                    
                    result = sign_off_for_user(user, browser, base_url, headless, slow_mo)
                    results.append(result)
                    
                    # Log result
                    logger.info(format_result_message(result))
                    
                    # Send email notification
                    if email_service:
                        try:
                            email_service.send_signoff_result(result)
                        except Exception as e:
                            logger.error(f"Failed to send email to {user.email}: {e}")
                    
                    logger.info(f"Completed processing for {user.email}\n")
            
            finally:
                browser.close()
        
        # Print summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        logger.info(f"\n{'='*60}")
        logger.info("SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total users processed: {len(results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"{'='*60}\n")
        
        # Exit with appropriate code
        if failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
    
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

