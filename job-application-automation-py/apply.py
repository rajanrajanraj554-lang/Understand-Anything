import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from captcha import check_for_captcha
from detect_ats import detect_ats
from resume import extract_resume_text
from smart_form import fill_form_smart, upload_resume_and_cover_letter
from types_ import AnsweredQuestion, ApplicationResult, ApplyOptions


def apply_to_job(options: ApplyOptions) -> ApplicationResult:
    api_key = options.ai_api_key or os.environ.get(
        "GROQ_API_KEY" if options.ai_provider == "groq" else "ANTHROPIC_API_KEY"
    )
    if not api_key:
        raise RuntimeError(
            "Missing AI API key. Pass ai_api_key or set ANTHROPIC_API_KEY / "
            "GROQ_API_KEY depending on ai_provider."
        )

    ats = detect_ats(options.job_url)  # informational only; nothing below branches on it

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
