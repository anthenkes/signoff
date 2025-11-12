#!/usr/bin/env python3
"""
Extensible test script to verify login page element selection and functionality.
Run this to check if all login page selectors and interactions work correctly.
"""
import sys
from pathlib import Path

# Add src directory to path so we can import from modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.sync_api import sync_playwright
from play.pages.login_page import LoginPage
from config import get_app_config
from play.tests.test_utils import (
    test_element,
    test_input_field,
    test_dropdown,
    test_button
)


def test_login_page():
    """Main test function for login page elements."""
    app_config = get_app_config()
    base_url = app_config["base_url"]
    
    print("=" * 60)
    print("Login Page Element Testing")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print("=" * 60)
    
    with sync_playwright() as p:
        # Launch browser in headed mode (visible)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)
        
        # Enable tracing for debugging
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        
        try:
            # Navigate to login page
            print("\n1. Navigating to login page...")
            login_page = LoginPage(page)
            login_page.goto(base_url)
            login_page.wait_for_page_load()
            print("   ✅ Page loaded")
            
            # Test all elements
            print("\n" + "=" * 60)
            print("2. Testing Element Selection")
            print("=" * 60)
            
            # Test username field
            username_result = test_element(
                login_page.username_input,
                "Username Input",
                page,
                pause=True
            )
            
            # Test password field
            password_result = test_element(
                login_page.password_input,
                "Password Input",
                page,
                pause=True
            )
            
            # Test domain dropdown
            domain_result = test_element(
                login_page.domain_select,
                "Domain Dropdown",
                page,
                pause=True
            )
            
            # Test sign in button
            signin_result = test_element(
                login_page.sign_in_button,
                "Sign In Button",
                page,
                pause=True
            )
            
            # Test interactions
            print("\n" + "=" * 60)
            print("3. Testing Element Interactions")
            print("=" * 60)
            
            # Test username input
            if username_result["found"]:
                test_input_field(
                    login_page.username_input,
                    "Username",
                    "test_username",
                    page,
                    pause=True
                )
            
            # Test password input
            if password_result["found"]:
                test_input_field(
                    login_page.password_input,
                    "Password",
                    "test_password",
                    page,
                    pause=True
                )
            
            # Test domain dropdown
            if domain_result["found"]:
                test_dropdown(
                    login_page.domain_select,
                    "Domain Dropdown",
                    page,
                    test_options=["LLU Network", "MC Network", "System Authentication"],
                    pause=True
                )
            
            # Test buttons (without actually clicking - just verify they're ready)
            if signin_result["found"]:
                test_button(
                    login_page.sign_in_button,
                    "Sign In Button",
                    page,
                    pause=True
                )
            
            # Summary
            print("\n" + "=" * 60)
            print("Test Summary")
            print("=" * 60)
            print(f"Username field: {'✅ Found' if username_result['found'] else '❌ Not found'}")
            print(f"Password field: {'✅ Found' if password_result['found'] else '❌ Not found'}")
            print(f"Domain dropdown: {'✅ Found' if domain_result['found'] else '❌ Not found'}")
            print(f"Sign In button: {'✅ Found' if signin_result['found'] else '❌ Not found'}")
            print("=" * 60)
            
            # Save trace
            trace_path = "test-results/trace_login_test.zip"
            Path("test-results").mkdir(exist_ok=True)
            context.tracing.stop(path=trace_path)
            print(f"\n📊 Trace saved to: {trace_path}")
            print(f"   View with: playwright show-trace {trace_path}")
            
            input("\nPress Enter to close browser...")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            page.pause()
        
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        test_login_page()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)