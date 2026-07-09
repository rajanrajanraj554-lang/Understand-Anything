import type { Page } from 'playwright';
import { answerQuestion } from '../ai.js';
import type { CandidateProfile } from '../types.js';

/**
 * Finds application questions that aren't covered by our known
 * name/email/phone/resume fields, drafts an answer for each via AI, and
 * fills it in. Works against any container of labelled text inputs /
 * textareas, which covers Greenhouse, Lever, and Ashby's custom-question
 * sections closely enough in practice; selectors are intentionally loose
 * since every job posting defines its own custom fields.
 */
export async function fillCustomQuestions(
  page: Page,
  scope: string,
  profile: CandidateProfile,
  resumeText: string,
  apiKey: string,
  answeredQuestions: { question: string; answer: string }[],
): Promise<void> {
  const fields = page.locator(
    `${scope} label:has(~ textarea), ${scope} label:has(~ input[type="text"])`,
  );
  const count = await fields.count();

  for (let i = 0; i < count; i++) {
    const label = fields.nth(i);
    const questionText = (await label.textContent())?.trim();
    if (!questionText || isKnownField(questionText)) continue;

    const input = await findAssociatedInput(page, label);
    if (!input) continue;

    const alreadyFilled = await input.inputValue().catch(() => '');
    if (alreadyFilled) continue;

    const answer = await answerQuestion(questionText, profile, resumeText, apiKey);
    if (!answer) continue;

    await input.fill(answer);
    answeredQuestions.push({ question: questionText, answer });
  }
}

function isKnownField(label: string): boolean {
  const normalized = label.toLowerCase();
  return [
    'first name',
    'last name',
    'full name',
    'email',
    'phone',
    'resume',
    'resume/cv',
    'cover letter',
    'linkedin',
    'website',
    'github',
    'location',
  ].some((known) => normalized.includes(known));
}

async function findAssociatedInput(page: Page, label: import('playwright').Locator) {
  const forAttr = await label.getAttribute('for');
  if (forAttr) {
    const byId = page.locator(`[id="${forAttr.replace(/"/g, '\\"')}"]`);
    if (await byId.count()) return byId.first();
  }
  const sibling = label.locator('xpath=following-sibling::textarea[1] | following-sibling::input[1]');
  if (await sibling.count()) return sibling.first();
  return null;
}
