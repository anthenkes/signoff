"""
Email service for sending sign-off results using Resend API.
Admin emails are sent via Mailtrap.
"""
import logging
import base64
import os
from typing import List, Optional
from sqlalchemy.orm import Session
from src.signoff_models import SignoffResult, SignoffUser
from src.mail.config import get_email_config
from src.storage import get_bucket_service

logger = logging.getLogger(__name__)

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend package not available. Email functionality will be disabled.")

try:
    import mailtrap as mt
    MAILTRAP_AVAILABLE = True
except ImportError:
    MAILTRAP_AVAILABLE = False
    logger.warning("Mailtrap package not available. Admin email functionality will be disabled.")


class EmailService:
    """Service for sending emails using Resend API."""

    def __init__(self):
        """Initialize the email service with configuration."""
        if not RESEND_AVAILABLE:
            raise ImportError("Resend package is not installed. Install with: pip install resend")
        
        email_config = get_email_config()
        # Set the API key at module level for Resend
        resend.api_key = email_config["api_key"]
        self.from_email = email_config["from_email"]
        self.from_name = email_config.get("from_name", "Time Card Automation")  # type: ignore

    def _get_deletion_link(self, email: str, db_session: Optional[Session] = None) -> Optional[str]:
        """
        Generate a deletion magic link for a user (same pattern as credentials magic link).
        The link is stored in the database.
        
        Args:
            email: The user's email address
            db_session: Database session (optional - if None, returns None and logs warning)
        
        Returns:
            The full URL for account deletion, or None if db_session is not provided
        """
        if db_session is None:
            logger.warning(f"Cannot generate deletion link for {email}: database session not available")
            return None
        
        # Import here to avoid circular imports
        from src.endpoints.main import generate_deletion_magic_link
        try:
            return generate_deletion_magic_link(email, db_session)
        except Exception as e:
            logger.error(f"Failed to generate deletion magic link for {email}: {e}")
            return None

    def send_signoff_result(self, result: SignoffResult, db_session: Optional[Session] = None) -> bool:
        """
        Send email to user with their sign-off result.
        
        Args:
            result: The SignoffResult object containing sign-off information
            db_session: Database session (optional - deletion link will be omitted if not provided)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if result.success:
                subject, html_content = self.format_success_email(result, db_session)
            else:
                subject, html_content = self.format_error_email(result, db_session)
            
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [result.user.email],
                "subject": subject,
                "html": html_content
            }
            
            # Always try to attach screenshot (blue thumbs up icon) unless signoff completely failed
            # Screenshot should be available for all successful signoffs (including "already signed off")
            screenshot_attached = False
            if result.success:  # Only attach screenshots for successful signoffs
                try:
                    # First try to get screenshot from bucket
                    bucket_service = get_bucket_service()
                    screenshot_base64 = None
                    
                    if bucket_service:
                        screenshot_base64 = bucket_service.get_screenshot_base64(result.user)
                    
                    # If not in bucket, try local file
                    if not screenshot_base64 and result.screenshot_path:
                        try:
                            with open(result.screenshot_path, 'rb') as f:
                                screenshot_bytes = f.read()
                                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                        except Exception as local_error:
                            logger.warning(f"Failed to read local screenshot file: {local_error}")
                    
                    # Attach screenshot if available (should always be available for successful signoffs)
                    if screenshot_base64:
                        params["attachments"] = [{
                            "filename": f"{result.user.email}_signoff_confirmed.png",
                            "content": screenshot_base64,
                            "type": "image/png"
                        }]
                        screenshot_attached = True
                        logger.info(f"Attaching blue thumbs up screenshot to email for {result.user.email}")
                    else:
                        logger.warning(f"No screenshot available for successful signoff - email sent without attachment")
                except Exception as attach_error:
                    logger.warning(f"Failed to attach screenshot to email: {attach_error}")
                    # Continue without attachment rather than failing
            # Note: For failed signoffs, we don't attach screenshots (as per requirement)
            
            email = resend.Emails.send(params)
            
            # Resend returns a TypedDict, so access id as a dictionary key
            email_id = email.get("id", "unknown")
            attachment_note = " (with screenshot)" if screenshot_attached else ""
            logger.info(f"Email sent successfully to {result.user.email}{attachment_note}. Email ID: {email_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending email to {result.user.email}: {e}")
            return False

    def format_success_email(self, result: SignoffResult, db_session: Optional[Session] = None) -> tuple[str, str]:
        """
        Format email template for successful sign-off.
        
        Args:
            result: The SignoffResult object
            db_session: Database session (optional - deletion link will be omitted if not provided)
        
        Returns:
            Tuple of (subject, html_content)
        """
        user_name = result.user.name or result.user.username
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        deletion_link = self._get_deletion_link(result.user.email, db_session)
        
        subject = f"Time Card Sign-Off Successful - {timestamp}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #28a745;">Time Card Sign-Off Successful</h2>
            <p>Hello {user_name},</p>
            <p>Your time card has been successfully signed off.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Username:</strong> {result.user.username}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Status:</strong> <span style="color: #28a745;">Success</span></p>
            </div>
            <p>{result.message}</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                This is an automated message from the Time Card Sign-Off system.
            </p>
            {f'<p style="margin-top: 20px; color: #666; font-size: 0.85em;"><a href="{deletion_link}" style="color: #dc3545; text-decoration: none;">Delete my account</a> - If you no longer wish to use this service, you can permanently delete your account using this link.</p>' if deletion_link else ''}
        </body>
        </html>
        """
        
        return subject, html_content

    def format_error_email(self, result: SignoffResult, db_session: Optional[Session] = None) -> tuple[str, str]:
        """
        Format email template for failed sign-off.
        
        Args:
            result: The SignoffResult object
            db_session: Database session (optional - deletion link will be omitted if not provided)
        
        Returns:
            Tuple of (subject, html_content)
        """
        user_name = result.user.name or result.user.username
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        deletion_link = self._get_deletion_link(result.user.email, db_session)
        
        subject = f"Time Card Sign-Off Failed - {timestamp}"
        
        error_details = result.error or result.message or "Unknown error occurred"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #dc3545;">Time Card Sign-Off Failed</h2>
            <p>Hello {user_name},</p>
            <p>Unfortunately, there was an error signing off your time card.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Username:</strong> {result.user.username}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Status:</strong> <span style="color: #dc3545;">Failed</span></p>
            </div>
            <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                <p><strong>Error Details:</strong></p>
                <p>{error_details}</p>
            </div>
            <p>Please try signing off manually or contact support if the issue persists.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                This is an automated message from the Time Card Sign-Off system.
            </p>
            {f'<p style="margin-top: 20px; color: #666; font-size: 0.85em;"><a href="{deletion_link}" style="color: #dc3545; text-decoration: none;">Delete my account</a> - If you no longer wish to use this service, you can permanently delete your account using this link.</p>' if deletion_link else ''}
        </body>
        </html>
        """
        
        return subject, html_content

    def format_multi_user_report(self, results: List[SignoffResult]) -> tuple[str, str]:
        """
        Format email template for summary report of multiple users.
        
        Args:
            results: List of SignoffResult objects
        
        Returns:
            Tuple of (subject, html_content)
        """
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        subject = f"Time Card Sign-Off Summary - {successful} Successful, {failed} Failed"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Time Card Sign-Off Summary Report</h2>
            <p>Summary of automated time card sign-off operations:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Total Users:</strong> {len(results)}</p>
                <p><strong>Successful:</strong> <span style="color: #28a745;">{successful}</span></p>
                <p><strong>Failed:</strong> <span style="color: #dc3545;">{failed}</span></p>
            </div>
            <h3>Details:</h3>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr style="background-color: #007bff; color: white;">
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">User</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Status</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Message</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for result in results:
            status_color = "#28a745" if result.success else "#dc3545"
            status_text = "Success" if result.success else "Failed"
            user_name = result.user.name or result.user.username
            
            html_content += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">{user_name}</td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: {status_color};"><strong>{status_text}</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{result.message[:100]}</td>
                    </tr>
            """
        
        html_content += """
                </tbody>
            </table>
            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                This is an automated report from the Time Card Sign-Off system.
            </p>
        </body>
        </html>
        """
        
        return subject, html_content

    def send_magic_link(self, email: str, magic_link: str, db_session: Optional[Session] = None) -> bool:
        """
        Send magic link email to user for credentials setup.
        
        Args:
            email: The recipient's email address
            magic_link: The full URL of the magic link
            db_session: Database session (optional - deletion link will be omitted if not provided)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            deletion_link = self._get_deletion_link(email, db_session)
            subject = "Complete Your Time Card Credentials Setup"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #007bff;">Time Card Credentials Setup</h2>
                    <p>Hello,</p>
                    <p>Click the button below to set up your time card credentials:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{magic_link}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">Set Up Credentials</a>
                    </div>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.9em;">{magic_link}</p>
                    <p style="color: #666; font-size: 0.9em; margin-top: 30px;">
                        <strong>Note:</strong> This link will expire in 24 hours.
                    </p>
                    <p style="color: #666; font-size: 0.9em; margin-top: 20px;">
                        If you did not request this link, please ignore this email.
                    </p>
                    {f'<hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;"><p style="margin-top: 20px; color: #666; font-size: 0.85em;"><a href="{deletion_link}" style="color: #dc3545; text-decoration: none;">Delete my account</a> - If you no longer wish to use this service, you can permanently delete your account using this link.</p>' if deletion_link else ''}
                </div>
            </body>
            </html>
            """
            
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [email],
                "subject": subject,
                "html": html_content
            }
            
            email_result = resend.Emails.send(params)
            email_id = email_result.get("id", "unknown")
            logger.info(f"Magic link email sent successfully to {email}. Email ID: {email_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending magic link email to {email}: {e}")
            return False

    def send_credentials_confirmation(self, email: str, first_name: Optional[str] = None, db_session: Optional[Session] = None) -> bool:
        """
        Send confirmation email to user after credentials are successfully saved.
        
        Args:
            email: The recipient's email address
            first_name: Optional first name for personalization
            db_session: Database session (optional - deletion link will be omitted if not provided)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            deletion_link = self._get_deletion_link(email, db_session)
            user_name = first_name or "there"
            subject = "Time Card Credentials Successfully Saved"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #28a745;">✓ Credentials Saved Successfully</h2>
                    <p>Hello {user_name},</p>
                    <p>Your time card credentials have been successfully saved and encrypted.</p>
                    <p>Your account is now set up and ready for automated time card sign-off.</p>
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>What's next?</strong></p>
                        <ul style="margin: 10px 0 0 20px;">
                            <li>Your credentials are securely encrypted and stored</li>
                            <li>Automated time card sign-off will begin on the next scheduled run</li>
                            <li>You'll receive email notifications for each sign-off attempt</li>
                        </ul>
                    </div>
                    {f'<hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;"><p style="margin-top: 20px; color: #666; font-size: 0.85em;"><a href="{deletion_link}" style="color: #dc3545; text-decoration: none;">Delete my account</a> - If you no longer wish to use this service, you can permanently delete your account using this link.</p>' if deletion_link else ''}
                </div>
            </body>
            </html>
            """
            
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [email],
                "subject": subject,
                "html": html_content
            }
            
            email_result = resend.Emails.send(params)
            email_id = email_result.get("id", "unknown")
            logger.info(f"Credentials confirmation email sent successfully to {email}. Email ID: {email_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending credentials confirmation email to {email}: {e}")
            return False

    def send_admin_alert(self, subject: str, message: str, error_details: Optional[str] = None) -> bool:
        """
        Send an alert email to the admin when critical errors occur.
        Uses Mailtrap for admin emails.
        
        Args:
            subject: The subject line of the alert email
            message: The main message/description of the issue
            error_details: Optional detailed error information (traceback, etc.)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not MAILTRAP_AVAILABLE:
                logger.warning("Mailtrap package not available. Admin alerts will not be sent.")
                return False
            
            email_config = get_email_config()
            admin_email = email_config.get("admin_email")
            mailtrap_token = email_config.get("mailtrap_token")
            
            if not admin_email:
                logger.warning("ADMIN_EMAIL not configured. Admin alerts will not be sent.")
                return False
            
            if not mailtrap_token:
                logger.warning("MAILTRAP_API_TOKEN not configured. Admin alerts will not be sent.")
                return False
            
            # Build HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #dc3545;">⚠️ Admin Alert: {subject}</h2>
                    <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                        <p style="margin: 0;"><strong>Message:</strong></p>
                        <p style="margin: 10px 0 0 0;">{message}</p>
                    </div>
            """
            
            if error_details:
                html_content += f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>Error Details:</strong></p>
                        <pre style="background-color: #ffffff; padding: 10px; border: 1px solid #ddd; border-radius: 3px; overflow-x: auto; font-size: 0.85em; white-space: pre-wrap; word-wrap: break-word;">{error_details}</pre>
                    </div>
                """
            
            html_content += """
                    <p style="color: #666; font-size: 0.9em; margin-top: 30px;">
                        This is an automated alert from the Time Card Sign-Off system.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Build plain text version for Mailtrap
            text_content = f"Admin Alert: {subject}\n\nMessage:\n{message}\n"
            if error_details:
                text_content += f"\nError Details:\n{error_details}\n"
            text_content += "\nThis is an automated alert from the Time Card Sign-Off system."
            
            # Get Mailtrap configuration
            mailtrap_from_email = email_config.get("mailtrap_from_email", "hello@demomailtrap.co")
            mailtrap_from_name = email_config.get("mailtrap_from_name", "Time Card Automation")
            
            # Create Mailtrap mail object
            mail = mt.Mail(
                sender=mt.Address(email=mailtrap_from_email, name=mailtrap_from_name),
                to=[mt.Address(email=admin_email)],
                subject=f"[ALERT] {subject}",
                text=text_content,
                html=html_content,
                category="Admin Alert"
            )
            
            # Send via Mailtrap
            client = mt.MailtrapClient(token=mailtrap_token)
            response = client.send(mail)
            
            logger.info(f"Admin alert email sent successfully to {admin_email} via Mailtrap. Response: {response}")
            return True
        except Exception as e:
            logger.error(f"Error sending admin alert email via Mailtrap: {e}")
            return False

