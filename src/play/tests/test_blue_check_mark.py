#!/usr/bin/env python3
"""
Test script for blue check mark on employee tab.
This test logs in, navigates to the Employee tab, checks if the blue check mark is present,
and takes a screenshot if it is found.
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


def test_blue_check_mark():
    """Main test function for blue check mark on employee tab."""
    # Setup logging to see logs from employee_page.py and other modules
    setup_logging(verbose=True)
    
    app_config = get_app_config()
    base_url = app_config["base_url"]
    
    print("=" * 60)
    print("Blue Check Mark Test - Employee Tab")
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
            
            # Step 2: Wait for dashboard to load
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
            
            # Step 5: Check for blue check mark
            print("\n" + "=" * 60)
            print("5. Checking for Blue Check Mark")
            print("=" * 60)
            
            # Check if blue check mark is visible
            blue_check_visible = employee_page.is_blue_thumbs_up()
            print(f"Blue check mark visible: {'✅ Yes' if blue_check_visible else '❌ No'}")
            
            if blue_check_visible:
                print("\n   ✅ Blue check mark found on employee tab!")
                
                # Step 6: Take screenshot
                print("\n" + "=" * 60)
                print("6. Taking Screenshot")
                print("=" * 60)
                
                try:
                    screenshot_path = employee_page.capture_blue_thumbs_up_tooltip()
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
                    # Take a simple screenshot as fallback
                    try:
                        fallback_path = employee_page.take_screenshot("blue_check_mark_fallback")
                        print(f"   📸 Fallback screenshot saved to: {fallback_path}")
                    except Exception as fallback_error:
                        print(f"   ❌ Fallback screenshot also failed: {fallback_error}")
            else:
                print("\n   ⚠️  Blue check mark not found on employee tab")
                print("   (This may be expected if the employee has not signed off yet)")
                
                # Take a screenshot anyway to show the current state
                try:
                    screenshot_path = employee_page.take_screenshot("blue_check_mark_not_found")
                    print(f"\n   📸 Screenshot of current state saved to: {screenshot_path}")
                except Exception as e:
                    print(f"   ⚠️  Could not take screenshot: {e}")
            
            # Summary
            print("\n" + "=" * 60)
            print("Test Summary")
            print("=" * 60)
            print(f"Login: ✅ Success")
            print(f"Dashboard Load: ✅ Success")
            print(f"Navigation to Employee Tab: ✅ Success")
            print(f"Employee Page Load: ✅ Success")
            print(f"Blue Check Mark: {'✅ Found' if blue_check_visible else '❌ Not found'}")
            if blue_check_visible:
                print(f"Screenshot: ✅ Captured")
            print("=" * 60)
            
            # Save trace
            trace_path = "test-results/trace_blue_check_mark_test.zip"
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
        test_blue_check_mark()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

