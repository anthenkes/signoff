"""
Email service for sending sign-off results using Resend API.
"""
import logging
from typing import List, Optional
from models import SignOffResult, User
from mail.config import get_email_config

logger = logging.getLogger(__name__)

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend package not available. Email functionality will be disabled.")


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

    def send_signoff_result(self, result: SignOffResult) -> bool:
        """
        Send email to user with their sign-off result.
        
        Args:
            result: The SignOffResult object containing sign-off information
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if result.success:
                subject, html_content = self.format_success_email(result)
            else:
                subject, html_content = self.format_error_email(result)
            
            params: resend.Emails.SendParams = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [result.user.email],
                "subject": subject,
                "html": html_content
            }
            email = resend.Emails.send(params)
            
            # Resend returns a TypedDict, so access id as a dictionary key
            email_id = email.get("id", "unknown")
            logger.info(f"Email sent successfully to {result.user.email}. Email ID: {email_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending email to {result.user.email}: {e}")
            return False

    def format_success_email(self, result: SignOffResult) -> tuple[str, str]:
        """
        Format email template for successful sign-off.
        
        Args:
            result: The SignOffResult object
        
        Returns:
            Tuple of (subject, html_content)
        """
        user_name = result.user.name or result.user.username
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
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
            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                This is an automated message from the Time Card Sign-Off system.
            </p>
        </body>
        </html>
        """
        
        return subject, html_content

    def format_error_email(self, result: SignOffResult) -> tuple[str, str]:
        """
        Format email template for failed sign-off.
        
        Args:
            result: The SignOffResult object
        
        Returns:
            Tuple of (subject, html_content)
        """
        user_name = result.user.name or result.user.username
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
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
            <p style="margin-top: 30px; color: #666; font-size: 0.9em;">
                This is an automated message from the Time Card Sign-Off system.
            </p>
        </body>
        </html>
        """
        
        return subject, html_content

    def format_multi_user_report(self, results: List[SignOffResult]) -> tuple[str, str]:
        """
        Format email template for summary report of multiple users.
        
        Args:
            results: List of SignOffResult objects
        
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

