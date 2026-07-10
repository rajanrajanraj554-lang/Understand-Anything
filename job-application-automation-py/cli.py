"""
Usage:
    python cli.py <job_url> <profile.json> [--headed] [--submit] [--out ./out]
                  [--provider anthropic|groq] [--model MODEL]

profile.json shape: see CandidateProfile in types_.py. Example in
profile.example.json.

Defaults to a dry run (fills the form, screenshots it, does not click
submit) and to a headless browser. Pass --headed to see the window --
strongly recommended, see README.
"""

import argparse
import json
import sys

from apply import apply_to_job
from types_ import ApplyOptions, CandidateProfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_url")
    parser.add_argument("profile_path")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--out", default="./out")
    parser.add_argument("--provider", choices=["anthropic", "groq"], default="anthropic")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    with open(args.profile_path, encoding="utf-8") as f:
        profile = CandidateProfile.from_dict(json.load(f))

    result = apply_to_job(
        ApplyOptions(
            job_url=args.job_url,
            profile=profile,
            output_dir=args.out,
            dry_run=not args.submit,
            headed=args.headed,
            ai_provider=args.provider,
            ai_model=args.model,
        )
    )

    print(json.dumps(result.__dict__, default=lambda o: o.__dict__, indent=2))

    if any(note.startswith("Dry run") for note in result.notes):
        print(
            "\nThis was a dry run. Review the screenshot and answers above, "
            "then re-run with --submit to actually send this application."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001
        print(err, file=sys.stderr)
        sys.exit(1)
