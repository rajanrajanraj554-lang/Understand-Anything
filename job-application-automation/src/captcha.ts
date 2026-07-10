import type { Page } from 'playwright';

export class CaptchaBlockedError extends Error {
  constructor(kind: string) {
    super(
      `A ${kind} challenge was detected on this application. This tool does ` +
        'not solve or bypass CAPTCHAs — that would defeat an anti-bot control ' +
        'the site put there on purpose, likely violating the employer\'s / ' +
        'ATS\'s terms of service. Re-run with `--headed` and solve it yourself ' +
        'in the visible browser window, then let the script continue.',
    );
    this.name = 'CaptchaBlockedError';
  }
}

/** Detects a CAPTCHA challenge without waiting on it. Returns the kind, or null. */
export async function detectCaptcha(page: Page): Promise<string | null> {
  const hcaptcha = await page.locator('iframe[src*="hcaptcha.com"]').count();
  if (hcaptcha) return 'hCaptcha';

  const recaptcha = await page.locator('iframe[src*="recaptcha"]').count();
  if (recaptcha) return 'reCAPTCHA';

  const cloudflareTurnstile = await page
    .locator('iframe[src*="challenges.cloudflare.com"]')
    .count();
  if (cloudflareTurnstile) return 'Cloudflare Turnstile';

  return null;
}

/**
 * Blocks until a previously-detected CAPTCHA disappears (i.e. a human solved
 * it in this same visible browser window), polling every 2s up to
 * `timeoutMs`. Never attempts to solve it itself.
 */
export async function waitForCaptchaClear(
  page: Page,
  kind: string,
  timeoutMs = 5 * 60_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const stillPresent = await detectCaptcha(page);
    if (!stillPresent) return;
    await page.waitForTimeout(2000);
  }
  throw new CaptchaBlockedError(`${kind} (not solved within ${Math.round(timeoutMs / 1000)}s)`);
}

/**
 * Detects (but never attempts to solve) common CAPTCHA challenges. If one is
 * present and the browser is running headless, there is no human available
 * to clear it, so we fail loudly instead of trying to work around it. In
 * headed mode, pauses and waits for a human to clear it in this window.
 */
export async function checkForCaptcha(page: Page, headed: boolean): Promise<void> {
  const kind = await detectCaptcha(page);
  if (!kind) return;

  if (!headed) {
    throw new CaptchaBlockedError(kind);
  }

  console.warn(
    `\n[captcha] ${kind} detected. Please solve it manually in the open ` +
      'browser window. The script will resume once it disappears (checking ' +
      'every 2s, up to 5 minutes).\n',
  );

  await waitForCaptchaClear(page, kind);
}
