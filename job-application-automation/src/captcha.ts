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

/**
 * Detects (but never attempts to solve) common CAPTCHA challenges. If one is
 * present and the browser is running headless, there is no human available
 * to clear it, so we fail loudly instead of trying to work around it.
 */
export async function checkForCaptcha(page: Page, headed: boolean): Promise<void> {
  const hcaptcha = await page.locator('iframe[src*="hcaptcha.com"]').count();
  const recaptcha = await page.locator('iframe[src*="recaptcha"]').count();
  const cloudflareTurnstile = await page
    .locator('iframe[src*="challenges.cloudflare.com"]')
    .count();

  const kind = hcaptcha
    ? 'hCaptcha'
    : recaptcha
      ? 'reCAPTCHA'
      : cloudflareTurnstile
        ? 'Cloudflare Turnstile'
        : null;

  if (!kind) return;

  if (!headed) {
    throw new CaptchaBlockedError(kind);
  }

  // Headed mode: pause and hand control to the human running the script.
  console.warn(
    `\n[captcha] ${kind} detected. Please solve it manually in the open ` +
      'browser window. The script will resume once it disappears (checking ' +
      'every 2s, up to 5 minutes).\n',
  );

  const deadline = Date.now() + 5 * 60_000;
  while (Date.now() < deadline) {
    const stillPresent =
      (await page.locator('iframe[src*="hcaptcha.com"]').count()) ||
      (await page.locator('iframe[src*="recaptcha"]').count()) ||
      (await page.locator('iframe[src*="challenges.cloudflare.com"]').count());
    if (!stillPresent) return;
    await page.waitForTimeout(2000);
  }

  throw new CaptchaBlockedError(`${kind} (not solved within 5 minutes)`);
}
