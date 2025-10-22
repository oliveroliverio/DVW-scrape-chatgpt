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


def get_chat_markdown(page) -> str:
    """
    Loads ./ChatGPT_to_md.js into the page and returns the markdown string.
    """
    js_path = Path(__file__).with_name("ChatGPT-to-md.js")
    src = js_path.read_text(encoding="utf-8")
    md = page.evaluate(f"(() => {{ {src}; return getChatMarkdown(); }})()")
    if not isinstance(md, str):
        raise RuntimeError("JS did not return a markdown string.")
    return md


def save_markdown(markdown: str, slug: str) -> Path:
    """
    Saves markdown to ~/Desktop/ChatGPT-Archive/{slug}_{YYMMDD_HHMMSS}.md
    """
    out_dir = Path.home() / "Desktop" / "ChatGPT-Archive"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{slug}_{timestamp_now()}.md"
    out_path = out_dir / fname
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


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
        # Try project links first (<section><ol><li><a href>)
        proj_links = page.locator(PROJECT_LINKS_SELECTOR)
        proj_count = proj_links.count()

        if proj_count > 0:
            print(f"[info] Project items detected: {proj_count}")
            links = proj_links
        else:
            print("[info] No project items found; using sidebar chat links...")
            container = page.locator(CONTAINER_SELECTOR).first
            try:
                container.wait_for(state="attached", timeout=5000)
                print("[info] Sidebar container located.")
            except PWTimeoutError:
                print("[warn] Sidebar container not found; using page scope.")
                container = page
            links = container.locator(CHAT_LINKS_SELECTOR)

        count = links.count()
        print(f"[info] Link items detected: {count}")
        if count == 0:
            raise RuntimeError("No links found in section or sidebar.")

        # Click and scrape first 3 items for now
        for i in range(min(3, count)):
            link = links.nth(i)

            # 1) TITLE BEFORE CLICK (attributes first, then inner text)
            title = link.get_attribute(
                "title") or link.get_attribute("aria-label")
            if not title:
                title = link.inner_text(timeout=5000)
            title = re.sub(r"\s+", " ", (title or f"chat_{i+1}")).strip()

            slug = slugify_title(title)
            href = link.get_attribute("href")
            print(
                f"[info] Opening item {i+1}: {href}  |  title='{title}'  |  slug='{slug}'")

            # 2) OPEN
            link.scroll_into_view_if_needed()
            link.click()
            page.wait_for_load_state("networkidle", timeout=8000)

            # 3) SCRAPE
            markdown = get_chat_markdown(page)
            print(f"[info] Collected markdown length: {len(markdown)}")

            # 4) SAVE
            out_path = save_markdown(markdown, slug)
            print(f"[info] Saved: {out_path}")

            # 5) BACK
            print("[info] Going back to list...")
            page.go_back()
            page.wait_for_load_state("networkidle", timeout=8000)


if __name__ == "__main__":
    main()
