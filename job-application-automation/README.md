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

## Queue mode (batch review)

Applying to several jobs one at a time means babysitting each CAPTCHA as it
comes up. Queue mode instead fills every job in a list back-to-back, leaves
anything blocked by a CAPTCHA open in its own tab, and then walks you
through a single review pass at the end where you solve CAPTCHAs and decide
submit/skip per application, one after another, in one sitting.

```bash
cp urls.example.txt urls.txt   # one job URL per line
cp profile.example.json profile.json
npm run apply-queue -- urls.txt profile.json
```

What happens:

1. **Fill pass** — opens a tab per job URL, fills known fields + resume,
   drafts answers to custom questions, screenshots each, and notes which
   ones have a CAPTCHA. Nothing blocks here; it just moves to the next job.
2. **Review pass** — goes tab by tab. For each: brings it to front, prints
   the drafted answers, and if that one needs a CAPTCHA, waits (up to
   `--captcha-timeout` seconds, default 300) for you to clear it in that
   window. Then it asks `Submit this application? [y/N/skip]` before doing
   anything. A `captcha-timeout` result just means you ran out of time on
   that one — it's skipped, not submitted.
3. Prints a summary line per job (`submitted` / `skipped` / `failed` /
   `captcha-timeout`).

Queue mode always runs headed — the whole feature is "a human reviews and
solves in one sitting," which needs a visible browser. It still never
solves a CAPTCHA for you; it only batches the waiting/reviewing so you're
not interrupted mid-fill for each one. See the design note below for why
that line matters.

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
- `src/captcha.ts` — detects (never solves) CAPTCHA challenges; exposes a
  non-blocking `detectCaptcha` and a blocking `waitForCaptchaClear` used by
  both single-apply and queue mode.
- `src/apply.ts` — single-job orchestrator; screenshot + dry-run gate before
  any submit click.
- `src/queue.ts` / `src/cliQueue.ts` — multi-job orchestrator: fills every
  job in a list, then runs one batch review pass (solve CAPTCHA / submit /
  skip per job) across all the open tabs.

## Known limitations

- Selectors are based on each platform's common DOM structure as of writing;
  individual job postings can add custom fields, multi-step flows, or
  platform redesigns that these selectors won't match. Always eyeball the
  dry-run screenshot.
- `fillCustomQuestions` only handles single-line/textarea text questions,
  not dropdowns, checkboxes, or multi-select EEO/demographic questions —
  fill those yourself in the headed browser before submitting.
- Resume text extraction only handles PDF and plain text.
