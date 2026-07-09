import type { Page } from 'playwright';
import type { CandidateProfile } from '../types.js';
import { fillCustomQuestions } from './common.js';

/** Fills a Lever application form (jobs.lever.co/<company>/<id>/apply). */
export async function fillLeverForm(
  page: Page,
  profile: CandidateProfile,
  resumeText: string,
  apiKey: string,
  answeredQuestions: { question: string; answer: string }[],
): Promise<void> {
  await page.waitForSelector('form.application-form, form[data-qa="btn-apply"]', {
    timeout: 15000,
  });

  await tryFill(page, 'input[name="name"]', profile.fullName);
  await tryFill(page, 'input[name="email"]', profile.email);
  await tryFill(page, 'input[name="phone"]', profile.phone);
  await tryFill(page, 'input[name="org"]', profile.location);
  await tryFill(page, 'input[name="urls[LinkedIn]"]', profile.linkedinUrl);
  await tryFill(page, 'input[name="urls[GitHub]"]', profile.githubUrl);
  await tryFill(page, 'input[name="urls[Portfolio]"]', profile.portfolioUrl);

  const resumeInput = page.locator('input[name="resume"][type="file"]').first();
  if (await resumeInput.count()) {
    await resumeInput.setInputFiles(profile.resumePath);
  }

  await fillCustomQuestions(page, 'form.application-form', profile, resumeText, apiKey, answeredQuestions);
}

async function tryFill(page: Page, selector: string, value?: string) {
  if (!value) return;
  const el = page.locator(selector).first();
  if (await el.count()) {
    await el.fill(value);
  }
}
