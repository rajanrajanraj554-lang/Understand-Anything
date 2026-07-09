from playwright.sync_api import Page

from ai import fill_form_fields
from types_ import AiProvider, AnsweredQuestion, CandidateProfile, FormField

# Anything that isn't free text/select/checkbox — handled separately (file
# uploads) or left for the human (submit/hidden/button controls).
_EXCLUDED_INPUT_TYPES = {"hidden", "file", "submit", "button", "reset", "image"}

_FILLABLE_SELECTOR = (
    "input:not([type=hidden]):not([type=file]):not([type=submit])"
    ":not([type=button]):not([type=reset]):not([type=image]), textarea, select"
)


def find_form_scope(page: Page) -> str:
    """Most application pages have exactly one <form>; fall back to the
    whole document if not, rather than guessing a platform-specific
    container.
    """
    return "form" if page.locator("form").count() > 0 else "body"


def scan_fields(page: Page, scope: str) -> list[FormField]:
    """Reads whatever fillable controls actually exist on the page, in DOM
    order, with no assumptions about which ATS rendered them. The returned
    list's `index` matches this same DOM order, so callers can map back to
    the exact Playwright locator with `.nth(index)` — no CSS selectors to
    keep in sync with any particular platform's markup.
    """
    controls = page.locator(f"{scope} {_FILLABLE_SELECTOR}")
    count = controls.count()

    fields: list[FormField] = []
    for i in range(count):
        control = controls.nth(i)
        tag = control.evaluate("el => el.tagName.toLowerCase()")
        input_type = (control.get_attribute("type") or "").lower() if tag == "input" else ""

        label = _label_for(page, control)
        required = control.get_attribute("required") is not None or (
            control.get_attribute("aria-required") or ""
        ).lower() == "true"

        options: list[str] = []
        if tag == "select":
            options = control.locator("option").all_inner_texts()
            options = [o.strip() for o in options if o.strip()]
        elif input_type == "radio":
            name = control.get_attribute("name")
            if name:
                group = page.locator(f'{scope} input[type="radio"][name="{_escape(name)}"]')
                for j in range(group.count()):
                    val = group.nth(j).get_attribute("value")
                    if val:
                        options.append(val)

        fields.append(
            FormField(
                index=i,
                label=label,
                tag=tag,
                input_type=input_type,
                options=options,
                required=required,
            )
        )

    return fields


def apply_ai_field_mapping(
    page: Page,
    scope: str,
    fields: list[FormField],
    mapping: dict[int, str | bool],
    answered_questions: list[AnsweredQuestion],
) -> None:
    controls = page.locator(f"{scope} {_FILLABLE_SELECTOR}")

    by_index = {f.index: f for f in fields}

    for index, value in mapping.items():
        field = by_index.get(index)
        if field is None:
            continue

        control = controls.nth(index)
        try:
            existing = control.input_value() if field.tag != "select" else None
        except Exception:
            existing = None
        if existing:
            continue  # don't clobber something already filled (e.g. pre-populated email)

        if field.tag == "select":
            control.select_option(label=str(value))
        elif field.input_type in ("checkbox", "radio"):
            if isinstance(value, str):
                value = value.strip().lower() in ("true", "yes", "1")
            if value:
                control.check()
        else:
            control.fill(str(value))

        if field.label:
            answered_questions.append(AnsweredQuestion(question=field.label, answer=str(value)))


def fill_form_smart(
    page: Page,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    answered_questions: list[AnsweredQuestion],
    ai_provider: AiProvider = "anthropic",
    ai_model: str | None = None,
) -> None:
    """Identifies whatever form is on the page, describes its fields to the
    AI (label/type/options — no hardcoded per-platform selectors), and fills
    in whatever the model returns a confident answer for.
    """
    scope = find_form_scope(page)
    fields = scan_fields(page, scope)
    mapping = fill_form_fields(fields, profile, resume_text, api_key, ai_provider, ai_model)
    apply_ai_field_mapping(page, scope, fields, mapping, answered_questions)


def upload_resume_and_cover_letter(page: Page, profile: CandidateProfile) -> None:
    """Finds file-upload inputs generically (there are rarely more than one
    or two) and disambiguates resume vs. cover letter by label text rather
    than a platform-specific selector.
    """
    file_inputs = page.locator('input[type="file"]')
    count = file_inputs.count()
    if count == 0:
        return

    if count == 1:
        file_inputs.first.set_input_files(profile.resume_path)
        return

    for i in range(count):
        control = file_inputs.nth(i)
        label = _label_for(page, control).lower()
        if profile.cover_letter_path and (
            "cover" in label or "letter" in label
        ):
            control.set_input_files(profile.cover_letter_path)
        elif "resume" in label or "cv" in label or not label:
            control.set_input_files(profile.resume_path)


def _label_for(page: Page, control) -> str:
    for_attr = control.get_attribute("id")
    if for_attr:
        label = page.locator(f'label[for="{_escape(for_attr)}"]').first
        if label.count() > 0:
            text = (label.text_content() or "").strip()
            if text:
                return text

    aria = control.get_attribute("aria-label")
    if aria:
        return aria.strip()

    placeholder = control.get_attribute("placeholder")
    if placeholder:
        return placeholder.strip()

    wrapping_label = control.locator("xpath=ancestor::label[1]")
    if wrapping_label.count() > 0:
        text = (wrapping_label.first.text_content() or "").strip()
        if text:
            return text

    preceding = control.locator("xpath=preceding::label[1]")
    if preceding.count() > 0:
        text = (preceding.first.text_content() or "").strip()
        if text:
            return text

    name = control.get_attribute("name") or ""
    return name


def _escape(value: str) -> str:
    return value.replace('"', '\\"')
