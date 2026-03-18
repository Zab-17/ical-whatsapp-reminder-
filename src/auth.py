"""Browser-based Canvas authentication using Playwright."""
from __future__ import annotations

import logging

from playwright.sync_api import sync_playwright

from src.config import settings

logger = logging.getLogger(__name__)


def login_and_get_cookies(email: str, password: str) -> list[dict]:
    """Log into Canvas via AUC's Microsoft SSO and return cookies."""
    logger.info("Logging in via Microsoft SSO as %s...", email)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Canvas SAML login → Microsoft
        page.goto(f"{settings.canvas_api_url}/login/saml", wait_until="networkidle", timeout=30000)

        # Step 2: Enter email
        email_input = page.wait_for_selector('input[type="email"], input[name="loginfmt"]', timeout=15000)
        email_input.fill(email)
        page.click('input[type="submit"]')
        page.wait_for_timeout(2000)

        # Step 3: Enter password
        password_input = page.wait_for_selector('input[type="password"], input[name="passwd"]', timeout=15000)
        password_input.fill(password)
        page.click('input[type="submit"]')

        # Step 4: Wait for 2FA (up to 2 minutes)
        logger.info("Waiting for 2FA approval...")
        try:
            page.wait_for_url(
                lambda url: "instructure.com" in url or "aucegypt.edu" in url,
                timeout=120000,
            )
        except Exception:
            pass

        # Step 5: Handle "Stay signed in?"
        try:
            page.wait_for_selector('#idBtn_Back, input[value="Yes"]', timeout=5000)
            try:
                page.click('input[value="Yes"]', timeout=3000)
            except Exception:
                page.click('#idBtn_Back', timeout=3000)
        except Exception:
            pass

        # Step 6: Wait for Canvas
        try:
            page.wait_for_url(
                lambda url: "instructure.com" in url or "aucegypt.edu" in url,
                timeout=30000,
            )
        except Exception:
            browser.close()
            raise RuntimeError("Login failed — could not reach Canvas after SSO. Check credentials.")

        # Step 7: Verify API access
        page.goto(f"{settings.canvas_api_url}/api/v1/users/self", wait_until="networkidle", timeout=15000)

        # Step 8: Extract cookies
        cookies = context.cookies()
        browser.close()

        if not cookies:
            raise RuntimeError("No cookies captured after login")

        logger.info("Login successful, captured %d cookies", len(cookies))
        return cookies
