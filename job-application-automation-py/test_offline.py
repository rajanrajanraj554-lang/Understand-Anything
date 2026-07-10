"""One-command offline test suite.

Runs every part of the tool that DOESN'T need a live job site or a paid
LLM key: URL detection, resume extraction, AI-response parsing, and the
full browser form-fill pipeline (against a local HTML form, with the LLM
call stubbed out).

    python test_offline.py

What this does NOT cover: a real end-to-end apply against greenhouse/
lever/ashby -- that needs internet + an API key and must run on a machine
with both (see the bottom of this file for that command).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
# Layer 1: pure logic (no browser, no key)
# ---------------------------------------------------------------------------
def test_detect_ats() -> None:
    print("\n[1] detect_ats")
    from detect_ats import detect_ats

    check("greenhouse", detect_ats("https://boards.greenhouse.io/acme/jobs/1") == "greenhouse")
    check("lever", detect_ats("https://jobs.lever.co/acme/abc") == "lever")
    check("ashby", detect_ats("https://jobs.ashbyhq.com/acme/abc") == "ashby")
    check("unknown", detect_ats("https://example.com/careers") == "unknown")


def test_ai_parsing() -> None:
    print("\n[2] ai._parse_field_mapping")
    from ai import _parse_field_mapping

    fenced = '```json\n{"0": "Jordan", "2": true, "3": null}\n```'
    r1 = _parse_field_mapping(fenced)
    check("strips markdown fences", r1 == {0: "Jordan", 2: True}, str(r1))

    prose = 'Here is the JSON:\n{"1": "a@b.com"}\nHope that helps!'
    r2 = _parse_field_mapping(prose)
    check("ignores surrounding prose", r2 == {1: "a@b.com"}, str(r2))

    check("garbage -> empty dict", _parse_field_mapping("no json here") == {})


def test_resume() -> None:
    print("\n[3] resume.extract_resume_text")
    from resume import extract_resume_text

    pdf = HERE / "testdata" / "dummy_resume.pdf"
    if not pdf.exists():
        check("dummy_resume.pdf exists", False, "run: python testdata/generate_dummy_documents.py")
        return
    text = extract_resume_text(str(pdf))
    check("extracts candidate name", "Jordan Rivera" in text, text[:80])
    check("extracts skills", "TypeScript" in text)


# ---------------------------------------------------------------------------
# Layer 2: browser form-fill (needs chromium, still no key/internet)
# ---------------------------------------------------------------------------
LOCAL_FORM = """
<form>
  <label for="fn">First Name</label><input id="fn" type="text"/>
  <label for="em">Email</label><input id="em" type="email"/>
  <label for="why">Why here?</label><textarea id="why"></textarea>
  <label for="loc">Location</label>
  <select id="loc"><option value="">Pick</option><option>Remote</option><option>Onsite</option></select>
  <button type="submit">Submit</button>
</form>
"""


def _launch(pw):
    """Launch chromium, falling back to this sandbox's preinstalled build if
    the pip-managed one isn't downloaded (your own machine won't need this)."""
    try:
        return pw.chromium.launch(headless=True)
    except Exception:
        for candidate in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"):
            return pw.chromium.launch(headless=True, executable_path=str(candidate))
        raise


def test_form_fill() -> None:
    print("\n[4] smart_form (browser, stubbed LLM)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("playwright installed", False, "pip install -r requirements.txt")
        return

    import ai
    from smart_form import apply_ai_field_mapping, find_form_scope, scan_fields
    from types_ import AnsweredQuestion

    # Stub the LLM so no API key is needed.
    ai._call_llm = lambda *a, **k: json.dumps(
        {"0": "Jordan", "1": "jordan@example.com", "2": "I like backends.", "3": "Remote"}
    )

    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            page.set_content(LOCAL_FORM)

            scope = find_form_scope(page)
            fields = scan_fields(page, scope)
            check("scanned 4 fields", len(fields) == 4, f"got {len(fields)}")
            check("detected the <select>", any(f.tag == "select" for f in fields))

            from ai import fill_form_fields
            from types_ import CandidateProfile

            profile = CandidateProfile.from_dict(json.load(open(HERE / "testdata" / "dummy_profile.json")))
            mapping = fill_form_fields(fields, profile, "resume text", "stub-key")
            answered: list[AnsweredQuestion] = []
            apply_ai_field_mapping(page, scope, fields, mapping, answered)

            check("filled first name", page.locator("#fn").input_value() == "Jordan")
            check("filled email", page.locator("#em").input_value() == "jordan@example.com")
            check("selected dropdown", page.locator("#loc").input_value() == "Remote")
            check("recorded answers", len(answered) == 4, f"got {len(answered)}")
            browser.close()
    except Exception as e:
        check("browser run completed", False, repr(e))


if __name__ == "__main__":
    test_detect_ats()
    test_ai_parsing()
    test_resume()
    test_form_fill()

    print(f"\n{'='*40}\n{passed} passed, {failed} failed")
    if failed:
        print(
            "\nNote: the live end-to-end apply is NOT tested here (no internet/"
            "key in some environments). To run it on your own machine:\n"
            "  export ANTHROPIC_API_KEY=...   # or GROQ_API_KEY with --provider groq\n"
            "  python cli.py '<job-url>' testdata/dummy_profile.json --headed"
        )
    sys.exit(1 if failed else 0)
