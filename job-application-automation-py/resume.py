from pathlib import Path

from pypdf import PdfReader


def extract_resume_text(resume_path: str) -> str:
    path = Path(resume_path)

    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return path.read_text(encoding="utf-8")
