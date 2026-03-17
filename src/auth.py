"""Browser-based Canvas authentication using Playwright.

Logs in via AUC's Microsoft SSO, handles 2FA,
and caches session cookies for reuse.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.config import settings

logger = logging.getLogger(__name__)

COOKIES_FILE = Path("canvas_cookies.json")


def get_canvas_token() -> str:
    """Get a Canvas API token or session cookies.

    Priority:
    1. CANVAS_API_TOKEN env var (if set)
    2. CANVAS_COOKIES_B64 env var (for cloud deployment)
    3. Cached cookies from file (local)
    4. Fresh browser login (requires 2FA approval)
    """
    if settings.canvas_api_token:
        logger.info("Using provided API token")
        return settings.canvas_api_token

    # Try base64-encoded cookies from env var (cloud deployment)
    cookies_b64 = settings.canvas_cookies_b64
    if cookies_b64:
        import base64
        cookies_json = base64.b64decode(cookies_b64).decode()
        cookies = json.loads(cookies_json)
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        logger.info("Using cookies from CANVAS_COOKIES_B64 env var (%d cookies)", len(cookie_dict))
        return "cookies:" + json.dumps(cookie_dict)

    # Try cached cookies from file
    cached = _load_cached_cookies()
    if cached:
        logger.info("Using cached session cookies")
        return cached

    if not settings.canvas_email or not settings.canvas_password:
        raise ValueError(
            "Either CANVAS_API_TOKEN, CANVAS_COOKIES_B64, or CANVAS_EMAIL+CANVAS_PASSWORD must be set. "
            "Or run: python -m src.auth_setup to do interactive login."
        )

    logger.info("No cached cookies found. Starting interactive login...")
    return _login_microsoft_sso(headless=False)


def setup_interactive() -> None:
    """Run interactive login with visible browser for 2FA approval.

    Call this once to cache cookies. Run with:
        python -m src.auth_setup
    """
    if not settings.canvas_email or not settings.canvas_password:
        raise ValueError("CANVAS_EMAIL and CANVAS_PASSWORD must be set in .env")

    print(f"\nLogging in as {settings.canvas_email}...")
    print("A browser window will open. Approve the 2FA request on your phone.\n")

    token = _login_microsoft_sso(headless=False)

    if token.startswith("cookies:"):
        print("\n✅ Login successful! Session cookies saved to canvas_cookies.json")
        print("The bot can now run without 2FA until the session expires.")
        print("If it stops working, run this again: python -m src.auth_setup")
    else:
        print("\n✅ Login successful with API token!")


def _login_microsoft_sso(headless: bool = True) -> str:
    """Log into Canvas via AUC's Microsoft Azure AD SSO."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Go to Canvas SAML login — redirects to Microsoft
        logger.info("Navigating to Canvas SAML login...")
        page.goto(
            f"{settings.canvas_api_url}/login/saml",
            wait_until="networkidle",
            timeout=30000,
        )

        # Step 2: Enter email on Microsoft login page
        logger.info("Entering email...")
        email_input = page.wait_for_selector(
            'input[type="email"], input[name="loginfmt"]',
            timeout=15000,
        )
        email_input.fill(settings.canvas_email)
        page.click('input[type="submit"]')
        page.wait_for_timeout(2000)

        # Step 3: Enter password
        logger.info("Entering password...")
        password_input = page.wait_for_selector(
            'input[type="password"], input[name="passwd"]',
            timeout=15000,
        )
        password_input.fill(settings.canvas_password)
        page.click('input[type="submit"]')

        # Step 4: Wait for 2FA approval (up to 2 minutes)
        if not headless:
            print("\n⏳ Waiting for 2FA approval... Check your Microsoft Authenticator app!")

        logger.info("Waiting for 2FA approval (up to 120 seconds)...")

        # Wait until we either get past 2FA or land on Canvas
        try:
            page.wait_for_url(
                lambda url: "instructure.com" in url or "aucegypt.edu" in url,
                timeout=120000,  # 2 minutes for 2FA
            )
        except Exception:
            # Maybe there's a "Stay signed in?" prompt
            pass

        # Step 5: Handle "Stay signed in?" prompt if it appears
        try:
            page.wait_for_selector(
                '#idBtn_Back, input[value="Yes"], input[value="No"]',
                timeout=5000,
            )
            logger.info("Handling 'Stay signed in?' prompt...")
            # Click "Yes" to stay signed in (longer session)
            try:
                page.click('input[value="Yes"]', timeout=3000)
            except Exception:
                page.click('#idBtn_Back', timeout=3000)
        except Exception:
            pass

        # Step 6: Wait for Canvas
        logger.info("Waiting for Canvas redirect...")
        try:
            page.wait_for_url(
                lambda url: "instructure.com" in url or "aucegypt.edu" in url,
                timeout=30000,
            )
        except Exception:
            page.screenshot(path="/tmp/sso_debug.png")
            logger.error("Current URL: %s", page.url)
            browser.close()
            raise RuntimeError(
                f"Failed to reach Canvas after login. Stuck at: {page.url}. "
                "Screenshot saved to /tmp/sso_debug.png"
            )

        logger.info("Logged in! Current URL: %s", page.url)

        # Step 7: Verify we can reach Canvas API
        page.goto(
            f"{settings.canvas_api_url}/api/v1/users/self",
            wait_until="networkidle",
            timeout=15000,
        )

        # Step 8: Extract and cache cookies
        cookies = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        browser.close()

        if not cookie_dict:
            raise RuntimeError("Failed to extract session cookies after SSO login")

        # Save cookies for reuse
        _save_cookies(cookies)

        logger.info("Successfully extracted %d cookies", len(cookie_dict))
        return "cookies:" + json.dumps(cookie_dict)


def _load_cached_cookies() -> str | None:
    """Load cached cookies if they exist and are likely still valid."""
    if not COOKIES_FILE.exists():
        return None
    try:
        cookies = json.loads(COOKIES_FILE.read_text())
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        if not cookie_dict:
            return None
        logger.info("Loaded %d cached cookies from %s", len(cookie_dict), COOKIES_FILE)
        return "cookies:" + json.dumps(cookie_dict)
    except Exception as e:
        logger.warning("Failed to load cached cookies: %s", e)
        return None


def _save_cookies(cookies: list[dict]) -> None:
    """Save browser cookies to file for reuse."""
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    logger.info("Saved %d cookies to %s", len(cookies), COOKIES_FILE)
