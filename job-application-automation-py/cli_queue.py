"""
Usage:
    python cli_queue.py <urls.txt> <profile.json> [--out ./out]
                         [--captcha-timeout 300] [--provider anthropic|groq]
                         [--model MODEL]

urls.txt: one job URL per line (blank lines and lines starting with # are
ignored).

Always runs headed -- queue mode's whole point is a human reviewing and
clearing CAPTCHAs in one sitting, which requires a visible browser.
"""

import argparse
import json
import sys

from queue_apply import run_queue
from types_ import CandidateProfile, QueueOptions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("urls_path")
    parser.add_argument("profile_path")
    parser.add_argument("--out", default="./out")
    parser.add_argument("--captcha-timeout", type=int, default=300)
    parser.add_argument("--provider", choices=["anthropic", "groq"], default="anthropic")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    with open(args.urls_path, encoding="utf-8") as f:
        job_urls = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    with open(args.profile_path, encoding="utf-8") as f:
        profile = CandidateProfile.from_dict(json.load(f))

    results = run_queue(
        QueueOptions(
            job_urls=job_urls,
            profile=profile,
            output_dir=args.out,
            captcha_timeout_seconds=args.captcha_timeout,
            ai_provider=args.provider,
            ai_model=args.model,
        )
    )

    print("\n=== Summary ===")
    for r in results:
        suffix = f"  ({r.error})" if r.error else ""
        print(f"{r.status.ljust(16)} {r.job_url}{suffix}")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001
        print(err, file=sys.stderr)
        sys.exit(1)
