# Chrome Remote Debugging Setup (De-duplicated)

This guide ensures Chrome is running with remote debugging enabled and verifies the port connection.

---

## Step 2.5 — Ensure Chrome is Listening on a Debugging Port

1. **Fully quit Chrome** (⌘+Q). To guarantee all processes are closed, run:

   ```bash
   pkill -f "Google Chrome"; pkill -f "Chrome Helper"; pkill -f "GoogleUpdater" 2>/dev/null || true
   ```

2. **Relaunch Chrome with debugging enabled (using full binary path)**

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"        --remote-debugging-port=9222        --user-data-dir="$HOME/tmp_chrome_debug"
   ```

3. **Verify the port is open** — in the Chrome window you just opened, visit:

   ```bash
   http://localhost:9222/json/version
   ```

   - If successful, you’ll see JSON fields such as `"Browser"` and `"webSocketDebuggerUrl"`.
   - If you get a “refused” page, Chrome was not launched correctly — repeat Step 1.

4. **Optional: make port configurable via environment variable**

   Modify the top of your `scrape.py` file:

   ```python
   import os
   CDP_ENDPOINT = os.environ.get("CDP", "http://localhost:9222")
   ```

   This allows running with a different port, e.g.:

   ```bash
   CDP=http://localhost:9333 python3 scrape.py
   ```

---

## Step 2.6 — Full Reset and Verification (If Step 2.5 Fails)

If visiting `http://localhost:9222/json/version` still fails, perform this hard reset.

1. **Kill all Chrome processes**

   ```bash
   pkill -f "Google Chrome"; pkill -f "Chrome Helper" 2>/dev/null || true
   ```

   If you see “no such process,” that’s fine.

2. **Confirm Chrome is fully closed**

   ```bash
   pgrep -fil "Google Chrome" || echo "OK: no Chrome running"
   ```

   You should see: `OK: no Chrome running`

3. **Relaunch Chrome with debugging enabled (using your normal profile)**

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"        --remote-debugging-port=9222        --profile-directory="Default"
   ```

   - If it opens with missing extensions/bookmarks, try other profiles:
     - `--profile-directory="Profile 1"`
     - `--profile-directory="Profile 2"`

   You can confirm your current profile name at `chrome://version → Profile Path`.

4. **Verify the debugging port**

   Visit in Chrome:

   ```bash
   http://localhost:9222/json/version
   ```

   If it still fails, try a different port (some corporate tools block 9222):

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"        --remote-debugging-port=9333        --profile-directory="Default"
   ```

   Then visit:

   ```bash
   http://localhost:9333/json/version
   ```

---

✅ **When you see the JSON page**, reply with:

- “Step 2.6 done”
- The working port number (`9222` or `9333`)
- The profile name used (`Default`, `Profile 1`, etc.)

Then you can continue to the next script setup step.
