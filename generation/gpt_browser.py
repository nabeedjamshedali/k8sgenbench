"""GPT slot via the ChatGPT web UI, driven by Playwright in the researcher's own logged-in Chrome session.

The researcher logs in by hand in the window this opens; the script never handles credentials. Each prompt goes to a
fresh Temporary Chat (no memory, no custom instructions), is sent once with no follow-up, and the reply is copied with
ChatGPT's own copy button (raw markdown) into relay/inbox/gpt/<project>__<variant>__s<k>.txt for relay.py import.
If a CAPTCHA / bot challenge appears the script STOPS: challenges are never circumvented (same rule as DeepSeek).

Usage: python generation/gpt_browser.py trial      one prompt (the first missing), then stop
       python generation/gpt_browser.py all        every missing sample, in relay order
Stop early: create generation/relay/.gpt_stop
"""
import datetime
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import relay

RELAY = relay.RELAY
INBOX = RELAY / "inbox" / "gpt"
# Dedicated Chrome profile holding only this ChatGPT login; kept OUTSIDE the project so session cookies can never
# end up in the replication package.
PROFILE = Path.home() / ".k8sgen_chatgpt_profile"
STOP = RELAY / ".gpt_stop"
LOG = RELAY / "gpt_browser_log.jsonl"
URL = "https://chatgpt.com/?temporary-chat=true"
LOGIN_TIMEOUT_S, REPLY_TIMEOUT_S, PAUSE_S = 900, 900, 30


def say(msg):
    print(f"{datetime.datetime.now():%H:%M:%S} {msg}", flush=True)


def challenged(page):
    """True if a bot check is showing (Cloudflare interstitial or a CAPTCHA frame)."""
    try:
        title = (page.title() or "").lower()
        if "just a moment" in title or "attention required" in title:
            return True
        for f in page.frames:
            if any(h in (f.url or "") for h in ("challenges.cloudflare.com", "captcha", "arkoselabs", "funcaptcha")):
                return True
        body = page.locator("body").inner_text(timeout=2000).lower()
        return "verify you are human" in body or "unusual activity" in body
    except Exception:
        return False


def jobs():
    return [(p, v, k) for p in relay.PROJECTS for v in relay.VARIANTS for k in relay.SAMPLES
            if not (INBOX / f"{p}__{v}__s{k}.txt").exists()]


def wait_for_composer(ctx, page, timeout_s):
    """Wait until a logged-in composer is visible. Follows the newest chatgpt.com tab if the login flow (popup,
    redirect) closes or replaces the original one. Returns (state, page)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if page.is_closed():
                live = [p for p in ctx.pages if not p.is_closed()]
                if not live:
                    return "browser_closed", page
                page = next((p for p in reversed(live) if "chatgpt.com" in p.url), live[-1])
            if challenged(page):
                return "challenge", page
            box = page.locator("#prompt-textarea")
            if box.count() and box.first.is_visible() and page.get_by_role("button", name="Log in").count() == 0:
                return "ready", page
        except Exception as e:  # page navigating or closed mid-check: retry on the next tick
            if "closed" in str(e).lower() and not [p for p in ctx.pages if not p.is_closed()]:
                return "browser_closed", page
        time.sleep(2)
    return "timeout", page


def model_label(page):
    for sel in ('[data-testid="model-switcher-dropdown-button"]', 'button[aria-haspopup="menu"]'):
        try:
            t = page.locator(sel).first.inner_text(timeout=2000).strip()
            if t:
                return t.replace("\n", " ")[:80]
        except Exception:
            pass
    return None


def run_one(page, p, v, k):
    prompt = (RELAY / "prompts" / f"{p}__{v}.txt").read_text(encoding="utf-8")
    page.goto(URL, wait_until="domcontentloaded")
    state, page = wait_for_composer(page.context, page, 120)
    if state != "ready":
        return {"status": state}
    temporary = "temporary-chat=true" in page.url
    box = page.locator("#prompt-textarea").first
    box.click()
    page.keyboard.insert_text(prompt)  # one paste-like insertion, not typed keystrokes
    time.sleep(2)
    n_before = page.locator('[data-message-author-role="assistant"]').count()
    send = page.locator('[data-testid="send-button"]')
    send.wait_for(state="visible", timeout=60000)
    send.click()
    t0 = time.time()
    # done = a new assistant turn exists, the stop button is gone and the composer's send/voice control is back
    deadline = t0 + REPLY_TIMEOUT_S
    started = False
    while time.time() < deadline:
        if STOP.exists():
            return {"status": "stopped"}
        if challenged(page):
            return {"status": "challenge"}
        stop_visible = page.locator('[data-testid="stop-button"]').count() > 0
        if stop_visible:
            started = True
        n_now = page.locator('[data-message-author-role="assistant"]').count()
        if n_now > n_before and not stop_visible and (started or time.time() - t0 > 20):
            time.sleep(3)
            if page.locator('[data-testid="stop-button"]').count() == 0:
                break
        time.sleep(2)
    else:
        return {"status": "reply_timeout"}
    turn = page.locator('[data-message-author-role="assistant"]').last
    text, via = None, None
    try:  # ChatGPT's own copy button yields the raw markdown (code fences intact)
        page.locator('[data-testid="copy-turn-action-button"]').last.click(timeout=10000)
        time.sleep(1)
        text, via = page.evaluate("navigator.clipboard.readText()"), "copy_button"
    except Exception:
        pass
    if not text:
        text, via = turn.inner_text(), "inner_text"
    out = INBOX / f"{p}__{v}__s{k}.txt"
    out.write_text(text, encoding="utf-8")
    return {"status": "ok", "chars": len(text), "via": via, "seconds": round(time.time() - t0, 1),
            "temporary_chat": temporary, "model_label": model_label(page)}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "trial"
    INBOX.mkdir(parents=True, exist_ok=True)
    STOP.unlink(missing_ok=True)
    todo = jobs()
    say(f"{len(todo)} samples missing; mode={mode}")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False, no_viewport=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://chatgpt.com")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        say("LOGIN_NEEDED: log in to ChatGPT in the Chrome window (the script waits up to 15 min)")
        state, page = wait_for_composer(ctx, page, LOGIN_TIMEOUT_S)
        if state != "ready":
            say(f"STOP: {state} before login completed" + (" (bot challenge; not circumvented)" if state == "challenge" else ""))
            ctx.close()
            return
        say(f"logged in; model shown: {model_label(page)}")
        for i, (p, v, k) in enumerate(todo[:1] if mode == "trial" else todo):
            if STOP.exists():
                say("stop file found")
                break
            say(f"[{i + 1}] {p} {v} s{k}: sending")
            res = run_one(page, p, v, k)
            rec = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "project": p, "variant": v,
                   "sample": k, **res}
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            say(f"[{i + 1}] {p} {v} s{k}: {res}")
            if res["status"] != "ok":
                say("STOP: " + ("bot challenge appeared; not circumvented" if res["status"] == "challenge" else res["status"]))
                break
            time.sleep(PAUSE_S)
        say("DONE")
        time.sleep(5)
        ctx.close()


if __name__ == "__main__":
    main()
