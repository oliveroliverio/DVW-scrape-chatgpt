#!/usr/bin/env python3
"""
example_usage.py

Example usage of the attach_to_browser module for various scraping scenarios.
"""

from attach_to_browser import (
    attach_to_browser,
    find_page_by_domain,
    find_page_by_url_pattern,
    attach_and_find_page,
    print_browser_info
)


def example_basic_attachment():
    """Basic example: Attach to browser and get first page."""
    print("=== Basic Browser Attachment ===")
    try:
        browser = attach_to_browser()
        print_browser_info(browser)
    except Exception as e:
        print(f"Error: {e}")


def example_find_chatgpt():
    """Example: Find and use ChatGPT page."""
    print("\n=== ChatGPT Example ===")
    try:
        browser = attach_to_browser()
        page = find_page_by_domain(browser, "chatgpt.com")
        
        if page:
            print(f"Current page title: {page.title()}")
            # You can now use the page for scraping
            # Example: page.click("button")
            # Example: page.fill("input", "text")
        else:
            print("ChatGPT page not found. Please open ChatGPT in browser.")
            
    except Exception as e:
        print(f"Error: {e}")


def example_find_by_pattern():
    """Example: Find page by URL pattern."""
    print("\n=== URL Pattern Example ===")
    try:
        browser = attach_to_browser()
        # Look for a ChatGPT conversation (contains /c/ in URL)
        page = find_page_by_url_pattern(browser, "/c/")
        
        if page:
            print(f"Found conversation page: {page.url}")
            # Continue with conversation-specific scraping
        else:
            print("No conversation page found")
            
    except Exception as e:
        print(f"Error: {e}")


def example_convenience_function():
    """Example: Using the convenience function."""
    print("\n=== Convenience Function Example ===")
    try:
        # One-liner to attach and find page
        browser, page = attach_and_find_page(domain="chatgpt.com")
        
        if page:
            print(f"Ready to scrape: {page.url}")
            # Your scraping logic here
        
    except Exception as e:
        print(f"Error: {e}")


def example_custom_site():
    """Example: Attach to any custom site."""
    print("\n=== Custom Site Example ===")
    try:
        # Replace "example.com" with your target site
        browser = attach_to_browser()
        page = find_page_by_domain(browser, "example.com")
        
        if page:
            print(f"Found page: {page.url}")
            # Your custom scraping logic here
            # Example: 
            # page.wait_for_selector("div.content")
            # content = page.inner_text("div.content")
            # print(content)
        else:
            print("Target site not found in open tabs")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("Browser Attachment Examples")
    print("=" * 40)
    print("Make sure Chrome is running with:")
    print('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\')
    print('  --remote-debugging-port=9222 \\')
    print('  --profile-directory="Default"')
    print("=" * 40)
    
    # Run examples
    example_basic_attachment()
    example_find_chatgpt()
    example_find_by_pattern()
    example_convenience_function()
    example_custom_site()
