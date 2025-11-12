"""
Page Object Model for API Healthcare Dashboard Page.
Encapsulates all interactions with the dashboard page.
"""
from playwright.sync_api import Page, Locator
from play.pages.base_page import BasePage
import logging

logger = logging.getLogger(__name__)


class DashboardPage(BasePage):
    """Represents the Dashboard page after login."""

    def __init__(self, page: Page):
        super().__init__(page)
        self._base_url = None

    def wait_for_dashboard_load(self) -> None:
        """Wait for the dashboard to load completely."""
        # Wait for navigation bar - this is the reliable check
        self.wait_for_element(self.nav_bar)

    @property
    def nav_bar(self) -> Locator:
        """Get the navigation bar element."""
        # PrimeNG menubar with id navBar
        return self.page.locator("#navBar, .primary-navbar").first

    @property
    def home_tab(self) -> Locator:
        """Get the Home tab in the navigation bar."""
        # PrimeNG menu item: a[role="menuitem"] containing span with text "Home"
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Home'))").first

    @property
    def employee_tab(self) -> Locator:
        """Get the Employee tab in the navigation bar."""
        # PrimeNG menu item: a[role="menuitem"] containing span with text "Employee"
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Employee'))").first

    @property
    def configuration_tab(self) -> Locator:
        """Get the Configuration tab in the navigation bar."""
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Configuration'))").first

    @property
    def reports_tab(self) -> Locator:
        """Get the Reports tab in the navigation bar."""
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Reports'))").first

    @property
    def actions_tab(self) -> Locator:
        """Get the Actions tab in the navigation bar."""
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Actions'))").first

    @property
    def preferences_tab(self) -> Locator:
        """Get the Preferences tab in the navigation bar."""
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Preferences'))").first

    @property
    def help_tab(self) -> Locator:
        """Get the Help tab in the navigation bar."""
        return self.page.locator("#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('Help'))").first

    def is_on_home_tab(self) -> bool:
        """Check if currently on the Home tab."""
        try:
            # Check if Home tab's parent li has active-menu class (p-menuitem.active-menu)
            home_tab_li = self.page.locator("#navBar li.p-menuitem.active-menu:has(a:has(span.p-menuitem-text:has-text('Home')))").first
            # Check if the element exists and is visible
            return home_tab_li.is_visible(timeout=1000)
        except Exception:
            return False

    def navigate_to_employee(self) -> None:
        """
        Navigate to the Employee tab in the navigation bar.
        
        The tab starts with 'p-menuitem.inactive-menu' and transitions to 'p-menuitem.active-menu' when clicked.
        """
        try:
            # Check if already active
            if self.is_tab_active("Employee"):
                logger.info("Employee tab is already active")
                return
            
            logger.info("Navigating to Employee tab")
            # Verify the tab exists and is clickable (should be inactive-menu initially)
            employee_inactive = self.page.locator("#navBar li.p-menuitem.inactive-menu:has(a:has(span.p-menuitem-text:has-text('Employee')))").first
            if not employee_inactive.is_visible(timeout=5000):
                logger.warning("Employee tab not found in inactive state, proceeding anyway")
            
            self.employee_tab.click()
            
            # Wait for the Employee tab to transition from inactive-menu to active-menu
            # This indicates navigation has completed
            employee_tab_li = self.page.locator("#navBar li.p-menuitem.active-menu:has(a:has(span.p-menuitem-text:has-text('Employee')))")
            self.wait_for_element(employee_tab_li, timeout=30000)
            logger.info("Successfully navigated to Employee page")
        except Exception as e:
            logger.error(f"Error navigating to Employee tab: {e}")
            raise

    def navigate_to_tab(self, tab_name: str) -> None:
        """
        Navigate to a specific tab in the navigation bar.
        
        The tab starts with 'p-menuitem.inactive-menu' and transitions to 'p-menuitem.active-menu' when clicked.
        
        Args:
            tab_name: Name of the tab (Home, Employee, Configuration, Reports, Actions, Preferences, Help)
        """
        try:
            # Check if already active
            if self.is_tab_active(tab_name):
                logger.info(f"{tab_name} tab is already active")
                return
            
            logger.info(f"Navigating to {tab_name} tab")
            # Verify the tab exists and is clickable (should be inactive-menu initially)
            tab_inactive = self.page.locator(
                f"#navBar li.p-menuitem.inactive-menu:has(a:has(span.p-menuitem-text:has-text('{tab_name}')))"
            ).first
            if not tab_inactive.is_visible(timeout=5000):
                logger.warning(f"{tab_name} tab not found in inactive state, proceeding anyway")
            
            tab_locator = self.page.locator(
                f"#navBar a[role='menuitem']:has(span.p-menuitem-text:has-text('{tab_name}'))"
            ).first
            tab_locator.click()
            
            # Wait for the tab to transition from inactive-menu to active-menu
            # This indicates navigation has completed
            tab_li = self.page.locator(
                f"#navBar li.p-menuitem.active-menu:has(a:has(span.p-menuitem-text:has-text('{tab_name}')))"
            )
            self.wait_for_element(tab_li, timeout=30000)
            logger.info(f"Successfully navigated to {tab_name} page")
        except Exception as e:
            logger.error(f"Error navigating to {tab_name} tab: {e}")
            raise

    def is_tab_active(self, tab_name: str) -> bool:
        """
        Check if a specific tab is currently active.
        
        Active tabs have the class 'p-menuitem.active-menu', inactive tabs have 'p-menuitem.inactive-menu'.
        
        Args:
            tab_name: Name of the tab to check
        
        Returns:
            True if the tab is active, False otherwise
        """
        try:
            # Check for li element with both p-menuitem and active-menu classes
            tab_li = self.page.locator(
                f"#navBar li.p-menuitem.active-menu:has(a:has(span.p-menuitem-text:has-text('{tab_name}')))"
            ).first
            # Check if the element exists and is visible
            return tab_li.is_visible(timeout=1000)
        except Exception:
            # If element not found or not visible, tab is not active
            return False

    def is_tab_inactive(self, tab_name: str) -> bool:
        """
        Check if a specific tab is currently inactive.
        
        Args:
            tab_name: Name of the tab to check
        
        Returns:
            True if the tab is inactive, False otherwise
        """
        try:
            # Check for li element with both p-menuitem and inactive-menu classes
            tab_li = self.page.locator(
                f"#navBar li.p-menuitem.inactive-menu:has(a:has(span.p-menuitem-text:has-text('{tab_name}')))"
            ).first
            # Check if the element exists and is visible
            return tab_li.is_visible(timeout=1000)
        except Exception:
            # If element not found or not visible, assume not inactive (could be transitioning)
            return False

    def get_active_tabs(self) -> list[str]:
        """
        Get a list of all currently active tab names.
        
        Active tabs have the class 'p-menuitem.active-menu'.
        
        Returns:
            List of active tab names
        """
        try:
            active_tabs = []
            # Find all menu items with both p-menuitem and active-menu classes
            active_items = self.page.locator("#navBar li.p-menuitem.active-menu").all()
            for item in active_items:
                try:
                    # Get the text from the span inside the menu item
                    text_span = item.locator("span.p-menuitem-text")
                    if text_span.is_visible():
                        tab_text = text_span.text_content()
                        if tab_text:
                            active_tabs.append(tab_text.strip())
                except Exception:
                    continue
            return active_tabs
        except Exception:
            return []

    def get_inactive_tabs(self) -> list[str]:
        """
        Get a list of all currently inactive tab names.
        
        Inactive tabs have the class 'p-menuitem.inactive-menu'.
        
        Returns:
            List of inactive tab names
        """
        try:
            inactive_tabs = []
            # Find all menu items with both p-menuitem and inactive-menu classes
            inactive_items = self.page.locator("#navBar li.p-menuitem.inactive-menu").all()
            for item in inactive_items:
                try:
                    # Get the text from the span inside the menu item
                    text_span = item.locator("span.p-menuitem-text")
                    if text_span.is_visible():
                        tab_text = text_span.text_content()
                        if tab_text:
                            inactive_tabs.append(tab_text.strip())
                except Exception:
                    continue
            return inactive_tabs
        except Exception:
            return []

