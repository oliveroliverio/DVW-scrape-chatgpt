# scrape.py
# Attaches to your *already running* Chrome (launched with --remote-debugging-port=9222),
# finds the main container <div class="relative basis-auto flex-col grow grid">,
# and clicks the first chat link inside it.

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

CDP_ENDPOINT = "http://localhost:9222"
CONTAINER_SELECTOR = 'div.relative.basis-auto.flex-col.grow.grid'
# Chat items usually navigate to /c/<id>
CHAT_LINKS_SELECTOR = 'a[href^="/c/"]'


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
        first_item = chat_links.first
        first_item.scroll_into_view_if_needed()
        first_item.click()
        print("[info] Clicked the first chat item.")


if __name__ == "__main__":
    main()
