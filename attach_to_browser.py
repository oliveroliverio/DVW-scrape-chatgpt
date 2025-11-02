"""
attach_to_browser.py

A reusable module for attaching to an existing Chrome browser instance via CDP
(Chrome DevTools Protocol). This allows manual login to sites before automated
scraping begins.

Usage:
    1. Launch Chrome with remote debugging:
       "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         --remote-debugging-port=9222 \
         --profile-directory="Default"

    2. Manually navigate to and login to your target site

    3. Use this module to attach to the browser and continue with automation

Example:
    from attach_to_browser import attach_to_browser, find_page_by_domain

    browser = attach_to_browser()
    page = find_page_by_domain(browser, "example.com")
    # Continue with your scraping logic...
"""

import os
from playwright.sync_api import sync_playwright
from typing import Optional
from urllib.parse import urlparse


def get_cdp_endpoint() -> str:
    """
    Get the CDP endpoint URL from environment variable or use default.

    Returns:
        str: CDP endpoint URL
    """
    return os.environ.get("CDP", "http://localhost:9222")


def attach_to_browser():
    """
    Attach to an existing Chrome browser instance via CDP.

    Returns:
        Browser: Playwright browser instance connected to existing Chrome

    Raises:
        RuntimeError: If no Chrome browser contexts are found or connection
                     fails

    Prerequisites:
        Chrome must be running with --remote-debugging-port=9222 (or custom
        port via CDP env var)

    Example Chrome launch command:
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
          --remote-debugging-port=9222 \
          --profile-directory="Default"
    """
    cdp_endpoint = get_cdp_endpoint()

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_endpoint)

        if not browser.contexts:
            raise RuntimeError(
                f"No contexts found in the attached Chrome. "
                f"Is Chrome running with --remote-debugging-port? "
                f"Current CDP endpoint: {cdp_endpoint}"
            )

        context_count = len(browser.contexts)
        page_count = sum(len(ctx.pages) for ctx in browser.contexts)
        print(f"[info] Successfully attached to Chrome browser via "
              f"{cdp_endpoint}")
        print(f"[info] Found {context_count} context(s) with {page_count} "
              f"total page(s)")

        return browser

    except Exception as e:
        raise RuntimeError(
            f"Failed to connect to Chrome browser at {cdp_endpoint}. "
            f"Make sure Chrome is running with --remote-debugging-port. "
            f"Error: {str(e)}"
        )


def find_page_by_domain(browser, domain: str,
                        exact_match: bool = False) -> Optional[object]:
    """
    Find a page/tab that matches the specified domain.

    Args:
        browser: Playwright browser instance
        domain: Domain to search for (e.g., "chatgpt.com", "example.com")
        exact_match: If True, requires exact domain match. If False, allows
                    subdomain matches.

    Returns:
        Page object if found, None otherwise

    Example:
        page = find_page_by_domain(browser, "chatgpt.com")
        page = find_page_by_domain(browser, "chat.openai.com",
                                   exact_match=True)
    """
    domain_lower = domain.lower()

    for context in browser.contexts:
        for page in context.pages:
            url = (page.url or "").lower()

            if exact_match:
                # Extract domain from URL for exact comparison
                parsed = urlparse(url)
                page_domain = parsed.netloc.lower()
                if page_domain == domain_lower:
                    print(f"[info] Found exact domain match: {page.url}")
                    return page
            else:
                # Allow subdomain matches
                if domain_lower in url:
                    print(f"[info] Found domain match: {page.url}")
                    return page

    print(f"[warning] No page found matching domain: {domain}")
    return None


def find_page_by_url_pattern(browser, pattern: str) -> Optional[object]:
    """
    Find a page/tab that contains the specified URL pattern.

    Args:
        browser: Playwright browser instance
        pattern: URL pattern to search for (case-insensitive)

    Returns:
        Page object if found, None otherwise

    Example:
        page = find_page_by_url_pattern(browser, "/c/")  # ChatGPT
        page = find_page_by_url_pattern(browser, "dashboard")
    """
    pattern_lower = pattern.lower()

    for context in browser.contexts:
        for page in context.pages:
            url = (page.url or "").lower()
            if pattern_lower in url:
                print(f"[info] Found URL pattern match: {page.url}")
                return page

    print(f"[warning] No page found matching pattern: {pattern}")
    return None


def get_first_page(browser) -> object:
    """
    Get the first available page from the browser.

    Args:
        browser: Playwright browser instance

    Returns:
        First page object found

    Raises:
        RuntimeError: If no pages are available
    """
    for context in browser.contexts:
        if context.pages:
            page = context.pages[0]
            print(f"[info] Using first available page: {page.url}")
            return page

    raise RuntimeError("No pages found in any browser context")


def list_all_pages(browser) -> list:
    """
    List all open pages/tabs in the browser.

    Args:
        browser: Playwright browser instance

    Returns:
        List of dictionaries containing page info (url, title)
    """
    pages_info = []

    for context_idx, context in enumerate(browser.contexts):
        for page_idx, page in enumerate(context.pages):
            try:
                title = page.title()
            except Exception:
                title = "Unable to get title"

            pages_info.append({
                'context': context_idx,
                'page': page_idx,
                'url': page.url,
                'title': title,
                'page_object': page
            })

    return pages_info


def print_browser_info(browser):
    """
    Print information about the attached browser and its pages.

    Args:
        browser: Playwright browser instance
    """
    print("\n=== Browser Information ===")
    print(f"CDP Endpoint: {get_cdp_endpoint()}")
    print(f"Contexts: {len(browser.contexts)}")

    pages_info = list_all_pages(browser)
    print(f"Total Pages: {len(pages_info)}")

    if pages_info:
        print("\nOpen Pages:")
        for i, page_info in enumerate(pages_info):
            print(f"  {i+1}. {page_info['title']}")
            print(f"     URL: {page_info['url']}")

    print("=" * 30)


def attach_and_find_page(domain: str = None, url_pattern: str = None,
                         exact_match: bool = False):
    """
    Convenience function that attaches to browser and finds a specific page.

    Args:
        domain: Domain to search for (optional)
        url_pattern: URL pattern to search for (optional)
        exact_match: Whether to require exact domain match

    Returns:
        Tuple of (browser, page) where page might be None if not found

    Example:
        browser, page = attach_and_find_page(domain="chatgpt.com")
        browser, page = attach_and_find_page(url_pattern="/dashboard")
    """
    browser = attach_to_browser()

    page = None
    if domain:
        page = find_page_by_domain(browser, domain, exact_match)
    elif url_pattern:
        page = find_page_by_url_pattern(browser, url_pattern)

    if not page:
        print("[info] No specific page found, using first available page")
        page = get_first_page(browser)

    return browser, page


if __name__ == "__main__":
    # Example usage and testing
    try:
        browser = attach_to_browser()
        print_browser_info(browser)

        # Example: Find ChatGPT page
        chatgpt_page = find_page_by_domain(browser, "chatgpt.com")
        if chatgpt_page:
            print(f"\nFound ChatGPT page: {chatgpt_page.url}")

        # Example: Get first page
        first_page = get_first_page(browser)
        print(f"First page: {first_page.url}")

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure Chrome is running with:")
        print('"/Applications/Google Chrome.app/Contents/MacOS/Google '
              'Chrome" \\')
        print('  --remote-debugging-port=9222 \\')
        print('  --profile-directory="Default"')
