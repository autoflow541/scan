"""CSV export of scan issues.

One row per *node* (the actual offending element) rather than per rule, so the
file drops straight into a spreadsheet or ticketing import as a remediation
worklist. A UTF-8 BOM is prepended so Excel opens it as UTF-8 without mangling
non-ASCII characters.
"""
from __future__ import annotations

import csv
import io

from .models import ScanResult

_HEADER = [
    "WCAG Criterion",
    "Rule",
    "Impact",
    "Description",
    "Element",
    "HTML",
    "Failure Summary",
    "Help",
    "Help URL",
]

# Cell values here (element HTML, descriptions) come from the *scanned page*,
# not the user -- a hostile page can put whatever it wants in there. Excel and
# Sheets treat a cell starting with one of these as a formula, so a crafted
# alt-text or class name could execute when someone opens the exported CSV.
# Prefixing with a straight quote neutralizes it while keeping the value
# visible (standard CSV-injection mitigation).
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: str) -> str:
    if value and value[0] in _FORMULA_TRIGGERS:
        return "'" + value
    return value


def issues_to_csv(result: ScanResult) -> str:
    """Render a scan result's issues as CSV text (with a leading UTF-8 BOM)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_HEADER)

    def row(*cells: str) -> list[str]:
        return [_safe_cell(c) for c in cells]

    for issue in result.issues:
        criterion = issue.wcag_criterion or ""
        base = (criterion, issue.id, issue.impact, issue.description)
        if issue.nodes:
            for node in issue.nodes:
                writer.writerow(
                    row(
                        *base,
                        " ".join(node.target),
                        node.html,
                        node.failure_summary or "",
                        issue.help,
                        issue.help_url,
                    )
                )
        else:
            writer.writerow(row(*base, "", "", "", issue.help, issue.help_url))

    return "﻿" + buf.getvalue()
