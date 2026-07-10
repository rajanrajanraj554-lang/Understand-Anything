export type AtsPlatform = 'greenhouse' | 'lever' | 'ashby' | 'unknown';

export interface CandidateProfile {
  fullName: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  location?: string;
  linkedinUrl?: string;
  portfolioUrl?: string;
  githubUrl?: string;
  resumePath: string;
  coverLetterPath?: string;
  /**
   * Optional exact-match overrides for specific application questions,
   * keyed by a lowercase substring of the question text. Checked before
   * falling back to the AI answerer.
   */
  answerOverrides?: Record<string, string>;
  /** Freeform facts fed to the AI when answering open-ended questions. */
  context?: string;
}

export interface ApplyOptions {
  jobUrl: string;
  profile: CandidateProfile;
  /**
   * When true (default), the form is filled and screenshotted but never
   * submitted. Set to false only once you've reviewed a dry run and want
   * this specific application actually sent.
   */
  dryRun: boolean;
  /**
   * Run with a visible browser window. Strongly recommended: keeps a human
   * in the loop for anything unexpected (extra fields, verification
   * challenges) and is more respectful of the target site's automation
   * policies. See README for why headless/"invisible" mode is deliberately
   * not the default here.
   */
  headed: boolean;
  outputDir: string;
  anthropicApiKey?: string;
}

export interface ApplicationResult {
  ats: AtsPlatform;
  submitted: boolean;
  screenshotPath: string;
  answeredQuestions: { question: string; answer: string }[];
  notes: string[];
}

export interface QueueOptions {
  jobUrls: string[];
  profile: CandidateProfile;
  outputDir: string;
  anthropicApiKey?: string;
  /**
   * Max seconds to wait for a human to clear a CAPTCHA on any one item
   * during the review pass before giving up on that item and moving on.
   */
  captchaTimeoutSeconds?: number;
}

export type QueueItemStatus =
  | 'submitted'
  | 'skipped'
  | 'failed'
  | 'captcha-timeout';

export interface QueueItemResult {
  jobUrl: string;
  ats: AtsPlatform;
  status: QueueItemStatus;
  neededCaptcha: boolean;
  screenshotPath?: string;
  answeredQuestions: { question: string; answer: string }[];
  notes: string[];
  error?: string;
}
