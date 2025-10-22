# scrape.py
# Attaches to your *already running* Chrome (launched with --remote-debugging-port=9222),
# finds the main container <div class="relative basis-auto flex-col grow grid">,
# and clicks the first chat link inside it.

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import os
import re
from datetime import datetime
import time
from pathlib import Path
import unicodedata


CDP_ENDPOINT = "http://localhost:9222"
CONTAINER_SELECTOR = 'div.relative.basis-auto.flex-col.grow.grid'
# target <a class="w-full" ...> that points to /c/<id>
CHAT_LINKS_SELECTOR = 'a.w-full[href*="/c/"]'
PROJECT_LINKS_SELECTOR = 'section ol li a[href]'


def timestamp_now() -> str:
    """Returns a compact YYMMDD_HHMMSS string."""
    return datetime.now().strftime("%y%m%d_%H%M%S")


def slugify_title(title: str) -> str:
    """
    Converts a chat title into a filesystem-safe slug

    Examples:
        'Project: ChatGPT Scraper v1.0!' → 'project_chatgpt_scraper_v1_0'
        'Deep Learning – Notes' → 'deep_learning_notes'
    """
    if not title:
        return "untitled_chat"

    # Normalize accented characters (é → e)
    title = unicodedata.normalize("NFKD", title).encode(
        "ascii", "ignore").decode("ascii")

    # Replace separators and illegal characters with underscores
    # remove anything not alphanumeric, space, dash
    title = re.sub(r"[^\w\s-]", "_", title)
    # collapse whitespace/dashes to single underscore
    title = re.sub(r"[\s\-]+", "_", title)

    # Strip leading/trailing underscores but keep case
    title = title.strip("_")

    # Limit length to something sane for filenames
    if len(title) > 80:
        title = title[:80]

    return title or "untitled_chat"


def pick_chatgpt_page(browser):
    # Prefer a tab already on ChatGPT; otherwise just take the first visible page.
    for context in browser.contexts:
        for page in context.pages:
            url = (page.url or "").lower()
            if "chatgpt.com" in url or "chat.openai.com" in url:
                return page
    # Fallback: first page in first context
    return browser.contexts[0].pages[0]


def main():
    with sync_playwright() as pw:
        # 1) Attach to existing Chrome via CDP
        browser = pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        if not browser.contexts:
            raise RuntimeError(
                "No contexts found in the attached Chrome. Is Chrome running with --remote-debugging-port=9222?")

        page = pick_chatgpt_page(browser)
        print(f"[info] Attached to page: {page.url}")

        # 2) Ensure the target container exists
        container = page.locator(CONTAINER_SELECTOR).first
        try:
            container.wait_for(state="attached", timeout=5000)
        except PWTimeoutError:
            raise RuntimeError(
                f"Container not found with selector: {CONTAINER_SELECTOR}")

        print("[info] Container located.")

        # 3) Count potential chat items (links to /c/<id>) within the container
        chat_links = container.locator(CHAT_LINKS_SELECTOR)
        count = chat_links.count()
        print(f"[info] Chat items detected: {count}")
        if count == 0:
            raise RuntimeError(
                f"No chat links found using selector: {CHAT_LINKS_SELECTOR}. Page structure may have changed.")

        # 4) Click the first chat item
        for i in range(3):
            chat_link = chat_links.nth(i)
            href = chat_link.get_attribute("href")
            print(f"[info] Opening chat {i+1}: {href}")
            chat_link.scroll_into_view_if_needed()
            chat_link.click()
            page.wait_for_load_state("networkidle", timeout=8000)

            # Save markdown to Desktop/ChatGPT-Archive
            out_path = scrape_current_chat_to_markdown(page)
            print(f"[info] Saved: {out_path}")

            # go back
            print("[info] Going back to chat list...")
            page.go_back()
            page.wait_for_load_state("networkidle", timeout=8000)


if __name__ == "__main__":
    main()
