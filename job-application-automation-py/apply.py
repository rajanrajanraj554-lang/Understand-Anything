import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from captcha import check_for_captcha
from detect_ats import detect_ats
from forms.ashby import fill_ashby_form
from forms.greenhouse import fill_greenhouse_form
from forms.lever import fill_lever_form
from resume import extract_resume_text
from types_ import AnsweredQuestion, ApplicationResult, ApplyOptions

FILLERS = {
    "greenhouse": fill_greenhouse_form,
    "lever": fill_lever_form,
    "ashby": fill_ashby_form,
}


def apply_to_job(options: ApplyOptions) -> ApplicationResult:
    api_key = options.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing Anthropic API key. Pass anthropic_api_key or set "
            "ANTHROPIC_API_KEY."
        )

    ats = detect_ats(options.job_url)
    if ats == "unknown":
        raise RuntimeError(
            f"Could not identify an ATS (Greenhouse/Lever/Ashby) from URL: "
            f"{options.job_url}"
        )

    Path(options.output_dir).mkdir(parents=True, exist_ok=True)
    resume_text = extract_resume_text(options.profile.resume_path)

    notes: list[str] = []
    answered_questions: list[AnsweredQuestion] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not options.headed)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(options.job_url, wait_until="domcontentloaded")

            check_for_captcha(page, options.headed)

            FILLERS[ats](page, options.profile, resume_text, api_key, answered_questions)

            # Re-check: some ATS platforms only render the CAPTCHA after
            # fields are filled.
            check_for_captcha(page, options.headed)

            screenshot_path = str(
                Path(options.output_dir) / f"application-{int(time.time() * 1000)}.png"
            )
            page.screenshot(path=screenshot_path, full_page=True)

            submitted = False
            if options.dry_run:
                notes.append(
                    "Dry run: form filled and screenshotted, submit button "
                    "NOT clicked."
                )
            else:
                submit_button = page.locator(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Submit")'
                ).first
                submit_button.click()
                try:
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass
                submitted = True
                notes.append("Submit button clicked.")

            return ApplicationResult(
                ats=ats,
                submitted=submitted,
                screenshot_path=screenshot_path,
                answered_questions=answered_questions,
                notes=notes,
            )
        finally:
            browser.close()
