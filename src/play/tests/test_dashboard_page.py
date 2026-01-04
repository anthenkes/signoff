#!/usr/bin/env python3
"""
Test script for dashboard page focusing on Employee tab navigation.
This test logs in and verifies navigation to the Employee tab works correctly.
"""
import sys
import os
from pathlib import Path

# Add src directory to path so we can import from modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.sync_api import sync_playwright
from src.play.pages.login_page import LoginPage
from src.play.pages.dashboard_page import DashboardPage
from src.config import get_app_config, load_users
from src.play.tests.test_utils import (
    test_element,
    test_button
)


def test_dashboard_page():
    """Main test function for dashboard page focusing on Employee tab navigation."""
    app_config = get_app_config()
    base_url = app_config["base_url"]
    
    print("=" * 60)
    print("Dashboard Page - Employee Tab Navigation Test")
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
            
            # Step 3: Verify navigation bar and Employee tab are present
            print("\n" + "=" * 60)
            print("3. Verifying Navigation Elements")
            print("=" * 60)
            
            # Test navigation bar
            nav_result = test_element(
                dashboard_page.nav_bar,
                "Navigation Bar",
                page,
                pause=False
            )
            
            if not nav_result["found"]:
                raise Exception("Navigation bar not found! Cannot proceed with tab testing.")
            
            # Test Employee tab exists
            employee_result = test_element(
                dashboard_page.employee_tab,
                "Employee Tab",
                page,
                pause=False
            )
            
            if not employee_result["found"]:
                raise Exception("Employee tab not found! Cannot proceed with navigation test.")
            
            # Verify Employee tab is clickable
            print("\n4. Verifying Employee Tab is Clickable")
            print("=" * 60)
            employee_clickable = test_button(
                dashboard_page.employee_tab,
                "Employee Tab",
                page,
                pause=False
            )
            
            if not employee_clickable:
                raise Exception("Employee tab is not clickable!")
            
            # Step 4: Test initial tab state (should be on Home)
            print("\n" + "=" * 60)
            print("5. Checking Initial Tab State")
            print("=" * 60)
            
            # Wait a moment for navigation state to stabilize
            page.wait_for_timeout(1000)
            
            active_tabs_before = dashboard_page.get_active_tabs()
            inactive_tabs_before = dashboard_page.get_inactive_tabs()
            print(f"Active tabs before navigation: {active_tabs_before if active_tabs_before else 'None'}")
            print(f"Inactive tabs before navigation: {inactive_tabs_before if inactive_tabs_before else 'None'}")
            
            is_home_active = dashboard_page.is_on_home_tab()
            is_home_inactive = dashboard_page.is_tab_inactive("Home")
            print(f"Home tab active: {'✅ Yes' if is_home_active else '❌ No'}")
            print(f"Home tab inactive: {'✅ Yes' if is_home_inactive else '❌ No'}")
            
            is_employee_active_before = dashboard_page.is_tab_active("Employee")
            is_employee_inactive_before = dashboard_page.is_tab_inactive("Employee")
            print(f"Employee tab active before navigation: {'✅ Yes' if is_employee_active_before else '❌ No'}")
            print(f"Employee tab inactive before navigation: {'✅ Yes' if is_employee_inactive_before else '❌ No'}")
            
            # Step 5: Navigate to Employee tab
            print("\n" + "=" * 60)
            print("6. Testing Navigation to Employee Tab")
            print("=" * 60)
            
            print("   Clicking Employee tab...")
            dashboard_page.navigate_to_employee()
            print("   ✅ Navigation to Employee tab completed")
            
            # Step 6: Verify Employee tab is now active
            print("\n" + "=" * 60)
            print("7. Verifying Employee Tab is Active")
            print("=" * 60)
            
            # Wait a moment for navigation state to update
            page.wait_for_timeout(1000)
            
            active_tabs_after = dashboard_page.get_active_tabs()
            inactive_tabs_after = dashboard_page.get_inactive_tabs()
            print(f"Active tabs after navigation: {active_tabs_after if active_tabs_after else 'None'}")
            print(f"Inactive tabs after navigation: {inactive_tabs_after if inactive_tabs_after else 'None'}")
            
            is_employee_active_after = dashboard_page.is_tab_active("Employee")
            is_employee_inactive_after = dashboard_page.is_tab_inactive("Employee")
            print(f"Employee tab active after navigation: {'✅ Yes' if is_employee_active_after else '❌ No'}")
            print(f"Employee tab inactive after navigation: {'✅ Yes' if is_employee_inactive_after else '❌ No'}")
            
            if not is_employee_active_after:
                raise Exception("Employee tab did not become active after navigation!")
            
            # Verify Home tab state after navigation
            is_home_active_after = dashboard_page.is_on_home_tab()
            is_home_inactive_after = dashboard_page.is_tab_inactive("Home")
            print(f"Home tab active after navigation: {'✅ Yes' if is_home_active_after else '❌ No'}")
            print(f"Home tab inactive after navigation: {'✅ Yes' if is_home_inactive_after else '❌ No'}")
            
            if is_home_active_after and is_employee_active_after:
                print("   ⚠️  Warning: Both Home and Employee tabs are active (may be expected behavior)")
            
            # Summary
            print("\n" + "=" * 60)
            print("Test Summary")
            print("=" * 60)
            print(f"Navigation Bar: {'✅ Found' if nav_result['found'] else '❌ Not found'}")
            print(f"Employee Tab: {'✅ Found' if employee_result['found'] else '❌ Not found'}")
            print(f"Employee Tab Clickable: {'✅ Yes' if employee_clickable else '❌ No'}")
            print(f"Navigation to Employee Tab: ✅ Success")
            print(f"Employee Tab Active After Navigation: {'✅ Yes' if is_employee_active_after else '❌ No'}")
            print("=" * 60)
            
            # Save trace
            trace_path = "test-results/trace_dashboard_test.zip"
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
        test_dashboard_page()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

