from playwright.sync_api import Page

from types_ import AnsweredQuestion, CandidateProfile

from .common import fill_custom_questions


def fill_lever_form(
    page: Page,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    answered_questions: list[AnsweredQuestion],
) -> None:
    """Fills a Lever application form (jobs.lever.co/<company>/<id>/apply)."""
    page.wait_for_selector(
        'form.application-form, form[data-qa="btn-apply"]', timeout=15000
    )

    _try_fill(page, 'input[name="name"]', profile.full_name)
    _try_fill(page, 'input[name="email"]', profile.email)
    _try_fill(page, 'input[name="phone"]', profile.phone)
    _try_fill(page, 'input[name="org"]', profile.location)
    _try_fill(page, 'input[name="urls[LinkedIn]"]', profile.linkedin_url)
    _try_fill(page, 'input[name="urls[GitHub]"]', profile.github_url)
    _try_fill(page, 'input[name="urls[Portfolio]"]', profile.portfolio_url)

    resume_input = page.locator('input[name="resume"][type="file"]').first
    if resume_input.count() > 0:
        resume_input.set_input_files(profile.resume_path)

    fill_custom_questions(
        page,
        "form.application-form",
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
