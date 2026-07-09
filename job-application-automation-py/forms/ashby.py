import re

from playwright.sync_api import Page

from types_ import AnsweredQuestion, CandidateProfile

from .common import fill_custom_questions


def fill_ashby_form(
    page: Page,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    answered_questions: list[AnsweredQuestion],
) -> None:
    """Fills an Ashby application form (jobs.ashbyhq.com/<company>/<id>)."""
    page.wait_for_selector("form", timeout=15000)

    _try_fill_by_label(page, re.compile("name", re.I), profile.full_name)
    _try_fill_by_label(page, re.compile("email", re.I), profile.email)
    _try_fill_by_label(page, re.compile("phone", re.I), profile.phone)
    _try_fill_by_label(page, re.compile("location", re.I), profile.location)
    _try_fill_by_label(page, re.compile("linkedin", re.I), profile.linkedin_url)
    _try_fill_by_label(page, re.compile("github", re.I), profile.github_url)
    _try_fill_by_label(
        page, re.compile("portfolio|website", re.I), profile.portfolio_url
    )

    resume_input = page.locator('input[type="file"]').first
    if resume_input.count() > 0:
        resume_input.set_input_files(profile.resume_path)

    fill_custom_questions(
        page, "form", profile, resume_text, api_key, answered_questions
    )


def _try_fill_by_label(page: Page, label_pattern: re.Pattern, value: str | None) -> None:
    if not value:
        return
    label = page.get_by_text(label_pattern).first
    if label.count() == 0:
        return

    field_input = label.locator(
        "xpath=following::input[1] | following::textarea[1]"
    )
    if field_input.count() > 0:
        field_input.first.fill(value)
