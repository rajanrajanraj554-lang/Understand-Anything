import type { Page } from 'playwright';
import type { CandidateProfile } from '../types.js';
import { fillCustomQuestions } from './common.js';

/** Fills a Greenhouse embedded application form (job-boards.greenhouse.io / boards.greenhouse.io). */
export async function fillGreenhouseForm(
  page: Page,
  profile: CandidateProfile,
  resumeText: string,
  apiKey: string,
  answeredQuestions: { question: string; answer: string }[],
): Promise<void> {
  await page.waitForSelector('#application_form, form#application-form', { timeout: 15000 });

  await tryFill(page, '#first_name', profile.firstName);
  await tryFill(page, '#last_name', profile.lastName);
  await tryFill(page, '#email', profile.email);
  await tryFill(page, '#phone', profile.phone);

  const resumeInput = page.locator('#resume, input[name="resume"][type="file"]').first();
  if (await resumeInput.count()) {
    await resumeInput.setInputFiles(profile.resumePath);
  }

  if (profile.coverLetterPath) {
    const coverInput = page.locator('#cover_letter, input[name="cover_letter"][type="file"]').first();
    if (await coverInput.count()) {
      await coverInput.setInputFiles(profile.coverLetterPath);
    }
  }

  if (profile.linkedinUrl) {
    await tryFill(page, 'input[name*="linked" i]', profile.linkedinUrl);
  }
  if (profile.portfolioUrl) {
    await tryFill(page, 'input[name*="website" i], input[name*="portfolio" i]', profile.portfolioUrl);
  }

  await fillCustomQuestions(page, '#application_form, form#application-form', profile, resumeText, apiKey, answeredQuestions);
}

async function tryFill(page: Page, selector: string, value?: string) {
  if (!value) return;
  const el = page.locator(selector).first();
  if (await el.count()) {
    await el.fill(value);
  }
}
