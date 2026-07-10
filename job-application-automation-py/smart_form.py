from playwright.sync_api import Page

from ai import fill_form_fields
from types_ import AiProvider, AnsweredQuestion, CandidateProfile, FormField

# Anything that isn't free text/select/checkbox — handled separately (file
# uploads) or left for the human (submit/hidden/button controls).
_EXCLUDED_INPUT_TYPES = {"hidden", "file", "submit", "button", "reset", "image"}

# Native form controls, plus the triggers of custom dropdown widgets (React-
# select-style comboboxes, common on Ashby and other React-based ATS forms)
# that never render as a real <select>. A comma-separated CSS selector
# returns matches in DOM order regardless of which part matched, so this
# still yields one stable, index-ordered list.
_FILLABLE_SELECTOR = (
    "input:not([type=hidden]):not([type=file]):not([type=submit])"
    ":not([type=button]):not([type=reset]):not([type=image]), textarea, select, "
    '[role="combobox"], [aria-haspopup="listbox"]'
)

_LISTBOX_OPTION_SELECTOR = (
    '[role="listbox"] [role="option"], [role="listbox"] li, ul[role="listbox"] li'
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

        role = (control.get_attribute("role") or "").lower()
        aria_haspopup = (control.get_attribute("aria-haspopup") or "").lower()
        is_custom_combobox = tag != "select" and (
            role == "combobox" or aria_haspopup == "listbox"
        )

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
        elif is_custom_combobox:
            # Some custom dropdowns only reveal options once opened, and a
            # few (type-ahead comboboxes) reveal none until you start
            # typing — this best-effort peek just gives the AI a menu to
            # choose from when one is available; an empty list here still
            # gets a value from the AI (a free-text guess), and fill time
            # falls back to typing it in if nothing matches.
            options = _peek_combobox_options(page, control)

        fields.append(
            FormField(
                index=i,
                label=label,
                tag="combobox" if is_custom_combobox else tag,
                input_type=input_type,
                options=options,
                required=required,
            )
        )

    return fields


def _peek_combobox_options(page: Page, control) -> list[str]:
    try:
        control.click()
        page.wait_for_selector(_LISTBOX_OPTION_SELECTOR, timeout=1500, state="visible")
        options = [
            o.strip()
            for o in page.locator(_LISTBOX_OPTION_SELECTOR).all_inner_texts()
            if o.strip()
        ]
    except Exception:
        options = []
    finally:
        page.keyboard.press("Escape")
    return options


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

        if field.tag not in ("select", "combobox"):
            try:
                existing = control.input_value()
            except Exception:
                existing = None
            if existing:
                continue  # don't clobber something already filled (e.g. pre-populated email)

        if field.tag == "select":
            control.select_option(label=str(value))
        elif field.tag == "combobox":
            if not _select_combobox_option(page, control, str(value)):
                continue  # couldn't resolve a value; leave it for the human to fill
        elif field.input_type in ("checkbox", "radio"):
            if isinstance(value, str):
                value = value.strip().lower() in ("true", "yes", "1")
            if value:
                control.check()
        else:
            control.fill(str(value))

        if field.label:
            answered_questions.append(AnsweredQuestion(question=field.label, answer=str(value)))


def _select_combobox_option(page: Page, control, target_text: str) -> bool:
    """Opens a custom dropdown and clicks the option matching `target_text`
    (exact match first, then substring match either direction). If no
    option list appears or nothing matches — common for type-ahead
    comboboxes that filter as you type — types the value in and retries
    once against whatever options that typing revealed.
    """
    target = target_text.strip().lower()
    if not target:
        return False

    control.click()
    try:
        page.wait_for_selector(_LISTBOX_OPTION_SELECTOR, timeout=1500, state="visible")
    except Exception:
        pass

    if _click_matching_option(page, target):
        return True

    # Type-ahead fallback: type the value to filter the list, then retry.
    try:
        control.fill(target_text)
    except Exception:
        try:
            control.type(target_text)
        except Exception:
            page.keyboard.press("Escape")
            return False

    try:
        page.wait_for_selector(_LISTBOX_OPTION_SELECTOR, timeout=1500, state="visible")
    except Exception:
        pass

    if _click_matching_option(page, target):
        return True

    page.keyboard.press("Escape")
    return False


def _click_matching_option(page: Page, target: str) -> bool:
    options = page.locator(_LISTBOX_OPTION_SELECTOR)
    count = options.count()

    for j in range(count):
        text = (options.nth(j).text_content() or "").strip().lower()
        if text == target:
            options.nth(j).click()
            return True

    for j in range(count):
        text = (options.nth(j).text_content() or "").strip().lower()
        if text and (target in text or text in target):
            options.nth(j).click()
            return True

    return False


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

    labelledby = control.get_attribute("aria-labelledby")
    if labelledby:
        texts = []
        for ref_id in labelledby.split():
            ref = page.locator(f'[id="{_escape(ref_id)}"]').first
            if ref.count() > 0:
                text = (ref.text_content() or "").strip()
                if text:
                    texts.append(text)
        if texts:
            return " ".join(texts)

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
