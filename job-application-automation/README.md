# job-application-automation

Playwright tool that opens a job posting URL, detects the ATS (Greenhouse,
Lever, or Ashby), fills in your profile fields and resume, drafts answers to
open-ended application questions with an LLM (Anthropic API), and — only if
you explicitly ask it to — submits.

## Install

```bash
cd job-application-automation
npm install
npx playwright install chromium
```

Set `ANTHROPIC_API_KEY` in your environment (or pass it programmatically via
`ApplyOptions.anthropicApiKey`).

## Usage

```bash
cp profile.example.json profile.json   # fill in your real details + resume path
npm run apply -- "https://boards.greenhouse.io/acme/jobs/123456" profile.json --headed
```

This does a **dry run** by default: it fills the form, drafts answers to
custom questions, and saves a screenshot to `./out/` — it does **not** click
submit. Read the screenshot and the answers printed to stdout. If they look
right, re-run with `--submit` added to actually send that one application:

```bash
npm run apply -- "https://boards.greenhouse.io/acme/jobs/123456" profile.json --headed --submit
```

## Design choices you should know about

**Dry run is the default, not an afterthought.** Submitting a job application
is a real action with a human on the other end reading it — a bad AI-drafted
answer or a mis-filled field goes out under your name. Review before you send.

**Headed, not headless/"invisible," is the intended mode.** The task this
tool was written for asked for invisible/headless automation with automatic
CAPTCHA handling. That combination — hiding automation from a site while
defeating the anti-bot challenge it serves you — is what CAPTCHAs exist to
stop, and it's very likely to violate the ATS's and/or the employer's terms
of service (Greenhouse, Lever, and Ashby's ToS generally restrict scripted or
bulk submissions). This tool intentionally:

- **defaults to a visible browser window**, so you're present as the actual
  applicant driving the session, and
- **does not solve or bypass CAPTCHAs.** `src/captcha.ts` only *detects*
  hCaptcha / reCAPTCHA / Cloudflare Turnstile. In headed mode it pauses and
  waits for you to solve the challenge yourself; in headless mode (which you
  have to opt out of `--headed` to get) it throws rather than attempting a
  bypass.

If you find yourself wanting headless mode specifically to get past a
CAPTCHA unattended, that's a sign the target explicitly doesn't want
automated submissions — respect that rather than routing around it.

**Use this for your own applications, not mass/bulk spam.** It's built for a
candidate applying to jobs they're genuinely interested in and reviewing
each one, not for blasting out hundreds of near-identical applications.
Employers and other applicants are on the other end of this.

## How it works

- `src/detectAts.ts` — identifies Greenhouse / Lever / Ashby from the URL.
- `src/forms/{greenhouse,lever,ashby}.ts` — fill known fields (name, email,
  phone, links, resume/cover-letter upload) for each platform.
- `src/forms/common.ts` — finds labelled fields not covered by the known
  ones (i.e. custom application questions) and routes them to the AI.
- `src/ai.ts` — drafts an answer to a custom question from your resume text
  and `profile.context`/`answerOverrides`, via the Claude API. It's
  instructed not to invent experience beyond what's in your resume.
- `src/captcha.ts` — detects (never solves) CAPTCHA challenges.
- `src/apply.ts` — orchestrates the above; screenshot + dry-run gate before
  any submit click.

## Known limitations

- Selectors are based on each platform's common DOM structure as of writing;
  individual job postings can add custom fields, multi-step flows, or
  platform redesigns that these selectors won't match. Always eyeball the
  dry-run screenshot.
- `fillCustomQuestions` only handles single-line/textarea text questions,
  not dropdowns, checkboxes, or multi-select EEO/demographic questions —
  fill those yourself in the headed browser before submitting.
- Resume text extraction only handles PDF and plain text.
