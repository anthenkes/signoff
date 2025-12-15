#!/usr/bin/env python3
"""
Headless login test that verifies login functionality in headless mode.
On failure, saves HTML and screenshot for debugging.
"""
import sys
import os
from pathlib import Path

# Add src directory to path so we can import from modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from playwright.sync_api import sync_playwright
from play.pages.login_page import LoginPage
from play.pages.dashboard_page import DashboardPage
from config import get_app_config, load_users


def test_login_headless():
    """
    Test login in headless mode.
    
    Asserts that login succeeds by waiting for the dashboard navigation bar.
    On failure, saves HTML and screenshot to test-results/login-headless/.
    """
    app_config = get_app_config()
    base_url = app_config["base_url"]
    
    # Get user credentials from environment or config file
    username = os.getenv("APIHC_USERNAME")
    password = os.getenv("APIHC_PASSWORD")
    
    # If not in environment, try to load from users.json
    if not username or not password:
        users = load_users()
        if users:
            user = users[0]
            username = user.username
            password = user.password
        else:
            print("❌ Error: No credentials found!")
            print("   Please set APIHC_USERNAME and APIHC_PASSWORD environment variables")
            print("   OR create a users.json file with user credentials")
            sys.exit(1)
    
    # Always use "MC Network" domain
    domain = "MC Network"
    
    # Create output directory for failure artifacts
    output_dir = Path("test-results/login-headless")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)
        
        try:
            # Step 1: Navigate to login page
            print("Navigating to login page...")
            login_page = LoginPage(page)
            login_page.goto(base_url)
            login_page.wait_for_page_load()
            print("✅ Login page loaded")
            
            # Step 2: Perform login
            print("Performing login...")
            login_page.login(username=username, password=password, domain=domain)
            print("✅ Login credentials submitted")
            
            # Step 3: Wait for post-login selector (dashboard navigation bar)
            print("Waiting for post-login selector (dashboard navigation bar)...")
            dashboard_page = DashboardPage(page)
            dashboard_page.wait_for_dashboard_load()
            print("✅ Login successful - dashboard navigation bar found")
            
            print("\n✅ Test passed: Login succeeded in headless mode")
            return 0
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Save failure artifacts
            try:
                # Save HTML
                html_path = output_dir / "login_failure.html"
                html_content = page.content()
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"📄 HTML saved to: {html_path}")
                
                # Save screenshot
                screenshot_path = output_dir / "login_failure.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"📸 Screenshot saved to: {screenshot_path}")
            except Exception as save_error:
                print(f"⚠️  Warning: Failed to save failure artifacts: {save_error}")
            
            return 1
        
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        exit_code = test_login_headless()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

