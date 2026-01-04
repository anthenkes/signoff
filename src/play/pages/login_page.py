"""
Page Object Model for API Healthcare Login Page.
Encapsulates all interactions with the login page.
"""
from playwright.sync_api import Page, Locator
from typing import Literal

from src.play.pages.base_page import BasePage


class LoginPage(BasePage):
    """Represents the API Healthcare login page."""
    
    # Domain options available on the login page
    Domain = Literal["LLU Network", "MC Network", "System Authentication"]
    
    def __init__(self, page: Page):
        self.page = page
        self._login_url = "/APIHC/TASS/WebPortal/APIHealthcare_LLCA419_Live_External/Login.aspx"
    
    def goto(self, base_url: str = None) -> None:
        """
        Navigate to the login page.
        
        Args:
            base_url: Optional base URL. If not provided, uses relative path.
        """
        if base_url:
            self.page.goto(f"{base_url}{self._login_url}")
        else:
            self.page.goto(self._login_url)
    
    @property
    def username_input(self) -> Locator:
        """Get the username input field."""
        # Use the id field name
        return self.page.locator("#formContentPlaceHolder_userNameField").first
    
    @property
    def password_input(self) -> Locator:
        """Get the password input field."""
        return self.page.locator("#formContentPlaceHolder_passwordField").first
    
    @property
    def domain_select(self) -> Locator:
        """Get the domain dropdown selector."""
        # Try common selectors for domain dropdown
        return self.page.locator("#formContentPlaceHolder_directoryField").first
    
    @property
    def sign_in_button(self) -> Locator:
        """Get the Sign In button."""
        return self.page.get_by_role("button", name="Sign In").or_(
            self.page.locator("#formContentPlaceHolder_loginApiButton")
        ).first
    
    def fill_username(self, username: str) -> None:
        """Fill in the username field."""
        self.username_input.fill(username)
    
    def fill_password(self, password: str) -> None:
        """Fill in the password field."""
        self.password_input.fill(password)
    
    def select_domain(self, domain: Domain) -> None:
        """
        Select a domain from the dropdown.
        
        Args:
            domain: One of "LLU Network", "MC Network", or "System Authentication"
        """
        self.domain_select.select_option(label=domain)
    
    def click_sign_in(self) -> None:
        """Click the Sign In button."""
        self.sign_in_button.click()
    
    def ensure_mc_network_domain(self) -> None:
        """Ensure the domain dropdown is set to 'MC Network'."""
        self.select_domain("MC Network")
    
    def login(self, username: str, password: str, domain: Domain = "MC Network") -> None:
        """
        Perform complete login flow.
        
        Args:
            username: Username to login with
            password: Password to login with
            domain: Domain to select (default: "MC Network")
        """
        self.fill_username(username)
        self.fill_password(password)
        self.select_domain(domain)
        self.click_sign_in()
    
    def wait_for_page_load(self) -> None:
        """Wait for the login page to load completely."""
        # Wait for username input to be attached to DOM (may have display:none initially)
        # Using "attached" state instead of "visible" since the element might be hidden
        self.wait_for_element(self.username_input, state="attached")
        # Also wait for sign in button to be attached to ensure form is fully loaded
        self.wait_for_element(self.sign_in_button, state="attached")
    
    def is_login_form_visible(self) -> bool:
        """Check if the login form is visible."""
        # Use is_element_visible from base class which properly waits for visibility
        # Check sign-in button as it should be visible when form is ready
        # (username/password may have display:none initially)
        return self.is_element_visible(self.sign_in_button, timeout=5000)

    @property
    def validation_summary(self) -> Locator:
        """
        Get the validation summary error element.
        
        Note: The validation summary is in the main page DOM, not in an iframe.
        This is different from the employee page where buttons are inside iframes.
        """
        return self.page.locator("#formContentPlaceHolder_validationSummary").first

    def has_login_error(self) -> bool:
        """
        Check if there is a login error displayed on the page.
        
        Returns True if the validation summary is visible and contains error text.
        """
        try:
            validation_summary = self.validation_summary
            # Check if the element exists and is visible
            if validation_summary.count() > 0:
                # Check if it's visible (not display:none)
                is_visible = validation_summary.is_visible(timeout=2000)
                if is_visible:
                    # Check if it contains error text
                    text = validation_summary.inner_text(timeout=1000)
                    if text and text.strip():
                        return True
            return False
        except Exception:
            # If we can't check, assume no error
            return False

    def get_login_error_message(self) -> str | None:
        """
        Get the login error message if one is displayed.
        
        Returns the error message text, or None if no error is displayed.
        """
        try:
            if self.has_login_error():
                text = self.validation_summary.inner_text(timeout=1000)
                return text.strip() if text else None
            return None
        except Exception:
            return None

