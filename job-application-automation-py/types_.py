"""Shared data types. Named types_ to avoid shadowing the stdlib `types` module."""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

AtsPlatform = Literal["greenhouse", "lever", "ashby", "unknown"]
QueueItemStatus = Literal["submitted", "skipped", "failed", "captcha-timeout"]
AiProvider = Literal["anthropic", "groq"]


@dataclass
class CandidateProfile:
    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str
    resume_path: str
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    cover_letter_path: Optional[str] = None
    # Substring (lowercase) -> exact answer, checked before the AI answerer.
    answer_overrides: dict[str, str] = field(default_factory=dict)
    # Freeform facts fed to the AI when answering open-ended questions.
    context: Optional[str] = None

    @staticmethod
    def from_dict(data: dict) -> "CandidateProfile":
        return CandidateProfile(
            full_name=data["fullName"],
            first_name=data["firstName"],
            last_name=data["lastName"],
            email=data["email"],
            phone=data["phone"],
            resume_path=data["resumePath"],
            location=data.get("location"),
            linkedin_url=data.get("linkedinUrl"),
            portfolio_url=data.get("portfolioUrl"),
            github_url=data.get("githubUrl"),
            cover_letter_path=data.get("coverLetterPath"),
            answer_overrides=data.get("answerOverrides", {}),
            context=data.get("context"),
        )


@dataclass
class AnsweredQuestion:
    question: str
    answer: str


@dataclass
class FormField:
    """One fillable control found on the page, in DOM order. `index` is its
    position in that scan and is how the AI's answer gets mapped back to the
    actual Playwright locator — no CSS selector guessing involved.
    """

    index: int
    label: str
    tag: str  # "input" | "textarea" | "select"
    input_type: str  # e.g. "text", "email", "tel", "checkbox", "radio", "" for textarea/select
    options: list[str] = field(default_factory=list)  # <option> texts, or group values for radio
    required: bool = False


@dataclass
class ApplyOptions:
    job_url: str
    profile: CandidateProfile
    output_dir: str
    # When True (default), the form is filled and screenshotted but never
    # submitted. Set to False only once you've reviewed a dry run and want
    # this specific application actually sent.
    dry_run: bool = True
    # Run with a visible browser window. Strongly recommended: keeps a human
    # in the loop for anything unexpected (extra fields, verification
    # challenges). See README for why headless/"invisible" mode is
    # deliberately not the default here.
    headed: bool = True
    ai_provider: AiProvider = "anthropic"
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None


@dataclass
class ApplicationResult:
    ats: AtsPlatform
    submitted: bool
    screenshot_path: str
    answered_questions: list[AnsweredQuestion]
    notes: list[str]


@dataclass
class QueueOptions:
    job_urls: list[str]
    profile: CandidateProfile
    output_dir: str
    ai_provider: AiProvider = "anthropic"
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    # Max seconds to wait for a human to clear a CAPTCHA on any one item
    # during the review pass before giving up on that item and moving on.
    captcha_timeout_seconds: int = 300


@dataclass
class QueueItemResult:
    job_url: str
    ats: AtsPlatform
    status: QueueItemStatus
    needed_captcha: bool
    answered_questions: list[AnsweredQuestion] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
