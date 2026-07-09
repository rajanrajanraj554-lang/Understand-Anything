# job-application-automation-py

Python port of `job-application-automation` (the TypeScript/Playwright
version lives alongside this one at `../job-application-automation`; both
implement the same tool, this one just uses Playwright's Python API and the
Anthropic Python SDK). Opens a job posting URL, detects the ATS (Greenhouse,
Lever, or Ashby), fills in your profile fields and resume, drafts answers to
open-ended application questions with an LLM, and — only if you explicitly
ask it to — submits.

## Install

```bash
cd job-application-automation-py
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Set `ANTHROPIC_API_KEY` in your environment (or pass it via
`ApplyOptions.anthropic_api_key` / `QueueOptions.anthropic_api_key`).

## Usage

```bash
cp profile.example.json profile.json   # fill in your real details + resume path
python cli.py "https://boards.greenhouse.io/acme/jobs/123456" profile.json --headed
```

This does a **dry run** by default: it fills the form, drafts answers to
custom questions, and saves a screenshot to `./out/` — it does **not** click
submit. Read the screenshot and the answers printed to stdout. If they look
right, re-run with `--submit` added to actually send that one application:

```bash
python cli.py "https://boards.greenhouse.io/acme/jobs/123456" profile.json --headed --submit
```

## Queue mode (batch review)

Fills a list of job URLs back-to-back, leaves anything blocked by a CAPTCHA
open in its own tab, then walks you through a single review pass at the end
where you solve CAPTCHAs and decide submit/skip per application, one after
another, in one sitting.

```bash
cp urls.example.txt urls.txt   # one job URL per line
cp profile.example.json profile.json
python cli_queue.py urls.txt profile.json
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
solves in one sitting," which needs a visible browser.

## Design choices you should know about

**Dry run is the default, not an afterthought.** Submitting a job
application is a real action with a human on the other end reading it — a
bad AI-drafted answer or a mis-filled field goes out under your name. Review
before you send.

**This tool does not solve or bypass CAPTCHAs**, and headed (visible
browser), not headless/"invisible," is the recommended mode. hCaptcha /
reCAPTCHA / Cloudflare Turnstile are anti-bot controls that Greenhouse,
Lever, and Ashby (or their customers) put in front of these forms
specifically to stop scripted submissions, and Greenhouse/Lever/Ashby's
terms of service generally restrict scripted or bulk submissions. `captcha.py`
only *detects* a challenge:

- in headed mode it pauses and waits (`wait_for_captcha_clear`) for a human
  to clear it in the visible window, then continues;
- in headless mode it raises `CaptchaBlockedError` rather than attempting a
  bypass.

If you find yourself wanting headless mode specifically to get past a
CAPTCHA unattended, that's a sign the target explicitly doesn't want
automated submissions — respect that rather than routing around it.

**Use this for your own applications, not mass/bulk spam.** It's built for a
candidate applying to jobs they're genuinely interested in and reviewing
each one, not for blasting out hundreds of near-identical applications.
Employers and other applicants are on the other end of this.

## How it works

- `detect_ats.py` — identifies Greenhouse / Lever / Ashby from the URL.
- `forms/{greenhouse,lever,ashby}.py` — fill known fields (name, email,
  phone, links, resume/cover-letter upload) for each platform.
- `forms/common.py` — finds labelled fields not covered by the known ones
  (i.e. custom application questions) and routes them to the AI.
- `ai.py` — drafts an answer to a custom question from your resume text and
  `profile.context` / `answer_overrides`, via the Claude API. It's
  instructed not to invent experience beyond what's in your resume.
- `captcha.py` — detects (never solves) CAPTCHA challenges; exposes a
  non-blocking `detect_captcha` and a blocking `wait_for_captcha_clear`
  used by both single-apply and queue mode.
- `apply.py` — single-job orchestrator; screenshot + dry-run gate before any
  submit click.
- `queue_apply.py` / `cli_queue.py` — multi-job orchestrator: fills every
  job in a list, then runs one batch review pass (solve CAPTCHA / submit /
  skip per job) across all the open tabs.
- `resume.py` — extracts text from a PDF (via `pypdf`) or plain-text resume
  for the AI answerer.

## Known limitations

- Selectors are based on each platform's common DOM structure as of
  writing; individual job postings can add custom fields, multi-step flows,
  or platform redesigns that these selectors won't match. Always eyeball
  the dry-run screenshot.
- `fill_custom_questions` only handles single-line/textarea text questions,
  not dropdowns, checkboxes, or multi-select EEO/demographic questions —
  fill those yourself in the headed browser before submitting.
- Resume text extraction only handles PDF and plain text.
