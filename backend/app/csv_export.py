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


def issues_to_csv(result: ScanResult) -> str:
    """Render a scan result's issues as CSV text (with a leading UTF-8 BOM)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_HEADER)

    for issue in result.issues:
        criterion = issue.wcag_criterion or ""
        base = [criterion, issue.id, issue.impact, issue.description]
        if issue.nodes:
            for node in issue.nodes:
                writer.writerow(
                    base
                    + [
                        " ".join(node.target),
                        node.html,
                        node.failure_summary or "",
                        issue.help,
                        issue.help_url,
                    ]
                )
        else:
            writer.writerow(base + ["", "", "", issue.help, issue.help_url])

    return "﻿" + buf.getvalue()
