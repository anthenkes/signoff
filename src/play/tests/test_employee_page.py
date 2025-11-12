#!/usr/bin/env python3
"""
Test script for employee page focusing on hover and screenshot capability.
This test logs in, navigates to the Employee tab, and tests the calculator tooltip screenshot.
"""
import sys
import os
from pathlib import Path

# Add src directory to path so we can import from modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.sync_api import sync_playwright
from play.pages.login_page import LoginPage
from play.pages.dashboard_page import DashboardPage
from play.pages.employee_page import EmployeePage
from config import get_app_config, load_users
from utils import setup_logging
from play.tests.test_utils import (
    test_element,
    test_button
)


def test_employee_page():
    """Main test function for employee page focusing on hover and screenshot capability."""
    # Setup logging to see logs from employee_page.py and other modules
    setup_logging(verbose=True)  # Set to DEBUG level to see all logs
    
    app_config = get_app_config()
    base_url = app_config["base_url"]
    
    print("=" * 60)
    print("Employee Page - Hover and Screenshot Test")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print("=" * 60)
    
    # Get user credentials from environment or config file
    username = os.getenv("APIHC_USERNAME")
    password = os.getenv("APIHC_PASSWORD")
    domain = os.getenv("APIHC_DOMAIN", "MC Network")
    
    # If not in environment, try to load from users.json
    if not username or not password:
        users = load_users()
        if users:
            user = users[0]
            username = user.username
            password = user.password
            domain = user.domain
            print(f"Using credentials from users.json: {username}")
        else:
            print("❌ Error: No credentials found!")
            print("   Please set APIHC_USERNAME and APIHC_PASSWORD environment variables")
            print("   OR create a users.json file with user credentials")
            return
    
    with sync_playwright() as p:
        # Launch browser in headed mode (visible)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)
        
        # Enable tracing for debugging
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        
        try:
            # Step 1: Login
            print("\n1. Logging in...")
            login_page = LoginPage(page)
            login_page.goto(base_url)
            login_page.wait_for_page_load()
            print("   ✅ Login page loaded")
            
            login_page.login(username=username, password=password, domain=domain)
            print("   ✅ Login credentials submitted")
            
            # Step 2: Wait for dashboard to load (this waits for specific elements)
            print("\n2. Waiting for dashboard to load...")
            dashboard_page = DashboardPage(page)
            dashboard_page.wait_for_dashboard_load()
            print("   ✅ Login successful, navigated to dashboard")
            print("   ✅ Dashboard loaded")
            
            # Step 3: Navigate to Employee tab
            print("\n" + "=" * 60)
            print("3. Navigating to Employee Tab")
            print("=" * 60)
            
            print("   Clicking Employee tab...")
            dashboard_page.navigate_to_employee()
            print("   ✅ Navigation to Employee tab completed")
            
            # Give the page a moment to start loading after navigation
            page.wait_for_timeout(1000)
            
            # Step 4: Wait for employee page to load
            print("\n" + "=" * 60)
            print("4. Waiting for Employee Page to Load")
            print("=" * 60)
            
            employee_page = EmployeePage(page)
            employee_page.wait_for_employee_page_load()
            print("   ✅ Employee page loaded")
            
            # Step 5: Verify Employee Sign Off button is visible
            print("\n" + "=" * 60)
            print("5. Verifying Employee Sign Off Button")
            print("=" * 60)
            
            sign_off_visible = employee_page.is_sign_off_button_visible()
            print(f"Employee Sign Off button visible: {'✅ Yes' if sign_off_visible else '❌ No'}")
            
            if not sign_off_visible:
                raise Exception("Employee Sign Off button is not visible! Cannot proceed with test.")
            
            # Test the button element
            sign_off_result = test_element(
                employee_page.employee_sign_off_button,
                "Employee Sign Off Button",
                page,
                pause=False
            )
            
            if not sign_off_result["found"]:
                raise Exception("Employee Sign Off button not found!")
            
            # Step 6: Test hover and screenshot capability
            print("\n" + "=" * 60)
            print("6. Testing Hover and Screenshot Capability")
            print("=" * 60)
            
            print("   Looking for calculator icon...")
            # Use the property from EmployeePage which accesses the iframe correctly
            calc_icon = employee_page.calculator_icon
            
            # Check if calculator icon exists
            try:
                calc_count = calc_icon.count()
                print(f"   Calculator icons found: {calc_count}")
                
                if calc_count == 0:
                    print("   ⚠️  Warning: Calculator icon not found. Testing screenshot capability anyway...")
                    print("   (The screenshot method will handle this gracefully)")
                else:
                    print("   ✅ Calculator icon found")
                    # Use .first to get a single element for visibility check
                    calc_visible = calc_icon.first.is_visible(timeout=5000)
                    print(f"   Calculator icon visible: {'✅ Yes' if calc_visible else '❌ No'}")
            except Exception as e:
                print(f"   ⚠️  Warning: Error checking calculator icon: {e}")
                print("   (The screenshot method will handle this gracefully)")
            
            # Test the capture_calculator_tooltip method
            print("\n   Testing capture_calculator_tooltip() method...")
            try:
                screenshot_path = employee_page.capture_calculator_tooltip()
                print(f"   ✅ Screenshot captured successfully!")
                print(f"   📸 Screenshot saved to: {screenshot_path}")
                
                # Verify the screenshot file exists
                if os.path.exists(screenshot_path):
                    file_size = os.path.getsize(screenshot_path)
                    print(f"   📊 Screenshot file size: {file_size} bytes")
                    if file_size > 0:
                        print("   ✅ Screenshot file is valid (non-empty)")
                    else:
                        print("   ⚠️  Warning: Screenshot file is empty")
                else:
                    print(f"   ⚠️  Warning: Screenshot file not found at expected path: {screenshot_path}")
                    
            except Exception as e:
                print(f"   ❌ Error capturing screenshot: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Summary
            print("\n" + "=" * 60)
            print("Test Summary")
            print("=" * 60)
            print(f"Login: ✅ Success")
            print(f"Dashboard Load: ✅ Success")
            print(f"Navigation to Employee Tab: ✅ Success")
            print(f"Employee Page Load: ✅ Success")
            print(f"Employee Sign Off Button: {'✅ Found' if sign_off_result['found'] else '❌ Not found'}")
            print(f"Calculator Icon: {'✅ Found' if calc_count > 0 else '⚠️  Not found'}")
            print(f"Screenshot Capture: ✅ Success")
            print("=" * 60)
            
            # Save trace
            trace_path = "test-results/trace_employee_test.zip"
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
        test_employee_page()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

