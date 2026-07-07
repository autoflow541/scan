"""Builds a VPAT-style per-criterion conformance summary from axe-core's
violations/passes/incomplete results -- not just a list of failures, but a
row per WCAG success criterion actually exercised by the scan, showing
whether it Supports (all checks passed), Does Not Support (has a violation),
or Needs Review (only ambiguous/manual-check items, no outright violation).
"""
from __future__ import annotations

from .wcag_map import primary_criterion


def _sc_sort_key(label: str) -> tuple[int, ...]:
    """Sort '1.4.10' after '1.4.3' (numeric, not lexicographic)."""
    prefix = label.split(" ", 1)[0]
    return tuple(int(p) for p in prefix.split("."))


def build_conformance(
    violations: list[dict], passes: list[dict], incomplete: list[dict]
) -> list[dict]:
    by_criterion: dict[str, dict[str, set[str]]] = {}

    def note(tags: list[str], rule_id: str, bucket: str) -> None:
        criterion = primary_criterion(tags)
        if criterion is None:
            return
        entry = by_criterion.setdefault(criterion, {"pass": set(), "fail": set(), "review": set()})
        entry[bucket].add(rule_id)

    for v in violations:
        note(v.get("tags", []), v.get("id", ""), "fail")
    for p in passes:
        note(p.get("tags", []), p.get("id", ""), "pass")
    for i in incomplete:
        note(i.get("tags", []), i.get("id", ""), "review")

    rows = []
    for criterion in sorted(by_criterion, key=_sc_sort_key):
        entry = by_criterion[criterion]
        if entry["fail"]:
            status = "does_not_support"
        elif entry["review"]:
            status = "needs_review"
        else:
            status = "supports"
        rows.append(
            {
                "criterion": criterion,
                "status": status,
                "passed_rules": sorted(entry["pass"]),
                "failed_rules": sorted(entry["fail"]),
                "review_rules": sorted(entry["review"]),
            }
        )
    return rows
