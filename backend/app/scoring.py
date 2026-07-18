"""The scan's headline percentage is tied directly to the VPAT-style
conformance table (see conformance.py), not a separate arbitrary heuristic:
it's the share of WCAG success criteria this scan actually tested that
came back "Supports". Criteria with a violation ("Does Not Support") or
only ambiguous/manual-check items ("Needs Review") don't count toward the
numerator -- "Needs Review" is deliberately NOT treated as passing, since
axe couldn't confirm it either way. This keeps the number meaningfully
equal to "percentage of tested criteria supported", matching how a VPAT
documents conformance per-criterion, rather than an opaque points system.

"Not Applicable" criteria (axe checked and confirmed a rule's target
content genuinely isn't present -- e.g. caption rules on a page with no
video at all) are excluded from both the numerator AND denominator: a page
shouldn't score lower just because it has no video to caption in the first
place. Counting them as failures would be wrong; counting them as passes
would be misleading credit for something never actually tested.
"""
from __future__ import annotations


def compute_score(conformance_rows: list[dict]) -> int:
    scored_rows = [row for row in conformance_rows if row["status"] != "not_applicable"]
    if not scored_rows:
        return 100  # nothing testable was found -- no criteria to fail
    supports = sum(1 for row in scored_rows if row["status"] == "supports")
    return round(supports / len(scored_rows) * 100)
