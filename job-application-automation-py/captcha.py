import time

from playwright.sync_api import Page

CAPTCHA_SELECTORS = {
    "hCaptcha": 'iframe[src*="hcaptcha.com"]',
    "reCAPTCHA": 'iframe[src*="recaptcha"]',
    "Cloudflare Turnstile": 'iframe[src*="challenges.cloudflare.com"]',
}


class CaptchaBlockedError(Exception):
    def __init__(self, kind: str):
        super().__init__(
            f"A {kind} challenge was detected on this application. This tool "
            "does not solve or bypass CAPTCHAs — that would defeat an anti-bot "
            "control the site put there on purpose, likely violating the "
            "employer's / ATS's terms of service. Re-run with headed=True and "
            "solve it yourself in the visible browser window, then let the "
            "script continue."
        )
        self.kind = kind


def detect_captcha(page: Page) -> str | None:
    """Detects a CAPTCHA challenge without waiting on it. Returns the kind, or None."""
    for kind, selector in CAPTCHA_SELECTORS.items():
        if page.locator(selector).count() > 0:
            return kind
    return None


def wait_for_captcha_clear(page: Page, kind: str, timeout_seconds: float = 300) -> None:
    """Blocks until a previously-detected CAPTCHA disappears (i.e. a human
    solved it in this same visible browser window), polling every 2s up to
    `timeout_seconds`. Never attempts to solve it itself.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not detect_captcha(page):
            return
        page.wait_for_timeout(2000)
    raise CaptchaBlockedError(f"{kind} (not solved within {int(timeout_seconds)}s)")


def check_for_captcha(page: Page, headed: bool) -> None:
    """Detects (but never attempts to solve) common CAPTCHA challenges. If one
    is present and the browser is running headless, there is no human
    available to clear it, so we fail loudly instead of trying to work around
    it. In headed mode, pauses and waits for a human to clear it in this
    window.
    """
    kind = detect_captcha(page)
    if not kind:
        return

    if not headed:
        raise CaptchaBlockedError(kind)

    print(
        f"\n[captcha] {kind} detected. Please solve it manually in the open "
        "browser window. The script will resume once it disappears (checking "
        "every 2s, up to 5 minutes).\n"
    )

    wait_for_captcha_clear(page, kind)
