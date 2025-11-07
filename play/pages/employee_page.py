"""
Page Object Model for API Healthcare Employee Page.
Encapsulates all interactions with the employee page.
"""
from playwright.sync_api._generated import Locator


from playwright.sync_api import Page, Locator, FrameLocator
from pages.base_page import BasePage
import logging
import json
import time

logger = logging.getLogger(__name__)


class EmployeePage(BasePage):
    """Represents the Employee page."""

    def __init__(self, page: Page):
        super().__init__(page)
        self._employee_actions_frame_locator = None

    def _get_employee_actions_frame_locator(self) -> FrameLocator:
        """
        Get the Employee Actions iframe frame locator.
        
        The button is inside an iframe, so we need to access it through the frame locator.
        Using FrameLocator is the recommended approach in Playwright.
        
        Returns:
            The FrameLocator for the Employee Actions iframe
        """
        if self._employee_actions_frame_locator is None:
            # Use attribute selector to handle space in ID: "Employee Actions_iframe"
            iframe_selector = 'iframe[id="Employee Actions_iframe"]'
            
            # Wait for the iframe to be attached
            iframe_locator = self.page.locator(iframe_selector)
            iframe_locator.wait_for(state="attached", timeout=15000)
            logger.debug("Employee Actions iframe attached to DOM")
            
            # Create a frame locator - this is the recommended way to work with iframes
            self._employee_actions_frame_locator = self.page.frame_locator(iframe_selector)
            logger.debug("Employee Actions iframe frame locator obtained")
        
        return self._employee_actions_frame_locator

    def wait_for_employee_page_load(self) -> None:
        """
        Wait for the employee page to load completely.
        
        The button is inside an iframe (Employee Actions_iframe), so we wait for:
        1. The iframe to be attached
        2. The iframe content to load
        3. Either the Sign Off or Un-Sign Off button to appear (polling until one exists)
        
        Note: The button changes from "Employee Sign Off" to "Employee Un-Sign Off" 
        after the timecard is signed off.
        """
        logger.info("Waiting for employee page to load...")
        
        # Wait for the Employee Actions iframe to be attached
        iframe_locator = self.page.locator('iframe[id="Employee Actions_iframe"]')
        iframe_locator.wait_for(state="attached", timeout=15000)
        
        # Scroll iframe into view so its content is accessible
        iframe_locator.scroll_into_view_if_needed(timeout=5000)
        
        # Wait for iframe content to load
        frame_locator = self._get_employee_actions_frame_locator()
        frame_locator.locator("body").wait_for(state="attached", timeout=10000)
        
        # Wait for either button to appear (Sign Off or Un-Sign Off)
        # The button changes after sign-off
        sign_off_button = frame_locator.locator("#formContentPlaceHolder_employeeSignoffApiButton")
        unsign_off_button = frame_locator.locator("#formContentPlaceHolder_employeeUnsignOffApiButton")
        timeout = 20  # seconds
        start_time = time.time()
        while time.time() - start_time < timeout:
            sign_off_count = sign_off_button.count()
            unsign_off_count = unsign_off_button.count()
            if sign_off_count > 0 or unsign_off_count > 0:
                break
            self.page.wait_for_timeout(500)  # Wait 500ms before checking again
        else:
            logger.error("Employee Sign Off/Un-Sign Off button not found in iframe after timeout")
            self.take_screenshot("employee_page_load_button_not_found")
            raise Exception("Employee Sign Off/Un-Sign Off button not found in iframe")
        
        # Scroll the found button into view if needed
        if sign_off_button.count() > 0:
            sign_off_button.first.scroll_into_view_if_needed(timeout=5000)
        else:
            unsign_off_button.first.scroll_into_view_if_needed(timeout=5000)
        logger.info("Employee page loaded successfully")

    @property
    def employee_sign_off_button(self) -> Locator:
        """
        Get the 'Employee Sign Off' button.
        
        The button is inside the Employee Actions iframe, so we need to access it
        through the frame locator.
        
        The button text contains &nbsp; entities, so we use the ID selector which is most reliable.
        """
        # Get the iframe frame locator and locate the button within it
        frame_locator = self._get_employee_actions_frame_locator()
        # Use the ID selector directly - it's the most reliable
        # The button ID is: formContentPlaceHolder_employeeSignoffApiButton
        return frame_locator.locator("#formContentPlaceHolder_employeeSignoffApiButton")

    def is_sign_off_button_visible(self) -> bool:
        """Check if the Employee sign Off button is visible."""
        return self.is_element_visible(self.employee_sign_off_button, timeout=5000)

    def click_employee_sign_off(self) -> Page:
        """
        Click the 'Employee sign Off' button and wait for new window to open.
        
        Returns:
            The new Page object for the confirmation window
        """
        try:
            logger.info("Clicking Employee sign Off button")
            
            # Wait for button to be visible and clickable
            self.wait_for_element(self.employee_sign_off_button, state="visible")
            self.wait_for_element(self.employee_sign_off_button, state="attached")
            
            # Click the button and wait for new window
            with self.page.context.expect_page(timeout=30000) as new_page_info:
                self.employee_sign_off_button.click()
            
            new_page = new_page_info.value
            # Wait for basic DOM readiness
            new_page.wait_for_load_state("load")
            # Note: The confirmation page object will wait for specific elements
            # via wait_for_confirmation_load()
            
            logger.info("New window opened for sign-off confirmation")
            return new_page
        except Exception as e:
            logger.error(f"Error clicking Employee sign Off button: {e}")
            self.take_screenshot("employee_sign_off_error")
            raise

    @property
    def calculator_icon(self) -> Locator:
        """
        Get the calculator icon locator.
        
        The calculator icon is located in the Employee Navigator_iframe.
        This property provides access to the icon for testing purposes.
        Returns the first matching icon (use .first if you need a single element).
        """
        # Access the iframe and locate the calculator icon
        frame_locator = self.page.frame_locator('iframe[id="Employee Navigator_iframe"]')
        # Note: class is icon-ico_calculator1_sm (with dash, not underscore)
        return frame_locator.locator('i.icon-ico_calculator1_sm[title*="Last calculated"]')

    # THIS IS A TEST OF THE SCREENSHOT CAPABILITY
    def capture_calculator_tooltip(self) -> str:
        """ 
        Hover over the calc icon and take a screenshot. Returns the str of the screenshot.
        
        The calculator icon is typically found in the Employee Navigator_iframe.
        """
        found_in_frame = None
        
        # Try to get the calculator icon using the property
        try:
            icon_locator = self.calculator_icon
            if icon_locator.count() > 0:
                calc_icon = icon_locator.first
                found_in_frame = "Employee Navigator_iframe"
                logger.info(f"Found calculator icon in iframe: {found_in_frame}")
            else:
                # Try without title filter as fallback
                frame_locator = self.page.frame_locator('iframe[id="Employee Navigator_iframe"]')
                icon_locator = frame_locator.locator('i.icon-ico_calculator1_sm')
                if icon_locator.count() > 0:
                    calc_icon = icon_locator.first
                    found_in_frame = "Employee Navigator_iframe"
                    logger.info(f"Found calculator icon in iframe (without title filter): {found_in_frame}")
                else:
                    calc_icon = None
        except Exception as e:
            logger.debug(f"Error getting calculator icon: {e}")
            calc_icon = None
        
        # Fallback: If not found in iframe, try main page
        if calc_icon is None:
            logger.debug("Looking for calculator icon on main page...")
            try:
                calc_icon = self.page.locator('i.icon-ico_calculator1_sm[title*="Last calculated"]').first
                if calc_icon.count() == 0:
                    calc_icon = self.page.locator('i.icon-ico_calculator1_sm').first
            except:
                calc_icon = None
        
        # Check if we found the icon
        if calc_icon is None:
            logger.warning("Calculator icon not found")
            logger.info("Taking screenshot of current page state instead")
            return self.take_screenshot("calc_tooltip_not_found")
        
        # If icon is in an iframe, make sure the iframe is in view BEFORE hovering
        # (scrolling after hover would move the mouse and hide the tooltip)
        if found_in_frame:
            try:
                iframe_element = self.page.locator(f'iframe[id="{found_in_frame}"]')
                iframe_element.scroll_into_view_if_needed(timeout=5000)
                logger.debug(f"Scrolled iframe {found_in_frame} into view")
                # Small delay to let iframe settle after scrolling
                self.page.wait_for_timeout(200)
            except Exception as e:
                logger.debug(f"Could not scroll iframe into view: {e}")
        
        # Wait for icon to be visible and attached
        try:
            calc_icon.first.wait_for(state="attached", timeout=5000)
            if not calc_icon.first.is_visible(timeout=5000):
                logger.warning("Calculator icon found but not visible")
                # Try scrolling it into view
                calc_icon.first.scroll_into_view_if_needed(timeout=5000)
        except Exception as e:
            logger.warning(f"Error waiting for calculator icon: {e}")
            return self.take_screenshot("calc_tooltip_wait_error")
        
        # Get the tooltip text from the title attribute BEFORE hovering
        # Native browser tooltips (from title) are OS-level overlays and won't be captured in screenshots
        # We'll create a visible DOM tooltip element instead
        tooltip_text = None
        try:
            tooltip_text = calc_icon.first.get_attribute("title")
            if tooltip_text:
                logger.info(f"Found tooltip text: {tooltip_text}")
            else:
                logger.warning("No title attribute found on calculator icon")
        except Exception as e:
            logger.warning(f"Could not get tooltip text: {e}")
        
        # Get the bounding box of the icon to position the tooltip
        icon_bbox = None
        try:
            icon_bbox = calc_icon.first.bounding_box()
            if icon_bbox:
                logger.debug(f"Icon bounding box: {icon_bbox}")
        except Exception as e:
            logger.warning(f"Could not get icon bounding box: {e}")
        
        # Hover over the icon to trigger any hover STATES (ie underlined text)
        # Will not need for the blue thumbs up icon, as it will not have any hover states
        try:
            logger.info("Hovering over calculator icon...")
            # Make sure icon is in view before hovering
            calc_icon.first.scroll_into_view_if_needed(timeout=5000)
            calc_icon.first.hover(timeout=10000)
            logger.debug("Hover successful")
        except Exception as e:
            logger.warning(f"Error hovering over calculator icon: {e}")
            # Take screenshot anyway
            return self.take_screenshot("calc_tooltip_hover_error")
        
        # Create a visible DOM tooltip element since native tooltips won't appear in screenshots
        # Based on: https://github.com/microsoft/playwright/issues/12077
        tooltip_id = "playwright_custom_tooltip"
        if tooltip_text and icon_bbox:
            try:
                # Calculate tooltip position using the icon's bounding box directly
                # Playwright's bounding_box() returns absolute viewport coordinates
                # Native tooltips typically appear to the right and slightly below the icon
                tooltip_x = icon_bbox['x'] + icon_bbox['width']
                tooltip_y = icon_bbox['y'] + icon_bbox['height'] / 2
                
                # Create tooltip element in the DOM
                # Match native browser tooltip styling more closely
                # Use json.dumps to safely escape the tooltip text for JavaScript
                escaped_text = json.dumps(tooltip_text)
                
                # Native tooltips typically appear to the right and slightly below the icon
                # Add small offset to match native positioning
                tooltip_offset_x = 1   # Small gap from icon
                tooltip_offset_y = -1  # Slight vertical offset to align with icon center
                
                create_tooltip_js = f"""
                (function() {{
                    // Remove existing tooltip if any
                    const existing = document.getElementById('{tooltip_id}');
                    if (existing) existing.remove();
                    
                    // Create tooltip element
                    const tooltip = document.createElement('div');
                    tooltip.id = '{tooltip_id}';
                    tooltip.textContent = {escaped_text};
                    // Match native browser tooltip styling more closely
                    tooltip.style.cssText = `
                        position: absolute;
                        left: {tooltip_x + tooltip_offset_x}px;
                        top: {tooltip_y + tooltip_offset_y}px;
                        background-color: #ffffe1;
                        border: 1px solid #737373;
                        border-radius: 2px;
                        padding: 3px 6px;
                        font-size: 11px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                        color: #000;
                        z-index: 999999;
                        pointer-events: none;
                        white-space: pre-line;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        max-width: 300px;
                        line-height: 1.4;
                    `;
                    document.body.appendChild(tooltip);
                }})();
                """
                
                self.page.evaluate(create_tooltip_js)
                logger.info("Created custom DOM tooltip (native tooltips won't appear in screenshots)")
                
                # Small delay to ensure tooltip is rendered
                self.page.wait_for_timeout(100)
                
            except Exception as e:
                logger.warning(f"Could not create custom tooltip: {e}")
                import traceback
                traceback.print_exc()
        
        # Take screenshot using page.screenshot() directly to preserve hover state
        # Based on the GitHub issue, page.screenshot() preserves hover better than locator.screenshot()
        logger.info("Taking screenshot of calculator tooltip...")
        screenshot_path = self.take_screenshot("calc_tooltip", full_page=True)
        
        # Clean up: Remove the custom tooltip
        try:
            remove_tooltip_js = f"""
            (function() {{
                const tooltip = document.getElementById('{tooltip_id}');
                if (tooltip) tooltip.remove();
            }})();
            """
            self.page.evaluate(remove_tooltip_js)
            logger.debug("Removed custom tooltip from DOM")
        except Exception as e:
            logger.debug(f"Could not remove tooltip: {e}")
        
        return screenshot_path

    # The dreaded blue check mark
    @property
    def blue_thumbs_up_icon(self) -> Locator:
        """
        Get the blue thumbs up icon locator.

        The blue check is located in the Employee Navigator_iframe.
        This icon appears after the employee has signed off on their timecard.

        Returns the first matching icon.
        """
        # Access the iframe and locate the blue check mark
        frame_locator = self.page.frame_locator('iframe[id="Employee Navigator_iframe"]')

        return frame_locator.locator('i.icon-ico_thumbsup_sm[title*="signed off on"]')

    def is_blue_thumbs_up(self) -> bool:
        """
        Check if the blue thumbs up icon is visible.
        
        This icon appears after the employee has signed off on their timecard.
        Returns True if the icon is visible, False otherwise.
        """
        return self.is_element_visible(self.blue_thumbs_up_icon, timeout=5000)

    def capture_blue_thumbs_up_tooltip(self) -> str:
        """
        Hover over the blue thumbs up and take a screenshot. Returns the str of the screenie.
        """
        found_in_frame = None

        # Try to get the blue thumbs up icon using the property
        try:
            icon_locator = self.blue_thumbs_up_icon
            if icon_locator.count() > 0:
                thumbs_up_icon = icon_locator.first
                found_in_frame = "Employee Navigator_iframe"
                logger.info(f"Found blue thumbs up icon in iframe: {found_in_frame}")
            else:
                # Try without title filter as fallback
                logger.info("Trying to find blue thumbs up icon without title filter...")
                frame_locator = self.page.frame_locator('iframe[id="Employee Navigator_iframe"]')
                icon_locator = frame_locator.locator('i.icon-ico_thumbsup_sm')
                if icon_locator.count() > 0:
                    thumbs_up_icon = icon_locator.first
                    found_in_frame = "Employee Navigator_iframe"
                    logger.info(f"Found blue thumbs up icon in iframe (without title filter): {found_in_frame}")
                else:
                    thumbs_up_icon = None
        except Exception as e:
                logger.warning(f"Error finding blue thumbs up icon: {e}")
                thumbs_up_icon = None
        
        # Check if we found the icon
        if thumbs_up_icon is None:
            logger.warning("Blue thumbs up icon not found")
            logger.info("Taking screenshot of current page state instead")
            return self.take_screenshot("blue_thumbs_up_not_found")
        
        # If icon is in an iframe, make sure the iframe is in view BEFORE hovering
        # (scrolling after hover would move the mouse and hide the tooltip)
        if found_in_frame:
            try:
                iframe_element = self.page.locator(f'iframe[id="{found_in_frame}"]')
                iframe_element.scroll_into_view_if_needed(timeout=5000)
                logger.debug(f"Scrolled iframe {found_in_frame} into view")
                # Small delay to let iframe settle after scrolling
                self.page.wait_for_timeout(200)
            except Exception as e:
                logger.debug(f"Could not scroll iframe into view: {e}")
        
        # Wait for icon to be visible and attached
        try:
            thumbs_up_icon.first.wait_for(state="attached", timeout=5000)
            if not thumbs_up_icon.first.is_visible(timeout=5000):
                logger.warning("Blue thumbs up icon found but not visible")
                # Try scrolling it into view
                thumbs_up_icon.first.scroll_into_view_if_needed(timeout=5000)
        except Exception as e:
            logger.warning(f"Error waiting for blue thumbs up icon: {e}")
            return self.take_screenshot("blue_thumbs_up_wait_error")
        
        # Get the tooltip text from the title attribute BEFORE hovering
        # Native browser tooltips (from title) are OS-level overlays and won't be captured in screenshots
        # We'll create a visible DOM tooltip element instead
        tooltip_text = None
        try:
            tooltip_text = thumbs_up_icon.first.get_attribute("title")
            if tooltip_text:
                logger.info(f"Found tooltip text: {tooltip_text}")
            else:
                logger.warning("No title attribute found on blue thumbs up icon")
        except Exception as e:
            logger.warning(f"Could not get tooltip text: {e}")
        
        # Get the bounding box of the icon to position the tooltip
        icon_bbox = None
        try:
            icon_bbox = thumbs_up_icon.first.bounding_box()
            if icon_bbox:
                logger.debug(f"Icon bounding box: {icon_bbox}")
        except Exception as e:
            logger.warning(f"Could not get icon bounding box: {e}")
            # Take screenshot anyway
            return self.take_screenshot("blue_thumbs_up_tooltip_text_error")
        


        # Create a visible DOM tooltip element since native tooltips won't appear in screenshots
        # Based on: https://github.com/microsoft/playwright/issues/12077
        tooltip_id = "playwright_custom_tooltip"
        if tooltip_text and icon_bbox:
            try:
                # Calculate tooltip position using the icon's bounding box directly
                # Playwright's bounding_box() returns absolute viewport coordinates
                # Native tooltips typically appear to the right and slightly below the icon
                tooltip_x = icon_bbox['x'] + icon_bbox['width']
                tooltip_y = icon_bbox['y'] + icon_bbox['height'] / 2
                
                # Create tooltip element in the DOM
                # Match native browser tooltip styling more closely
                # Use json.dumps to safely escape the tooltip text for JavaScript
                escaped_text = json.dumps(tooltip_text)
                
                # Native tooltips typically appear to the right and slightly below the icon
                # Add small offset to match native positioning
                tooltip_offset_x = 1   # Small gap from icon
                tooltip_offset_y = -1  # Slight vertical offset to align with icon center
                
                create_tooltip_js = f"""
                (function() {{
                    // Remove existing tooltip if any
                    const existing = document.getElementById('{tooltip_id}');
                    if (existing) existing.remove();
                    
                    // Create tooltip container
                    const tooltip = document.createElement('div');
                    tooltip.id = '{tooltip_id}';
                    tooltip.textContent = {escaped_text};
                    // Match the native tooltip styling from the screenshot
                    tooltip.style.cssText = `
                        position: absolute;
                        left: {tooltip_x + tooltip_offset_x}px;
                        top: {tooltip_y + tooltip_offset_y}px;
                        background-color: #333333;
                        border: none;
                        border-radius: 4px;
                        padding: 6px 10px;
                        font-size: 11px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                        color: #ffffff;
                        z-index: 999999;
                        pointer-events: none;
                        white-space: nowrap;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                        line-height: 1.4;
                    `;
                    document.body.appendChild(tooltip);
                }})();
                """
                
                self.page.evaluate(create_tooltip_js)
                logger.info("Created custom DOM tooltip (native tooltips won't appear in screenshots)")
                
                # Small delay to ensure tooltip is rendered
                self.page.wait_for_timeout(100)
            except Exception as e:
                logger.warning(f"Could not create custom tooltip: {e}")
                import traceback
                traceback.print_exc()
        
        # Take screenshot using page.screenshot() directly to preserve hover state
        # Based on the GitHub issue, page.screenshot() preserves hover better than locator.screenshot()
        logger.info("Taking screenshot of blue thumbs up icon...")
        screenshot_path = self.take_screenshot("blue_thumbs_up", full_page=True)
        
        # Clean up: Remove the custom tooltip
        try:
            remove_tooltip_js = f"""
            (function() {{
                const tooltip = document.getElementById('{tooltip_id}');
                if (tooltip) tooltip.remove();
            }})();
            """
            self.page.evaluate(remove_tooltip_js)
            logger.debug("Removed custom tooltip from DOM")
        except Exception as e:
            logger.debug(f"Could not remove tooltip: {e}")
        
        return screenshot_path