"""
Page Object Model for API Healthcare Sign-Off Confirmation Page.
Encapsulates all interactions with the sign-off confirmation window.
"""
from playwright.sync_api import Page, Locator
from pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)


class SignOffConfirmationPage(BasePage):
    """Represents the sign-off confirmation window/page."""

    def __init__(self, page: Page):
        super().__init__(page)

    def wait_for_confirmation_load(self) -> None:
        """Wait for the confirmation page/window to load completely."""
        # Wait for confirmation button - this is the reliable check
        self.wait_for_element(self.approve_button)

    @property
    def approve_button(self) -> Locator:
        """Get the approve/confirm button."""
        # Primary selector: ID of the actual button (most reliable)
        return self.page.locator("#formContentPlaceHolder_signoffButton").first
        # .or_(
        #     # Fallback: input with exact value "I approve" (not "I do NOT approve")
        #     self.page.locator("input[type='submit'][value='I approve']")
        # ).or_(
        #     # Additional fallbacks - using exact matches to avoid "I do NOT approve"
        #     self.page.get_by_role("button", name="I approve")
        # ).or_(
        #     self.page.get_by_role("button", name="Confirm")
        # ).or_(
        #     self.page.get_by_role("button", name="Yes")
        # ).first

    @property
    def confirm_button(self) -> Locator:
        """Alias for approve_button for backward compatibility."""
        return self.approve_button

    @property
    def cancel_button(self) -> Locator:
        """Get the cancel button."""
        # Primary selector: ID of the actual button
        return self.page.locator("#formContentPlaceHolder_cancelButton").first
        # .or_(
        #     # Fallback: input with value "Cancel"
        #     self.page.locator("input[type='submit'][value='Cancel']")
        # ).or_(
        #     # Additional fallbacks
        #     self.page.get_by_role("button", name="Cancel")
        # ).or_(
        #     self.page.get_by_role("button", name="No")
        # ).or_(
        #     self.page.locator("button:has-text('Cancel'), button:has-text('No')")
        # ).first

    def confirm_sign_off(self) -> None:
        """
        Click the approve button to complete sign-off.
        
        Note: After clicking, the confirmation window will close and return
        to the employee page. There is no confirmation message displayed.
        """
        try:
            logger.info("Confirming sign-off")
            self.wait_for_element(self.approve_button)
            self.approve_button.click()
            logger.info("Sign-off confirmed - window will close and return to employee page")
        except Exception as e:
            logger.error(f"Error confirming sign-off: {e}")
            self.take_screenshot("confirm_sign_off_error")
            raise

    def cancel_sign_off(self) -> None:
        """
        Click the cancel button to cancel sign-off.
        
        Note: After clicking, the confirmation window will close and return
        to the employee page. There is no confirmation message displayed.
        """
        try:
            logger.info("Cancelling sign-off")
            self.cancel_button.wait_for(state="visible", timeout=10000)
            self.cancel_button.click()
            logger.info("Cancel button clicked - window will close and return to employee page")
            
            # Try to wait a moment, but the window may close immediately
            # If the window closes, this will fail, which is expected
            try:
                self.wait_for_idle()
            except Exception as e:
                # Window closed - this is expected behavior after cancel
                if "closed" in str(e).lower() or "TargetClosedError" in str(type(e).__name__):
                    logger.debug("Confirmation window closed after cancel (expected)")
                else:
                    # Some other error occurred
                    raise
            
        except Exception as e:
            # Check if the error is because the page closed (expected behavior)
            if "closed" in str(e).lower() or "TargetClosedError" in str(type(e).__name__):
                logger.info("Sign-off cancelled - window closed (expected behavior)")
            else:
                logger.error(f"Error cancelling sign-off: {e}")
                raise


