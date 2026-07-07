"""A simple 0-100 score heuristic from axe-core violations, for the marketing
"how good is this page" framing. Deliberately simple and monotonic rather than
a claim of conformance -- UI copy should describe it as a relative indicator,
not a certification, since WCAG conformance isn't really binary/scorable.
"""
from __future__ import annotations

IMPACT_WEIGHT = {"critical": 10, "serious": 5, "moderate": 2, "minor": 1}


def compute_score(violations: list[dict]) -> int:
    penalty = sum(
        IMPACT_WEIGHT.get(v.get("impact") or "minor", 1) * max(1, len(v.get("nodes", [])))
        for v in violations
    )
    return max(0, 100 - min(100, penalty))
