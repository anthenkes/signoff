#!/usr/bin/env python3
"""
Shared test utilities for page element testing.
These functions can be reused across different page test files.
"""
from playwright.sync_api import Page, Locator
from typing import Dict, Optional, List


def test_element(
    locator: Locator, 
    element_name: str, 
    page: Page, 
    pause: bool = True,
    custom_attributes: Optional[List[str]] = None
) -> Dict:
    """
    Test a single element - check if it exists, get attributes, and highlight.
    
    This function is reusable across different page tests (login, dashboard, etc.).
    
    Args:
        locator: The Playwright locator to test
        element_name: Human-readable name for the element
        page: The Playwright Page object for pausing and interaction
        pause: Whether to pause after testing for inspection
        custom_attributes: Optional list of additional attributes to check beyond defaults
    
    Returns:
        Dictionary with test results containing:
        - name: Element name
        - found: Whether element was found
        - count: Number of matching elements
        - visible: Whether element is visible
        - attributes: Dictionary of element attributes
        - error: Error message if any
    
    Example:
        result = test_element(
            login_page.username_input,
            "Username Input",
            page,
            pause=True
        )
    """
    result = {
        "name": element_name,
        "found": False,
        "count": 0,
        "visible": False,
        "attributes": {},
        "error": None
    }
    
    try:
        count = locator.count()
        result["count"] = count
        result["found"] = count > 0
        
        if count == 0:
            print(f"\n   ❌ {element_name}: No elements found")
            return result
        
        print(f"\n   ✅ {element_name}: Found {count} element(s)")
        
        # Get element details
        try:
            result["visible"] = locator.is_visible()
            print(f"      Visible: {result['visible']}")
            
            # Get common attributes
            common_attrs = ["id", "name", "type", "value", "placeholder", "class", "href", "role", "aria-label"]
            if custom_attributes:
                common_attrs.extend(custom_attributes)
            
            for attr in common_attrs:
                try:
                    value = locator.get_attribute(attr)
                    if value:
                        result["attributes"][attr] = value
                        print(f"      {attr}: {value}")
                except:
                    pass
            
            # Highlight the element
            print(f"      Highlighting element...")
            locator.highlight()
            
            if pause:
                print(f"      ⏸️  Pausing for inspection...")
                page.pause()
            
        except Exception as e:
            result["error"] = str(e)
            print(f"      ⚠️  Error getting details: {e}")
    
    except Exception as e:
        result["error"] = str(e)
        print(f"   ❌ {element_name}: Error - {e}")
    
    return result


def test_input_field(
    locator: Locator, 
    field_name: str, 
    test_value: str, 
    page: Page, 
    pause: bool = True
) -> bool:
    """
    Test an input field by filling it and verifying the value.
    
    Args:
        locator: The input field locator
        field_name: Human-readable name for the field
        test_value: Value to fill in
        page: The Playwright Page object for pausing
        pause: Whether to pause after testing
    
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n   Testing {field_name} input...")
        
        # Clear and fill
        locator.clear()
        locator.fill(test_value)
        
        # Verify value
        actual_value = locator.input_value()
        if actual_value == test_value:
            print(f"      ✅ Successfully filled: '{test_value}'")
            if pause:
                page.pause()
            return True
        else:
            print(f"      ⚠️  Expected '{test_value}', got '{actual_value}'")
            if pause:
                page.pause()
            return False
    
    except Exception as e:
        print(f"      ❌ Error filling {field_name}: {e}")
        if pause:
            page.pause()
        return False


def test_dropdown(
    locator: Locator, 
    dropdown_name: str,
    page: Page, 
    test_options: Optional[List[str]] = None,
    pause: bool = True
) -> bool:
    """
    Test a dropdown/select element by selecting different options.
    
    Args:
        locator: The dropdown locator
        dropdown_name: Human-readable name for the dropdown
        page: The Playwright Page object for pausing
        test_options: Optional list of option labels/values to test. 
                     If None, will just list available options.
        pause: Whether to pause after testing
    
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n   Testing {dropdown_name}...")
        
        # Get available options
        options = locator.locator("option").all()
        option_texts = [opt.text_content() for opt in options if opt.text_content()]
        print(f"      Available options: {option_texts}")
        
        if not test_options:
            print(f"      ℹ️  No specific options to test")
            if pause:
                page.pause()
            return True
        
        # Test selecting each option
        success = True
        
        for option in test_options:
            if option in option_texts:
                try:
                    locator.select_option(label=option)
                    selected = locator.input_value()
                    print(f"      ✅ Selected '{option}'")
                    if pause:
                        page.pause()
                except Exception as e:
                    print(f"      ❌ Failed to select '{option}': {e}")
                    success = False
            else:
                print(f"      ⚠️  Option '{option}' not found in dropdown")
        
        return success
    
    except Exception as e:
        print(f"      ❌ Error testing {dropdown_name}: {e}")
        if pause:
            page.pause()
        return False


def test_button(
    locator: Locator, 
    button_name: str, 
    page: Page, 
    pause: bool = True
) -> bool:
    """
    Test a button by checking if it's clickable (without actually clicking).
    
    Args:
        locator: The button locator
        button_name: Human-readable name for the button
        page: The Playwright Page object for pausing
        pause: Whether to pause after testing
    
    Returns:
        True if button is clickable, False otherwise
    """
    try:
        print(f"\n   Testing {button_name}...")
        
        is_visible = locator.is_visible()
        is_enabled = locator.is_enabled()
        
        print(f"      Visible: {is_visible}")
        print(f"      Enabled: {is_enabled}")
        
        if is_visible and is_enabled:
            print(f"      ✅ {button_name} is clickable")
            if pause:
                page.pause()
            return True
        else:
            print(f"      ⚠️  {button_name} is not fully clickable")
            if pause:
                page.pause()
            return False
    
    except Exception as e:
        print(f"      ❌ Error testing {button_name}: {e}")
        if pause:
            page.pause()
        return False


def test_link(
    locator: Locator,
    link_name: str,
    page: Page,
    pause: bool = True
) -> Dict:
    """
    Test a link element by checking its properties.
    
    Args:
        locator: The link locator
        link_name: Human-readable name for the link
        page: The Playwright Page object for pausing
        pause: Whether to pause after testing
    
    Returns:
        Dictionary with test results
    """
    result = {
        "name": link_name,
        "found": False,
        "visible": False,
        "href": None,
        "error": None
    }
    
    try:
        count = locator.count()
        result["found"] = count > 0
        
        if count == 0:
            print(f"\n   ❌ {link_name}: No links found")
            return result
        
        print(f"\n   ✅ {link_name}: Found {count} link(s)")
        
        result["visible"] = locator.is_visible()
        print(f"      Visible: {result['visible']}")
        
        href = locator.get_attribute("href")
        if href:
            result["href"] = href
            print(f"      href: {href}")
        
        if pause:
            locator.highlight()
            page.pause()
    
    except Exception as e:
        result["error"] = str(e)
        print(f"   ❌ {link_name}: Error - {e}")
    
    return result

