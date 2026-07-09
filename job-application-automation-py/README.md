# job-application-automation-py

Python port of `job-application-automation` (the TypeScript/Playwright
version lives alongside this one at `../job-application-automation`). Opens
a job posting URL, reads whatever application form is actually there —
no per-platform CSS selectors — hands its fields to an LLM (Claude or Groq)
to fill, uploads your resume, and, only if you explicitly ask it to,
submits.

## Install

```bash
cd job-application-automation-py
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Set an API key for whichever provider you use: `ANTHROPIC_API_KEY` (default,
`--provider anthropic`) or `GROQ_API_KEY` (`--provider groq`). You can also
pass the key programmatically via `ApplyOptions.ai_api_key` /
`QueueOptions.ai_api_key`.

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

# or, using Groq instead of Claude:
python cli.py "https://jobs.lever.co/acme/abc123" profile.json --headed --provider groq --model llama-3.3-70b-versatile
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

1. **Fill pass** — opens a tab per job URL, uploads your resume, fills
   whatever fields the AI can confidently answer, screenshots each, and
   notes which ones have a CAPTCHA. Nothing blocks here; it just moves to
   the next job.
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

## How the smart form-filling works (no hardcoded selectors)

There's no `if ats == "greenhouse"` branch and no per-platform CSS
selectors. Instead, `smart_form.py`:

1. **Scans** whatever the page actually contains (`scan_fields`): every
   fillable `<input>`/`<textarea>`/`<select>` in DOM order, each described
   by its label (resolved from `<label for>`, `aria-label`, `placeholder`,
   or a wrapping/preceding `<label>` — whichever is actually present), its
   type, and its options if it's a `<select>` or radio group. The field's
   position in that scan (`index`) *is* its identifier — no CSS selector is
   ever constructed, so there's nothing to keep in sync with a platform's
   markup.
2. **Asks the model** (`ai.fill_form_fields`) to map each field index to a
   value, given your resume and profile. It's instructed to skip anything
   it doesn't have enough information for, and to skip legally-sensitive
   demographic/EEO questions outright so a human answers those.
3. **Applies** the returned mapping by index (`apply_ai_field_mapping`) —
   `.fill()` for text, `.select_option(label=...)` for selects, `.check()`
   for checkboxes — and records every field it touched as an
   `AnsweredQuestion` so you can review it before submitting.

File uploads are handled separately from the AI mapping, since a model
can't hand a browser a file path — `upload_resume_and_cover_letter` finds
`input[type=file]` elements generically and disambiguates resume vs. cover
letter by label text when there's more than one.

This means the same code path works against Greenhouse, Lever, Ashby, or
any other ATS's form — `detect_ats.py` is kept only to label results for
your own reference, nothing branches on it.

## Design choices you should know about

**Dry run is the default, not an afterthought.** Submitting a job
application is a real action with a human on the other end reading it — a
bad AI-drafted answer or a mis-filled field goes out under your name. Review
before you send.

**This tool does not solve, bypass, or evade detection for CAPTCHAs, and it
does not run in a "stealth"/fingerprint-spoofed/undetectable configuration.**
hCaptcha / reCAPTCHA / Cloudflare Turnstile are anti-bot controls that
Greenhouse, Lever, Ashby, or their customers put in front of these forms
specifically to stop scripted submissions — and their terms of service
generally restrict scripted or bulk submissions outright. Making the
automation harder to detect doesn't change what defeating that control
would be; it's still circumventing a system's access control without the
operator's consent, just quieter about it. `captcha.py` only *detects* a
challenge:

- in headed mode it pauses and waits (`wait_for_captcha_clear`) for a human
  to clear it in the visible window, then continues;
- in headless mode it raises `CaptchaBlockedError` rather than attempting a
  bypass.

If you find yourself wanting headless/stealth mode specifically to get past
a CAPTCHA unattended, that's a sign the target explicitly doesn't want
automated submissions — respect that rather than routing around it. Queue
mode (above) is the supported way to make manually clearing several
CAPTCHAs less tedious, by batching the review instead of automating away
the human step.

**Use this for your own applications, not mass/bulk spam.** It's built for a
candidate applying to jobs they're genuinely interested in and reviewing
each one, not for blasting out hundreds of near-identical applications.
Employers and other applicants are on the other end of this.

## How it works

- `detect_ats.py` — identifies Greenhouse / Lever / Ashby from the URL, for
  labeling results only; nothing branches on it.
- `smart_form.py` — generic field scanning, AI-mapping application, and
  resume/cover-letter upload. See above.
- `ai.py` — provider-agnostic LLM calls (Anthropic or Groq): drafts answers
  to standalone questions (`answer_question`) and produces the field→value
  mapping for `smart_form` (`fill_form_fields`). Never invents experience
  beyond what's in your resume/profile; skips sensitive demographic
  questions.
- `captcha.py` — detects (never solves) CAPTCHA challenges; exposes a
  non-blocking `detect_captcha` and a blocking `wait_for_captcha_clear`
  used by both single-apply and queue mode.
- `apply.py` — single-job orchestrator; screenshot + dry-run gate before any
  submit click.
- `queue_apply.py` / `cli_queue.py` — multi-job orchestrator: fills every
  job in a list, then runs one batch review pass (solve CAPTCHA / submit /
  skip per job) across all the open tabs.
- `resume.py` — extracts text from a PDF (via `pypdf`) or plain-text resume
  for the AI.

## Known limitations

- The AI only fills fields it's confident about from your resume/profile;
  anything it skips (insufficient info, ambiguous label, demographic/EEO
  questions) is left for you to fill in during the headed review before
  submitting.
- Field labels are resolved heuristically (`<label for>` → `aria-label` →
  `placeholder` → wrapping/preceding `<label>` → field `name`). A form with
  none of those on a given control will show up with an empty label, which
  the model will usually just skip.
- Multi-step application flows (fields revealed after a click) aren't
  followed automatically — re-run against the same page after advancing a
  step, or extend `smart_form.py` to loop until no new fields appear.
- Resume text extraction only handles PDF and plain text.
