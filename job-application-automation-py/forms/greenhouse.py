from playwright.sync_api import Page

from types_ import AnsweredQuestion, CandidateProfile

from .common import fill_custom_questions


def fill_greenhouse_form(
    page: Page,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    answered_questions: list[AnsweredQuestion],
) -> None:
    """Fills a Greenhouse embedded application form
    (job-boards.greenhouse.io / boards.greenhouse.io)."""
    page.wait_for_selector(
        "#application_form, form#application-form", timeout=15000
    )

    _try_fill(page, "#first_name", profile.first_name)
    _try_fill(page, "#last_name", profile.last_name)
    _try_fill(page, "#email", profile.email)
    _try_fill(page, "#phone", profile.phone)

    resume_input = page.locator('#resume, input[name="resume"][type="file"]').first
    if resume_input.count() > 0:
        resume_input.set_input_files(profile.resume_path)

    if profile.cover_letter_path:
        cover_input = page.locator(
            '#cover_letter, input[name="cover_letter"][type="file"]'
        ).first
        if cover_input.count() > 0:
            cover_input.set_input_files(profile.cover_letter_path)

    if profile.linkedin_url:
        _try_fill(page, 'input[name*="linked" i]', profile.linkedin_url)
    if profile.portfolio_url:
        _try_fill(
            page,
            'input[name*="website" i], input[name*="portfolio" i]',
            profile.portfolio_url,
        )

    fill_custom_questions(
        page,
        "#application_form, form#application-form",
        profile,
        resume_text,
        api_key,
        answered_questions,
    )


def _try_fill(page: Page, selector: str, value: str | None) -> None:
    if not value:
        return
    el = page.locator(selector).first
    if el.count() > 0:
        el.fill(value)
