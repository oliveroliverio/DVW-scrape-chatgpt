# scrape.py
# Attaches to your *already running* Chrome (launched with --remote-debugging-port=9222),
# finds the main container <div class="relative basis-auto flex-col grow grid">,
# and clicks the first chat link inside it.

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import re
from datetime import datetime
import time
from pathlib import Path
import unicodedata
import subprocess
import requests
from urllib.parse import urljoin, urlparse

CDP_ENDPOINT = "http://localhost:9222"
CONTAINER_SELECTOR = 'div.relative.basis-auto.flex-col.grow.grid'
# target <a class="w-full" ...> that points to /c/<id>
CHAT_LINKS_SELECTOR = 'a.w-full[href*="/c/"]'
PROJECT_LINKS_SELECTOR = 'section ol li a[href]'
CHAT_DOWNLOAD_DIR = './Downloaded_Chats'

# -----------------------helper functions---------------------------


def safe_go_back_to_list(page, list_selector: str, list_url: str) -> None:
    """
    Go back to the list view without hanging on SPA routes.
    Strategy:
      1) go_back(wait_until='commit') — don't wait for 'load'
      2) wait for list selector (anchors)
      3) if that fails, hard goto the captured list_url
    """
    # Try a light-weight history back (no 'load' wait)
    try:
        page.go_back(wait_until="commit", timeout=5000)
    except PWTimeoutError:
        print("[warn] go_back() timeout; will try detecting list directly...")
    # Check if the list is actually visible
    try:
        page.wait_for_selector(list_selector, timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=4000)
        print("[info] List detected after back.")
        return
    except PWTimeoutError:
        print("[warn] List selector not found after back; reloading list URL...")

    # Fallback: hard navigate back to list URL
    page.goto(list_url, wait_until="domcontentloaded", timeout=10000)
    page.wait_for_selector(list_selector, timeout=8000)
    print("[info] List detected after goto(list_url).")


def download_images_with_browser_session(page, markdown_content, markdown_file_path):
    """Download images using the browser's authenticated session"""
    try:
        # Create z-img directory within CHAT_DOWNLOAD_DIR if it doesn't exist
        chat_dir = Path(CHAT_DOWNLOAD_DIR)
        z_img_dir = chat_dir / "z-img"
        z_img_dir.mkdir(parents=True, exist_ok=True)

        # Extract title from markdown for naming
        title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r'[^a-zA-Z0-9\s-]', '', title)
            title = re.sub(r'\s+', '_', title).lower()
        else:
            title = 'chatgpt_conversation'

        # Find image URLs in markdown (fig_ pattern)
        image_pattern = r'!\[fig_[^\]]*\]\(([^)]+)\)'
        images_found = re.findall(image_pattern, markdown_content)

        if not images_found:
            print(f"[info] No ChatGPT images found in {markdown_file_path}")
            return markdown_content

        print(f"[info] Found {len(images_found)} images to download")

        # Get browser cookies for authenticated requests
        cookies = {}
        for cookie in page.context.cookies():
            cookies[cookie['name']] = cookie['value']

        # Download each image and update markdown
        updated_content = markdown_content

        for i, url in enumerate(images_found):
            if not url.startswith('http'):
                continue

            try:
                print(
                    f"[info] Downloading image {i+1}/{len(images_found)}: {url}")

                # Generate filename
                timestamp = datetime.now().isoformat().replace(':', '-').replace('.', '-')
                parsed_url = urlparse(url)
                extension = '.jpg'  # default
                if '.png' in url:
                    extension = '.png'
                elif '.webp' in url:
                    extension = '.webp'
                elif '.gif' in url:
                    extension = '.gif'
                elif '.svg' in url:
                    extension = '.svg'

                filename = f"{title}_fig_{timestamp}{extension}"
                local_path = z_img_dir / filename

                # Download with authenticated session
                response = requests.get(url, cookies=cookies, timeout=30)

                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)

                    # Update markdown content
                    relative_path = f"z-img/{filename}"
                    updated_content = updated_content.replace(
                        url, relative_path)
                    print(f"[info] ✅ Downloaded and updated: {filename}")
                else:
                    print(
                        f"[warn] ❌ Failed to download {url}: {response.status_code}")

            except Exception as e:
                print(f"[error] Failed to download {url}: {e}")
                continue

        return updated_content

    except Exception as e:
        print(f"[error] Image download process failed: {e}")
        return markdown_content


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
    Saves markdown to CHAT_DOWNLOAD_DIR/{slug}_{YYMMDD_HHMMSS}.md
    """
    out_dir = Path(CHAT_DOWNLOAD_DIR)
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

        list_url = page.url  # remember the list page to fall back to later

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

            markdown = download_images_with_browser_session(
                page, markdown, it["slug"])

            # Save
            out_path = save_markdown(markdown, it["slug"])
            print(f"[info] Saved: {out_path}")

            # Back to list for next item
            print("[info] Returning to list...")
            safe_go_back_to_list(
                page,
                list_selector=PROJECT_LINKS_SELECTOR if proj_count > 0 else CHAT_LINKS_SELECTOR,
                list_url=list_url,
            )


if __name__ == "__main__":
    main()
