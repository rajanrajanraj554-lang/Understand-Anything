import type { Page } from 'playwright';
import type { CandidateProfile } from '../types.js';
import { fillCustomQuestions } from './common.js';

/** Fills an Ashby application form (jobs.ashbyhq.com/<company>/<id>). */
export async function fillAshbyForm(
  page: Page,
  profile: CandidateProfile,
  resumeText: string,
  apiKey: string,
  answeredQuestions: { question: string; answer: string }[],
): Promise<void> {
  await page.waitForSelector('form', { timeout: 15000 });

  await tryFillByLabel(page, /name/i, profile.fullName);
  await tryFillByLabel(page, /email/i, profile.email);
  await tryFillByLabel(page, /phone/i, profile.phone);
  await tryFillByLabel(page, /location/i, profile.location);
  await tryFillByLabel(page, /linkedin/i, profile.linkedinUrl);
  await tryFillByLabel(page, /github/i, profile.githubUrl);
  await tryFillByLabel(page, /portfolio|website/i, profile.portfolioUrl);

  const resumeInput = page.locator('input[type="file"]').first();
  if (await resumeInput.count()) {
    await resumeInput.setInputFiles(profile.resumePath);
  }

  await fillCustomQuestions(page, 'form', profile, resumeText, apiKey, answeredQuestions);
}

async function tryFillByLabel(page: Page, labelPattern: RegExp, value?: string) {
  if (!value) return;
  const label = page.getByText(labelPattern, { exact: false }).first();
  if (!(await label.count())) return;

  const input = label.locator(
    'xpath=following::input[1] | following::textarea[1]',
  );
  if (await input.count()) {
    await input.first().fill(value);
  }
}
