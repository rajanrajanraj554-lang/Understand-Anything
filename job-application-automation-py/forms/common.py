from playwright.sync_api import Locator, Page

from ai import answer_question
from types_ import AnsweredQuestion, CandidateProfile

KNOWN_FIELD_LABELS = (
    "first name",
    "last name",
    "full name",
    "email",
    "phone",
    "resume",
    "resume/cv",
    "cover letter",
    "linkedin",
    "website",
    "github",
    "location",
)


def fill_custom_questions(
    page: Page,
    scope: str,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    answered_questions: list[AnsweredQuestion],
) -> None:
    """Finds application questions that aren't covered by our known
    name/email/phone/resume fields, drafts an answer for each via AI, and
    fills it in. Works against any container of labelled text inputs /
    textareas, which covers Greenhouse, Lever, and Ashby's custom-question
    sections closely enough in practice; selectors are intentionally loose
    since every job posting defines its own custom fields.
    """
    fields = page.locator(
        f'{scope} label:has(~ textarea), {scope} label:has(~ input[type="text"])'
    )
    count = fields.count()

    for i in range(count):
        label = fields.nth(i)
        question_text = (label.text_content() or "").strip()
        if not question_text or _is_known_field(question_text):
            continue

        field_input = _find_associated_input(page, label)
        if field_input is None:
            continue

        already_filled = field_input.input_value() or ""
        if already_filled:
            continue

        answer = answer_question(question_text, profile, resume_text, api_key)
        if not answer:
            continue

        field_input.fill(answer)
        answered_questions.append(AnsweredQuestion(question=question_text, answer=answer))


def _is_known_field(label: str) -> bool:
    normalized = label.lower()
    return any(known in normalized for known in KNOWN_FIELD_LABELS)


def _find_associated_input(page: Page, label: Locator) -> Locator | None:
    for_attr = label.get_attribute("for")
    if for_attr:
        escaped = for_attr.replace('"', '\\"')
        by_id = page.locator(f'[id="{escaped}"]')
        if by_id.count() > 0:
            return by_id.first

    sibling = label.locator(
        "xpath=following-sibling::textarea[1] | following-sibling::input[1]"
    )
    if sibling.count() > 0:
        return sibling.first

    return None
