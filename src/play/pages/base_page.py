"""
Page object model for the API Base Page.
Encapsulates all the interactions we will do with the base page
"""

import time
from playwright.sync_api import Page, Locator, BrowserContext
from typing import Optional, Callable, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BasePage:
    """Represents the Base page"""

    def __init__(self, page: Page) -> None:
        self.page = page

    def take_screenshot(self, filename: Optional[str] = None, full_page: bool = False) -> str:
        """
        Take a screenshot of the current page.
        
        Args:
            filename: Optional filename for the screenshot. If not provided, generates a timestamped name.
            full_page: If True, captures the full scrollable page
        
        Returns:
            Path to the saved screenshot
        """
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        
        # Ensure filename has .png extension
        if not filename.endswith('.png'):
            filename = f"{filename}.png"
        
        # Create screenshots directory if it doesn't exist
        screenshot_dir = Path("screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        
        screenshot_path = screenshot_dir / filename
        self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        logger.info(f"Screenshot saved to {screenshot_path}")
        return str(screenshot_path)

    def handle_alert(self, accept: bool = True, prompt_text: Optional[str] = None) -> Optional[str]:
        """
        Handle browser alert, confirm, or prompt dialog.
        
        Args:
            accept: If True, accept the dialog; if False, dismiss it
            prompt_text: Text to enter in prompt dialogs
        
        Returns:
            The message text from the dialog, or None
        """
        try:
            with self.page.expect_dialog() as dialog_info:
                dialog = dialog_info.value
                message = dialog.message
                
                if prompt_text:
                    dialog.accept(prompt_text=prompt_text)
                elif accept:
                    dialog.accept()
                else:
                    dialog.dismiss()
                
                return message
        except Exception as e:
            logger.error(f"Error handling alert: {e}")
            return None

    def is_element_visible(
            self, 
            locator_or_getter: Union[Locator, Callable[[], Locator]], 
            timeout: int = 5000
        ) -> bool:
        """
        Check if an element is visible on the page (Non-blocking check).
        
        Args:
            locator_or_getter: eiter a Locator or a calllable that returns a Locator
            timeout: Maximum time to wait in milliseconds
        
        Returns:
            True if element is visible, False otherwise
        """
        try:
            self.wait_for_element(locator_or_getter, state='visible', timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_new_window(self, timeout: int = 30000) -> Page:
        """
        Wait for a new window/tab to open and return its Page object.
        
        Args:
            timeout: Maximum time to wait in milliseconds
        
        Returns:
            The new Page object
        
        Raises:
            TimeoutError: If no new window opens within the timeout
        """
        with self.page.context.expect_page(timeout=timeout) as new_page_info:
            new_page = new_page_info.value
            new_page.wait_for_load_state("load")
            return new_page

    def wait_for_element(
        self, 
        locator_or_getter: Union[Locator, Callable[[], Locator]], 
        state: str = "visible", 
        timeout: int = 10000
    ) -> Locator:
        """
        Wait for an element to reach a specific state.
        
        This is the recommended way to wait for page readiness - wait for specific
        elements rather than using load states like 'networkidle'.
        
        Args:
            locator_or_getter: Either a Locator or a callable (e.g., property) that returns a Locator
            state: The state to wait for - "visible", "attached", "detached", "hidden" (default: "visible")
            timeout: Maximum time to wait in milliseconds (default: 10000)
        
        Returns:
            The Locator that was waited for (useful for chaining)
        
        Raises:
            TimeoutError: If element doesn't reach the state within timeout
        
        Example:
            # Wait for a property
            self.wait_for_element(self.username_input)
            
            # Wait for a dynamically created locator
            self.wait_for_element(lambda: self.page.get_by_text("Loading..."))
            
            # Wait for detached state
            self.wait_for_element(self.loading_spinner, state="detached")
        """
        if callable(locator_or_getter):
            locator = locator_or_getter()
        else:
            locator = locator_or_getter
        
        locator.wait_for(state=state, timeout=timeout)
        return locator

    def wait_for_idle(self, timeout: int = 1000) -> None:
        """
        Wait a short moment for any immediate actions to complete.
        
        This is a simple timeout to allow any immediate UI updates or
        navigation to start after an action. Does not wait for network idle.
        
        Args:
            timeout: Time to wait in milliseconds (default: 1000)
        """
        self.page.wait_for_timeout(timeout)

