# Playwright Testing Guide in Jupyter

This guide explains how to use Jupyter Notebooks as an interactive "EDA" (Exploratory Data Analysis) environment for developing and testing Playwright browser automation scripts. This approach allows you to iterate faster by testing selectors and logic in real-time without restarting the entire script.

## Prerequisites

Ensure you have the following installed in your environment:

```bash
pip install playwright jupyter ipykernel
playwright install chromium
```

## 1. Setting up the Jupyter Environment

Since we are often debugging `scrape.py` which uses the **Sync** API, we will use the synchronous Playwright API in Jupyter as well. This avoids the complexity of `asyncio` loops in notebooks.

Create a new notebook (e.g., `debug_scraping.ipynb`) and import the necessary libraries:

```python
from playwright.sync_api import sync_playwright
import time
import sys
import os

# Add the root directory to path so we can import local modules
sys.path.append('..') 

# Import your existing helper for attaching to browser
try:
    from attach_to_browser import attach_to_browser, find_page_by_domain
    print("✅ attach_to_browser loaded successfully")
except ImportError:
    print("❌ Could not import attach_to_browser. Make sure you are in the Jupyter/ directory.")
```

## 2. Attaching to an Existing Browser

This is the **preferred method** for debugging. It allows you to manually log in and navigate, then hand off control to Python.

1.  **Launch Chrome via Terminal** (Run this in your terminal, not Jupyter):
    ```bash
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --profile-directory="Default"
    ```
2.  **Attach in Jupyter**:

    ```python
    # Connect to the running browser
    browser = attach_to_browser()
    
    # Get the current active page (or find specific one)
    # This is great for testing on the page you are currently looking at!
    page = browser.contexts[0].pages[0] 
    
    print(f"Attached to: {page.title()}")
    ```

## 3. Starting a Fresh Browser (Alternative)

If you want to test a completely clean state (like a fresh user):

```python
# Start a new browser instance
p = sync_playwright().start()
browser = p.chromium.launch(headless=False) # Headless=False to see what's happening
context = browser.new_context()
page = context.new_page()

page.goto("https://example.com")
```

> **Note:** When you are done with a fresh browser, remember to run `browser.close()` and `p.stop()`.

## 4. Testing Variable Websites and Selectors

You can use Python lists and loops to iterate through different sites and selectors, similar to testing models in EDA.

```python
# Define your test cases: (Name, URL, Selector to test)
targets = [
    ("ChatGPT", "https://chatgpt.com", 'div.relative.basis-auto'),
    ("Example", "https://example.com", 'h1'),
    ("Google", "https://google.com", 'textarea[name="q"]'),
]

results = []

for name, url, selector in targets:
    print(f"Testing {name}...")
    try:
        # Navigate if we aren't already there
        if url not in page.url:
            page.goto(url, timeout=10000)
            page.wait_for_load_state('domcontentloaded')
        
        # Test the selector
        element = page.locator(selector).first
        
        # Check if visible
        if element.is_visible(timeout=3000):
            text = element.inner_text()[:50] # Preview text
            print(f"  ✅ Found '{selector}': {text}...")
            results.append({"name": name, "status": "Found", "content": text})
        else:
            print(f"  ❌ Selector '{selector}' timed out.")
            results.append({"name": name, "status": "Missing", "content": None})
            
    except Exception as e:
        print(f"  ⚠️ Error calling {url}: {e}")

# View summary
import pandas as pd
pd.DataFrame(results)
```

## 5. Automatic Login & Authentication

You can script the login process. It is best to wrap this in a function so you can re-run it easily if the session times out.

```python
def login_to_site(page, username, password):
    print("Attempting login...")
    page.goto("https://example.com/login")
    
    # Fill credentials
    page.fill('input[name="email"]', username)
    page.fill('input[name="password"]', password)
    
    # Click login and wait for navigation
    # 'wait_for_navigation' is crucial to ensure login completed
    with page.expect_navigation():
        page.click('button[type="submit"]')
        
    # Verify login success (look for a logout button or dashboard element)
    if page.is_visible('#dashboard'):
        print("✅ Login successful!")
    else:
        print("❌ Login might have failed.")

# Usage
# login_to_site(page, "myuser@test.com", "secret123")
```

## 6. Cookie Retrieval and Storage

Saving cookies allows you to persist a session across different runs or re-use it in your main script (`scrape.py`).

### Saving Cookies

```python
import json

def save_cookies(context, filepath="cookies.json"):
    cookies = context.cookies()
    with open(filepath, 'w') as f:
        json.dump(cookies, f, indent=2)
    print(f"Saved {len(cookies)} cookies to {filepath}")

# Run this after you are logged in
save_cookies(browser.contexts[0], "manual_session_cookies.json")
```

### Loading Cookies

```python
def load_cookies(context, filepath="cookies.json"):
    with open(filepath, 'r') as f:
        cookies = json.load(f)
    context.add_cookies(cookies)
    print(f"Loaded {len(cookies)} cookies.")

# Usage on a FRESH context
# 1. Create context
# new_context = browser.new_context()
# 2. Load cookies BEFORE navigating
# load_cookies(new_context, "manual_session_cookies.json")
# 3. Create page and go
# page = new_context.new_page()
# page.goto("https://chatgpt.com") # Should be logged in now!
```

## Summary Workflow

1.  **Start Chrome** in debug mode.
2.  **Attach** using `attach_to_browser()`.
3.  **Explore** the page using `page.locator(...)` in Jupyter cells.
4.  **Prototype** your extraction logic (loops, regex).
5.  **Move** working code to your main script (e.g., `scrape.py`).
