"""Builds a VPAT-style per-criterion conformance summary from axe-core's
violations/passes/incomplete/inapplicable results -- not just a list of
failures, but a row per WCAG success criterion the scan actually reasoned
about, showing whether it Supports (all checks passed), Does Not Support
(has a violation), Needs Review (only ambiguous/manual-check items), or Not
Applicable (axe checked and the criterion's rules genuinely don't apply to
this page -- e.g. caption rules on a page with no audio/video at all).

Not Applicable matters as its own status, not a fold into "Not Evaluated":
axe DID run these rules and DID determine they don't apply here, which is a
real, positive result -- collapsing it into "we never checked" understates
coverage and (via scoring.py) would otherwise unfairly penalize a page for
"not supporting" something that isn't even present.
"""
from __future__ import annotations

from .wcag_map import primary_criterion


def _sc_sort_key(label: str) -> tuple[int, ...]:
    """Sort '1.4.10' after '1.4.3' (numeric, not lexicographic)."""
    prefix = label.split(" ", 1)[0]
    return tuple(int(p) for p in prefix.split("."))


def build_conformance(
    violations: list[dict],
    passes: list[dict],
    incomplete: list[dict],
    inapplicable: list[dict] | None = None,
) -> list[dict]:
    by_criterion: dict[str, dict[str, set[str]]] = {}

    def note(tags: list[str], rule_id: str, bucket: str) -> None:
        criterion = primary_criterion(tags)
        if criterion is None:
            return
        entry = by_criterion.setdefault(
            criterion, {"pass": set(), "fail": set(), "review": set(), "na": set()}
        )
        entry[bucket].add(rule_id)

    for v in violations:
        note(v.get("tags", []), v.get("id", ""), "fail")
    for p in passes:
        note(p.get("tags", []), p.get("id", ""), "pass")
    for i in incomplete:
        note(i.get("tags", []), i.get("id", ""), "review")
    for i in inapplicable or []:
        note(i.get("tags", []), i.get("id", ""), "na")

    rows = []
    for criterion in sorted(by_criterion, key=_sc_sort_key):
        entry = by_criterion[criterion]
        if entry["fail"]:
            status = "does_not_support"
        elif entry["review"]:
            status = "needs_review"
        elif entry["pass"]:
            status = "supports"
        elif entry["na"]:
            # Only real evidence for this criterion is "checked, didn't
            # apply" -- e.g. video-caption ran and found no <video> at all.
            status = "not_applicable"
        else:
            status = "supports"  # unreachable in practice; every bucket empty means note() was never called
        rows.append(
            {
                "criterion": criterion,
                "status": status,
                "passed_rules": sorted(entry["pass"]),
                "failed_rules": sorted(entry["fail"]),
                "review_rules": sorted(entry["review"]),
                "na_rules": sorted(entry["na"]),
            }
        )
    return rows
