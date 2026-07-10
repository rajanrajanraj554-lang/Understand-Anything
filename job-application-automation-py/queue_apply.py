import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, sync_playwright

from captcha import CaptchaBlockedError, detect_captcha, wait_for_captcha_clear
from detect_ats import detect_ats
from resume import extract_resume_text
from smart_form import fill_form_smart, upload_resume_and_cover_letter
from types_ import AnsweredQuestion, QueueItemResult, QueueOptions


@dataclass
class _PendingItem:
    result: QueueItemResult
    page: Optional[Page]


def run_queue(options: QueueOptions) -> list[QueueItemResult]:
    """Queue mode: fills every job in `job_urls` back-to-back in a visible
    browser, one tab per job. Anything blocked by a CAPTCHA is left open
    rather than making you sit and watch it — you solve those (and review
    everything else) in a single batch pass at the end, one tab at a time,
    deciding per application whether to submit.

    This is still "a human clears every CAPTCHA" — it just lets you do that
    clearing/reviewing in one sitting instead of interrupting the fill of
    each job individually. See README for why this tool never solves a
    CAPTCHA itself.
    """
    api_key = options.ai_api_key or os.environ.get(
        "GROQ_API_KEY" if options.ai_provider == "groq" else "ANTHROPIC_API_KEY"
    )
    if not api_key:
        raise RuntimeError(
            "Missing AI API key. Pass ai_api_key or set ANTHROPIC_API_KEY / "
            "GROQ_API_KEY depending on ai_provider."
        )
    if not options.job_urls:
        return []

    Path(options.output_dir).mkdir(parents=True, exist_ok=True)
    resume_text = extract_resume_text(options.profile.resume_path)

    pending: list[_PendingItem] = []

    with sync_playwright() as p:
        # Queue mode is fundamentally "a human reviews/solves in one
        # sitting" -- that only makes sense with a visible browser.
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context()

            print(f"\n=== Fill pass: {len(options.job_urls)} job(s) ===\n")

            for job_url in options.job_urls:
                pending.append(_fill_one(context, job_url, options, resume_text, api_key))

            _review_pass(pending, options.captcha_timeout_seconds)

            return [item.result for item in pending]
        finally:
            browser.close()


def _fill_one(context, job_url, options, resume_text, api_key) -> _PendingItem:
    answered_questions: list[AnsweredQuestion] = []
    notes: list[str] = []
    ats = detect_ats(job_url)  # informational only

    page = context.new_page()
    try:
        page.goto(job_url, wait_until="domcontentloaded")

        upload_resume_and_cover_letter(page, options.profile)
        fill_form_smart(
            page,
            options.profile,
            resume_text,
            api_key,
            answered_questions,
            options.ai_provider,
            options.ai_model,
        )

        captcha_kind = detect_captcha(page)
        screenshot_path = str(
            Path(options.output_dir) / f"queue-{_sanitize(job_url)}.png"
        )
        page.screenshot(path=screenshot_path, full_page=True)

        if captcha_kind:
            notes.append(f"{captcha_kind} detected — left open for the review pass.")

        print(
            f"[filled] {job_url}"
            + (f"  (needs CAPTCHA solve: {captcha_kind})" if captcha_kind else "")
        )

        return _PendingItem(
            page=page,
            result=QueueItemResult(
                job_url=job_url,
                ats=ats,
                status="skipped",  # placeholder until the review pass decides
                needed_captcha=bool(captcha_kind),
                screenshot_path=screenshot_path,
                answered_questions=answered_questions,
                notes=notes,
            ),
        )
    except Exception as err:  # noqa: BLE001 - surface any failure per-item
        page.close()
        print(f"[failed] {job_url} — {err}")
        return _PendingItem(
            page=None,
            result=QueueItemResult(
                job_url=job_url,
                ats=ats,
                status="failed",
                needed_captcha=False,
                answered_questions=answered_questions,
                notes=notes,
                error=str(err),
            ),
        )


def _review_pass(pending: list[_PendingItem], captcha_timeout_seconds: int) -> None:
    reviewable = [item for item in pending if item.page is not None]
    if not reviewable:
        return

    print(f"\n=== Review pass: {len(reviewable)} application(s) ===")
    print("For each one: solve any CAPTCHA in the tab, review the filled fields,")
    print("then answer the prompt to submit or skip.\n")

    for item in reviewable:
        page = item.page
        result = item.result

        page.bring_to_front()
        print(f"\n--- {result.job_url} ({result.ats}) ---")
        for qa in result.answered_questions:
            print(f"  Q: {qa.question}\n  A: {qa.answer}")
        if result.screenshot_path:
            print(f"  screenshot: {result.screenshot_path}")

        if result.needed_captcha:
            print("  Solve the CAPTCHA in this tab now...")
            try:
                wait_for_captcha_clear(page, "CAPTCHA", captcha_timeout_seconds)
            except CaptchaBlockedError as err:
                result.status = "captcha-timeout"
                result.notes.append(str(err))
                print("  Timed out waiting for CAPTCHA — skipping this one.")
                page.close()
                continue

        answer = input("  Submit this application? [y/N/skip] ").strip().lower()

        if answer in ("y", "yes"):
            try:
                submit_button = page.locator(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Submit")'
                ).first
                submit_button.click()
                try:
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass
                result.status = "submitted"
                result.notes.append("Submit button clicked.")
                print("  Submitted.")
            except Exception as err:  # noqa: BLE001
                result.status = "failed"
                result.error = str(err)
                print(f"  Submit failed: {err}")
        else:
            result.status = "skipped"
            print("  Skipped.")

        page.close()


def _sanitize(url: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", url)[:80]
