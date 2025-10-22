# scrape.py
# Attaches to your *already running* Chrome (launched with --remote-debugging-port=9222),
# finds the main container <div class="relative basis-auto flex-col grow grid">,
# and clicks the first chat link inside it.

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

CDP_ENDPOINT = "http://localhost:9222"
CONTAINER_SELECTOR = 'div.relative.basis-auto.flex-col.grow.grid'

# target <a class="w-full" ...> that points to /c/<id>
CHAT_LINKS_SELECTOR = 'a.w-full[href*="/c/"]'


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
        for i in range(2):
            chat_link = chat_links.nth(i)
            href = chat_link.get_attribute("href")
            print(f"[info] Opening chat {i+1}: {href}")
            chat_link.scroll_into_view_if_needed()
            chat_link.click()
            page.wait_for_load_state("networkidle", timeout=8000)

            # (simulate scraping later)
            print("[info] (pretend scraping markdown here)")

            # go back
            print("[info] Going back to chat list...")
            page.go_back()
            page.wait_for_load_state("networkidle", timeout=8000)

        # print("[info] Going back to chat list...")
        # page.wait_for_load_state("networkidle", timeout=5000)
        # page.go_back()
        # page.wait_for_load_state("networkidle", timeout=5000)
        # print("[info] Returned to chat list.")


if __name__ == "__main__":
    main()
