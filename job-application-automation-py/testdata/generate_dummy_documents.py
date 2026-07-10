"""Generates dummy_resume.pdf and dummy_cover_letter.pdf for a fake
candidate (Jordan Rivera), used only to exercise the job-application
automation tool's form filling. Not a real person's data.

Usage: python testdata/generate_dummy_documents.py
"""

from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent

RESUME_TEXT = """
Jordan Rivera
Austin, TX | jordan.rivera.dummy@example.com | +1-555-0100
linkedin.com/in/jordanrivera-dummy | github.com/jordanrivera-dummy | jordanrivera-dummy.dev

SUMMARY
Backend engineer with 8 years of experience building distributed systems in
Go and TypeScript. Led a 4-person team shipping payments infrastructure at a
Series B fintech startup. Comfortable owning services end to end: design,
on-call, and mentoring.

EXPERIENCE
Senior Software Engineer, Fintech Startup (fictional) -- 2021-Present
- Led redesign of the payment-ledger service, cutting reconciliation errors
  by an estimated 90% (dummy figure for testing).
- Managed a team of 4 engineers; ran on-call rotation for 12 services.
- Migrated a monolith's billing module to a Go microservice.

Software Engineer, Data Platform Co (fictional) -- 2018-2021
- Built ETL pipelines processing ~2TB/day of event data.
- Wrote internal tooling in TypeScript/Node for schema migrations.

Junior Engineer, DevTools Inc (fictional) -- 2016-2018
- Contributed to an internal CI system used by ~50 engineers.

EDUCATION
B.S. Computer Science, State University (fictional) -- 2016

SKILLS
Go, TypeScript, Python, PostgreSQL, Kafka, Kubernetes, AWS
"""

COVER_LETTER_TEXT = """
Jordan Rivera
jordan.rivera.dummy@example.com | +1-555-0100

Dear Hiring Team,

I'm reaching out about the Software Engineer opening on your team. I've
spent the last several years building backend services in Go and
TypeScript, most recently leading a small team responsible for payments
infrastructure at a Series B startup. I'm drawn to roles where I can own a
service end to end, and I'd welcome the chance to bring that experience to
your engineering org.

I've attached my resume and would be glad to speak further.

Best,
Jordan Rivera

(Note: this cover letter and the attached resume describe a fictional
candidate, generated only to test job-application form-filling automation.
No real person or work history is represented.)
"""


def write_pdf(text: str, out_path: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for line in text.strip("\n").split("\n"):
        pdf.set_x(pdf.l_margin)
        if line.strip():
            pdf.multi_cell(width, 6, line)
        else:
            pdf.ln(6)
    pdf.output(str(out_path))


if __name__ == "__main__":
    write_pdf(RESUME_TEXT, HERE / "dummy_resume.pdf")
    write_pdf(COVER_LETTER_TEXT, HERE / "dummy_cover_letter.pdf")
    print(f"Wrote {HERE / 'dummy_resume.pdf'}")
    print(f"Wrote {HERE / 'dummy_cover_letter.pdf'}")
