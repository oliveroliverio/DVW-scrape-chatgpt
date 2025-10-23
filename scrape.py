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

# -----------------------helper functions---------------------------


def to_abs_url(page, href: str) -> str:
    """Return absolute URL for a given href based on the current page origin."""
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    origin = page.evaluate("() => location.origin")
    return origin.rstrip("/") + "/" + href.lstrip("/")


def snapshot_items(page, links_locator):
    """
    Capture a stable list of (href, title, slug) from the current list view.
    Use this BEFORE clicking anything.
    """
    total = links_locator.count()
    items = []
    for i in range(total):
        a = links_locator.nth(i)
        href = a.get_attribute("href")
        title = get_list_title(a) or f"chat_{i+1}"
        slug = slugify_title(title)
        abs_url = to_abs_url(page, href)
        if not abs_url:
            continue
        items.append({"index": i, "href": href,
                     "abs_url": abs_url, "title": title, "slug": slug})
    return items


def wait_for_chat_and_markdown(page, max_wait_ms=12000, retries=4, pause_s=0.6) -> str:
    """
    Waits for chat content to appear, then returns non-empty markdown.
    Retries a few times in case the SPA is still painting.
    """
    # 1) Wait for any message node to be in the DOM
    page.wait_for_selector('[data-message-author-role]', timeout=max_wait_ms)
    page.wait_for_load_state("load", timeout=4000)

    # 2) Try a few times until markdown is non-empty
    for attempt in range(1, retries + 1):
        md = get_chat_markdown(page).strip()
        if md:
            return md
        # give the SPA a moment to finish painting/rehydration
        time.sleep(pause_s)
        try:
            page.wait_for_load_state("load", timeout=1500)
        except Exception:
            pass

    # last try; return whatever we got (possibly empty) so caller can decide
    return get_chat_markdown(page).strip()


def get_list_title(link_el) -> str:
    """
    From a project list <a>, return only the visible title text,
    preferring <div class="text-sm font-medium">.
    """
    try:
        title_node = link_el.locator('div.text-sm.font-medium').first
        return title_node.inner_text(timeout=2000).strip()
    except Exception:
        # fallback: attribute → full anchor text
        t = link_el.get_attribute(
            "title") or link_el.get_attribute("aria-label")
        if not t:
            t = link_el.inner_text(timeout=5000)
        return re.sub(r"\s+", " ", (t or "")).strip()


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

# ---------------------------------main function-------------------------


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
        # Prefer project links first; else sidebar
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

        # --- NEW: snapshot the list so locators don't go stale after nav ---
        items = snapshot_items(page, links)
        print(f"[info] Snapshot captured: {len(items)} items")

        # Scrape ALL currently visible items
        for n, it in enumerate(items, 1):
            print(
                f"\n[info] Opening {n}/{len(items)}: {it['href']}  |  title='{it['title']}'")
            # Prefer clicking the exact href; if not present (list re-render), just goto the absolute URL
            link = page.locator(f'a[href="{it["href"]}"]').first
            if link.count() > 0:
                link.scroll_into_view_if_needed()
                link.click()
            else:
                page.goto(it["abs_url"], wait_until="load")
            page.wait_for_load_state("load", timeout=8000)

            # Wait + scrape (your robust helper)
            markdown = wait_for_chat_and_markdown(page)
            if not markdown:
                print("[warn] Markdown empty after waits; skipping save.")
                # Try to go back anyway
                try:
                    page.go_back()
                    page.wait_for_load_state("load", timeout=8000)
                except Exception:
                    pass
                continue

            # Save
            out_path = save_markdown(markdown, it["slug"])
            print(f"[info] Saved: {out_path}")

            # Back to list for next item
            print("[info] Returning to list...")
            page.go_back()
            page.wait_for_load_state("load", timeout=8000)


if __name__ == "__main__":
    main()
