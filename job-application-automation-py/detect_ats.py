from urllib.parse import urlparse

from types_ import AtsPlatform


def detect_ats(job_url: str) -> AtsPlatform:
    host = urlparse(job_url).hostname or ""

    if "greenhouse.io" in host or "grnh.se" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    return "unknown"
