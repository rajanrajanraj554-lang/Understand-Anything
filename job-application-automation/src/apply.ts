import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import { checkForCaptcha } from './captcha.js';
import { detectAts } from './detectAts.js';
import { fillAshbyForm } from './forms/ashby.js';
import { fillGreenhouseForm } from './forms/greenhouse.js';
import { fillLeverForm } from './forms/lever.js';
import { extractResumeText } from './resume.js';
import type { ApplicationResult, ApplyOptions } from './types.js';

export async function applyToJob(options: ApplyOptions): Promise<ApplicationResult> {
  const apiKey = options.anthropicApiKey ?? process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      'Missing Anthropic API key. Pass anthropicApiKey or set ANTHROPIC_API_KEY.',
    );
  }

  const ats = detectAts(options.jobUrl);
  if (ats === 'unknown') {
    throw new Error(
      `Could not identify an ATS (Greenhouse/Lever/Ashby) from URL: ${options.jobUrl}`,
    );
  }

  await mkdir(options.outputDir, { recursive: true });
  const resumeText = await extractResumeText(options.profile.resumePath);

  const browser = await chromium.launch({ headless: !options.headed });
  const notes: string[] = [];
  const answeredQuestions: { question: string; answer: string }[] = [];

  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(options.jobUrl, { waitUntil: 'domcontentloaded' });

    await checkForCaptcha(page, options.headed);

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

    // Re-check: some ATS platforms only render the CAPTCHA after fields are filled.
    await checkForCaptcha(page, options.headed);

    const screenshotPath = path.join(
      options.outputDir,
      `application-${Date.now()}.png`,
    );
    await page.screenshot({ path: screenshotPath, fullPage: true });

    let submitted = false;
    if (options.dryRun) {
      notes.push('Dry run: form filled and screenshotted, submit button NOT clicked.');
    } else {
      const submitButton = page
        .locator(
          'button[type="submit"], input[type="submit"], button:has-text("Submit")',
        )
        .first();
      await submitButton.click();
      await page.waitForLoadState('networkidle').catch(() => undefined);
      submitted = true;
      notes.push('Submit button clicked.');
    }

    return { ats, submitted, screenshotPath, answeredQuestions, notes };
  } finally {
    await browser.close();
  }
}
