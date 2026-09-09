"""Lead capture for the CTA band -- someone who liked what the scan showed
and wants to be contacted about a full audit.

No email service wired up yet (deliberately deferred -- see README): leads
are appended to a JSON-lines file on a host-mounted directory (see
deploy/setup-vm.sh's -v flag) so they survive container recreation, which a
container-internal path would not -- every redeploy in this project's
workflow does `docker rm -f` before starting the new container.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Deliberately simple: syntactic sanity, not deliverability verification.
# Good enough to reject "asdf" and typos like "a@b", not meant to catch every
# malformed edge case -- a human follows up on these leads manually anyway.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LEADS_DIR = Path(os.environ.get("LEADS_DIR", "/app/leads"))
LEADS_FILE = LEADS_DIR / "leads.jsonl"

MAX_EMAIL_LENGTH = 254  # RFC 5321


class InvalidEmailError(Exception):
    pass


def validate_email(email: str) -> str:
    email = (email or "").strip()
    if not email or len(email) > MAX_EMAIL_LENGTH or not _EMAIL_RE.match(email):
        raise InvalidEmailError("That doesn't look like a valid email address.")
    return email


_MAX_TOP_ISSUES = 10
_MAX_ISSUE_LENGTH = 200


def record_lead(
    *, email: str, scanned_url: str, score: int | None, client_ip: str,
    top_issues: list[str] | None = None,
) -> None:
    """Append one lead as a JSON line. Best-effort: a filesystem hiccup here
    should never break the request for the person submitting the form.

    top_issues carries the scan's own findings into the lead record, so
    whoever follows up has something concrete to reference instead of
    re-scanning the page themselves -- the actual "send this report to us"
    the CTA copy already promises. Capped again here (list length and per-
    item length) regardless of what the request schema already enforced --
    never trust client input to stay within schema limits at the storage
    layer too.
    """
    clean_issues = [str(i)[:_MAX_ISSUE_LENGTH] for i in (top_issues or [])][:_MAX_TOP_ISSUES]
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "email": email,
        "scanned_url": scanned_url,
        "score": score,
        "top_issues": clean_issues,
        "ip": client_ip,
    }
    try:
        LEADS_DIR.mkdir(parents=True, exist_ok=True)
        with LEADS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        log.error("Failed to record lead (email=%r): %s", email, exc)
        raise
    log.info("LEAD captured: email=%s scanned_url=%r score=%s ip=%s", email, scanned_url, score, client_ip)
