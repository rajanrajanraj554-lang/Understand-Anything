import Anthropic from '@anthropic-ai/sdk';
import type { CandidateProfile } from './types.js';

/**
 * Answers a single free-text application question using the candidate's
 * resume and profile context. Always returns a draft answer — the caller is
 * responsible for giving the candidate a chance to review it before it's
 * submitted anywhere (see ApplyOptions.dryRun).
 */
export async function answerQuestion(
  question: string,
  profile: CandidateProfile,
  resumeText: string,
  apiKey: string,
): Promise<string> {
  const override = findOverride(question, profile.answerOverrides);
  if (override) {
    return override;
  }

  const client = new Anthropic({ apiKey });

  const message = await client.messages.create({
    model: 'claude-sonnet-5',
    max_tokens: 400,
    system:
      'You are drafting a first-person answer to a job application question ' +
      'on behalf of a candidate. Use only facts present in the resume/context ' +
      'below — never invent experience, dates, employers, or skills that are ' +
      'not supported by them. Keep the answer concise (2-5 sentences unless ' +
      'the question clearly calls for a short factual reply, e.g. years of ' +
      'experience or a yes/no). Respond with only the answer text, no preamble.',
    messages: [
      {
        role: 'user',
        content: [
          `Resume:\n${resumeText}`,
          profile.context ? `Additional context:\n${profile.context}` : '',
          `Application question:\n${question}`,
        ]
          .filter(Boolean)
          .join('\n\n'),
      },
    ],
  });

  const textBlock = message.content.find((block) => block.type === 'text');
  return textBlock && textBlock.type === 'text' ? textBlock.text.trim() : '';
}

function findOverride(
  question: string,
  overrides?: Record<string, string>,
): string | undefined {
  if (!overrides) return undefined;
  const normalized = question.toLowerCase();
  for (const [key, value] of Object.entries(overrides)) {
    if (normalized.includes(key.toLowerCase())) {
      return value;
    }
  }
  return undefined;
}
