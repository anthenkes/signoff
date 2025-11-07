"""Page Object Model classes for Playwright tests."""

from pages.base_page import BasePage
from pages.login_page import LoginPage
from pages.dashboard_page import DashboardPage
from pages.employee_page import EmployeePage
from pages.signoff_confirmation_page import SignOffConfirmationPage

__all__ = [
    "BasePage",
    "LoginPage",
    "DashboardPage",
    "EmployeePage",
    "SignOffConfirmationPage",
]

