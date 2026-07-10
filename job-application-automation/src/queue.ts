import { mkdir } from 'node:fs/promises';
import { createInterface } from 'node:readline/promises';
import path from 'node:path';
import { chromium, type Page } from 'playwright';
import { detectCaptcha, waitForCaptchaClear, CaptchaBlockedError } from './captcha.js';
import { detectAts } from './detectAts.js';
import { fillAshbyForm } from './forms/ashby.js';
import { fillGreenhouseForm } from './forms/greenhouse.js';
import { fillLeverForm } from './forms/lever.js';
import { extractResumeText } from './resume.js';
import type { QueueItemResult, QueueOptions } from './types.js';

interface PendingItem {
  result: QueueItemResult;
  page: Page | null;
}

/**
 * Queue mode: fills every job in `jobUrls` back-to-back in a visible
 * browser, one tab per job. Anything blocked by a CAPTCHA is left open
 * rather than making you sit and watch it — you solve those (and review
 * everything else) in a single batch pass at the end, one tab at a time,
 * deciding per application whether to submit.
 *
 * This is still "a human clears every CAPTCHA" — it just lets you do all
 * that clearing/reviewing in one sitting instead of interrupting the fill
 * of each job individually. See README for why this tool never solves a
 * CAPTCHA itself.
 */
export async function runQueue(options: QueueOptions): Promise<QueueItemResult[]> {
  const apiKey = options.anthropicApiKey ?? process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      'Missing Anthropic API key. Pass anthropicApiKey or set ANTHROPIC_API_KEY.',
    );
  }
  if (options.jobUrls.length === 0) {
    return [];
  }

  await mkdir(options.outputDir, { recursive: true });
  const resumeText = await extractResumeText(options.profile.resumePath);
  const captchaTimeoutMs = (options.captchaTimeoutSeconds ?? 300) * 1000;

  // Queue mode is fundamentally "a human reviews/solves in one sitting" —
  // that only makes sense with a visible browser.
  const browser = await chromium.launch({ headless: false });
  const pending: PendingItem[] = [];

  try {
    const context = await browser.newContext();

    console.log(`\n=== Fill pass: ${options.jobUrls.length} job(s) ===\n`);

    for (const jobUrl of options.jobUrls) {
      const answeredQuestions: { question: string; answer: string }[] = [];
      const notes: string[] = [];
      const ats = detectAts(jobUrl);

      if (ats === 'unknown') {
        pending.push({
          page: null,
          result: {
            jobUrl,
            ats,
            status: 'failed',
            neededCaptcha: false,
            answeredQuestions,
            notes,
            error: 'Could not identify an ATS (Greenhouse/Lever/Ashby) from URL.',
          },
        });
        console.log(`[skip] ${jobUrl} — unrecognized ATS`);
        continue;
      }

      const page = await context.newPage();
      try {
        await page.goto(jobUrl, { waitUntil: 'domcontentloaded' });

        switch (ats) {
          case 'greenhouse':
            await fillGreenhouseForm(page, options.profile, resumeText, apiKey, answeredQuestions);
            break;
          case 'lever':
            await fillLeverForm(page, options.profile, resumeText, apiKey, answeredQuestions);
            break;
          case 'ashby':
            await fillAshbyForm(page, options.profile, resumeText, apiKey, answeredQuestions);
            break;
        }

        const captchaKind = await detectCaptcha(page);
        const screenshotPath = path.join(
          options.outputDir,
          `queue-${sanitize(jobUrl)}.png`,
        );
        await page.screenshot({ path: screenshotPath, fullPage: true });

        if (captchaKind) {
          notes.push(`${captchaKind} detected — left open for the review pass.`);
        }

        pending.push({
          page,
          result: {
            jobUrl,
            ats,
            status: 'skipped', // placeholder until the review pass decides
            neededCaptcha: Boolean(captchaKind),
            screenshotPath,
            answeredQuestions,
            notes,
          },
        });

        console.log(
          `[filled] ${jobUrl}${captchaKind ? `  (needs CAPTCHA solve: ${captchaKind})` : ''}`,
        );
      } catch (err) {
        await page.close().catch(() => undefined);
        pending.push({
          page: null,
          result: {
            jobUrl,
            ats,
            status: 'failed',
            neededCaptcha: false,
            answeredQuestions,
            notes,
            error: err instanceof Error ? err.message : String(err),
          },
        });
        console.log(`[failed] ${jobUrl} — ${err instanceof Error ? err.message : err}`);
      }
    }

    await reviewPass(pending, captchaTimeoutMs);

    return pending.map((p) => p.result);
  } finally {
    await browser.close();
  }
}

async function reviewPass(pending: PendingItem[], captchaTimeoutMs: number): Promise<void> {
  const reviewable = pending.filter((p) => p.page);
  if (reviewable.length === 0) return;

  console.log(`\n=== Review pass: ${reviewable.length} application(s) ===`);
  console.log('For each one: solve any CAPTCHA in the tab, review the filled fields,');
  console.log('then answer the prompt to submit or skip.\n');

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  try {
    for (const item of reviewable) {
      const page = item.page!;
      const { jobUrl, ats, answeredQuestions } = item.result;

      await page.bringToFront();
      console.log(`\n--- ${jobUrl} (${ats}) ---`);
      for (const qa of answeredQuestions) {
        console.log(`  Q: ${qa.question}\n  A: ${qa.answer}`);
      }
      if (item.result.screenshotPath) {
        console.log(`  screenshot: ${item.result.screenshotPath}`);
      }

      if (item.result.neededCaptcha) {
        console.log('  Solve the CAPTCHA in this tab now...');
        try {
          await waitForCaptchaClear(page, 'CAPTCHA', captchaTimeoutMs);
        } catch (err) {
          if (err instanceof CaptchaBlockedError) {
            item.result.status = 'captcha-timeout';
            item.result.notes.push(err.message);
            console.log(`  Timed out waiting for CAPTCHA — skipping this one.`);
            await page.close().catch(() => undefined);
            continue;
          }
          throw err;
        }
      }

      const answer = (
        await rl.question('  Submit this application? [y/N/skip] ')
      )
        .trim()
        .toLowerCase();

      if (answer === 'y' || answer === 'yes') {
        try {
          const submitButton = page
            .locator(
              'button[type="submit"], input[type="submit"], button:has-text("Submit")',
            )
            .first();
          await submitButton.click();
          await page.waitForLoadState('networkidle').catch(() => undefined);
          item.result.status = 'submitted';
          item.result.notes.push('Submit button clicked.');
          console.log('  Submitted.');
        } catch (err) {
          item.result.status = 'failed';
          item.result.error = err instanceof Error ? err.message : String(err);
          console.log(`  Submit failed: ${item.result.error}`);
        }
      } else {
        item.result.status = 'skipped';
        console.log('  Skipped.');
      }

      await page.close().catch(() => undefined);
    }
  } finally {
    rl.close();
  }
}

function sanitize(url: string): string {
  return url.replace(/[^a-z0-9]+/gi, '-').slice(0, 80);
}
