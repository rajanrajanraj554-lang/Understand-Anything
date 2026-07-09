import json
import re

from types_ import AiProvider, CandidateProfile, FormField

QUESTION_SYSTEM_PROMPT = (
    "You are drafting a first-person answer to a job application question "
    "on behalf of a candidate. Use only facts present in the resume/context "
    "below — never invent experience, dates, employers, or skills that are "
    "not supported by them. Keep the answer concise (2-5 sentences unless "
    "the question clearly calls for a short factual reply, e.g. years of "
    "experience or a yes/no). Respond with only the answer text, no preamble."
)

FORM_SYSTEM_PROMPT = (
    "You are filling out a job application form on behalf of a candidate, "
    "given their resume/profile and a list of the form's fields. Use only "
    "facts present in the resume/profile — never invent experience, dates, "
    "employers, or skills. For each field you can confidently fill, decide a "
    "value:\n"
    '- text/email/tel/textarea fields: a plain string value.\n'
    '- select/radio fields: pick one value verbatim from that field\'s '
    '"options" list.\n'
    '- checkbox fields: true or false.\n'
    "Skip (omit from your answer) any field you don't have enough "
    "information to answer confidently, or that looks like a legally "
    "sensitive demographic/EEO question (race, gender, disability, veteran "
    "status, etc.) — a human should answer those themselves.\n\n"
    "Respond with ONLY a JSON object mapping each field's index (as a "
    'string, e.g. "0") to its value. No prose, no markdown fences.'
)

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "groq": "llama-3.3-70b-versatile",
}


def _call_llm(
    system_prompt: str,
    user_content: str,
    provider: AiProvider,
    api_key: str,
    model: str | None = None,
    max_tokens: int = 800,
) -> str:
    model = model or DEFAULT_MODELS[provider]

    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return completion.choices[0].message.content or ""

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        for block in message.content:
            if block.type == "text":
                return block.text
        return ""

    raise ValueError(f"Unknown AI provider: {provider}")


def answer_question(
    question: str,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    provider: AiProvider = "anthropic",
    model: str | None = None,
) -> str:
    """Drafts a first-person answer to a single free-text application
    question. Always returns a draft — the caller is responsible for giving
    the candidate a chance to review it before it's submitted anywhere (see
    ApplyOptions.dry_run).
    """
    override = _find_override(question, profile.answer_overrides)
    if override:
        return override

    parts = [f"Resume:\n{resume_text}"]
    if profile.context:
        parts.append(f"Additional context:\n{profile.context}")
    parts.append(f"Application question:\n{question}")

    text = _call_llm(
        QUESTION_SYSTEM_PROMPT,
        "\n\n".join(parts),
        provider,
        api_key,
        model,
        max_tokens=400,
    )
    return text.strip()


def fill_form_fields(
    fields: list[FormField],
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
    provider: AiProvider = "anthropic",
    model: str | None = None,
) -> dict[int, str | bool]:
    """Given the fields actually present on a page (no assumptions about
    which ATS it is), asks the model how to fill each one and returns a
    mapping of field index -> value. Fields the model skips (not enough
    info, or sensitive demographic questions) are simply absent from the
    returned dict — the caller leaves those alone for the human to fill in
    during review.
    """
    if not fields:
        return {}

    field_lines = []
    for f in fields:
        desc = f'{{"index": {f.index}, "label": {json.dumps(f.label)}, "type": "{f.input_type or f.tag}"'
        if f.options:
            desc += f", \"options\": {json.dumps(f.options)}"
        if f.required:
            desc += ', "required": true'
        desc += "}"
        field_lines.append(desc)

    user_content = "\n\n".join(
        [
            f"Resume:\n{resume_text}",
            f"Additional context:\n{profile.context}" if profile.context else "",
            "Profile:\n"
            + json.dumps(
                {
                    "fullName": profile.full_name,
                    "email": profile.email,
                    "phone": profile.phone,
                    "location": profile.location,
                    "linkedinUrl": profile.linkedin_url,
                    "portfolioUrl": profile.portfolio_url,
                    "githubUrl": profile.github_url,
                }
            ),
            "Form fields:\n[" + ",\n".join(field_lines) + "]",
        ]
    ).strip()

    raw = _call_llm(FORM_SYSTEM_PROMPT, user_content, provider, api_key, model, max_tokens=1500)
    return _parse_field_mapping(raw)


def _parse_field_mapping(raw: str) -> dict[int, str | bool]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    result: dict[int, str | bool] = {}
    for key, value in parsed.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if value is None:
            continue
        result[idx] = value
    return result


def _find_override(question: str, overrides: dict[str, str]) -> str | None:
    normalized = question.lower()
    for key, value in overrides.items():
        if key.lower() in normalized:
            return value
    return None
