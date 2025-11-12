"""Page Object Model classes for Playwright tests."""

from .base_page import BasePage
from .login_page import LoginPage
from .dashboard_page import DashboardPage
from .employee_page import EmployeePage
from .signoff_confirmation_page import SignOffConfirmationPage

__all__ = [
    "BasePage",
    "LoginPage",
    "DashboardPage",
    "EmployeePage",
    "SignOffConfirmationPage",
]

