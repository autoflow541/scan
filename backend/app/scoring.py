"""The scan's headline percentage is tied directly to the VPAT-style
conformance table (see conformance.py), not a separate arbitrary heuristic:
it's the share of WCAG success criteria this scan actually tested that
came back "Supports". Criteria with a violation ("Does Not Support") or
only ambiguous/manual-check items ("Needs Review") don't count toward the
numerator -- "Needs Review" is deliberately NOT treated as passing, since
axe couldn't confirm it either way. This keeps the number meaningfully
equal to "percentage of tested criteria supported", matching how a VPAT
documents conformance per-criterion, rather than an opaque points system.
"""
from __future__ import annotations


def compute_score(conformance_rows: list[dict]) -> int:
    if not conformance_rows:
        return 100  # nothing testable was found -- no criteria to fail
    supports = sum(1 for row in conformance_rows if row["status"] == "supports")
    return round(supports / len(conformance_rows) * 100)
