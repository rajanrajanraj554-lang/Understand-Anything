from anthropic import Anthropic

from types_ import CandidateProfile

SYSTEM_PROMPT = (
    "You are drafting a first-person answer to a job application question "
    "on behalf of a candidate. Use only facts present in the resume/context "
    "below — never invent experience, dates, employers, or skills that are "
    "not supported by them. Keep the answer concise (2-5 sentences unless "
    "the question clearly calls for a short factual reply, e.g. years of "
    "experience or a yes/no). Respond with only the answer text, no preamble."
)


def answer_question(
    question: str,
    profile: CandidateProfile,
    resume_text: str,
    api_key: str,
) -> str:
    """Drafts a first-person answer to a single free-text application
    question. Always returns a draft — the caller is responsible for giving
    the candidate a chance to review it before it's submitted anywhere (see
    ApplyOptions.dry_run).
    """
    override = _find_override(question, profile.answer_overrides)
    if override:
        return override

    client = Anthropic(api_key=api_key)

    parts = [f"Resume:\n{resume_text}"]
    if profile.context:
        parts.append(f"Additional context:\n{profile.context}")
    parts.append(f"Application question:\n{question}")

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )

    for block in message.content:
        if block.type == "text":
            return block.text.strip()
    return ""


def _find_override(question: str, overrides: dict[str, str]) -> str | None:
    normalized = question.lower()
    for key, value in overrides.items():
        if key.lower() in normalized:
            return value
    return None
