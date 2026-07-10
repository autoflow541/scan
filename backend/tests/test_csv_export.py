import csv
import io
from datetime import datetime, timezone

from app.csv_export import issues_to_csv
from app.models import Issue, IssueNode, ScanResult


def _result(issues):
    return ScanResult(
        url="https://example.com", final_url="https://example.com", page_title="Example",
        scanned_at=datetime.now(timezone.utc), score=50, counts={}, issues=issues,
        passes=[], conformance=[], vpat=[], vpat_summary={}, incomplete_count=0,
        scan_duration_ms=100, screenshot=None,
    )


def _rows(csv_text):
    # Strip the leading UTF-8 BOM before parsing.
    return list(csv.reader(io.StringIO(csv_text.lstrip("﻿"))))


def test_header_and_one_row_per_node():
    issue = Issue(
        id="color-contrast", impact="serious", wcag_criterion="1.4.3 Contrast (Minimum)",
        tags=["wcag143"], description="Elements must have sufficient contrast",
        help="Fix contrast", help_url="https://example.com/rules/color-contrast",
        node_count=2,
        nodes=[
            IssueNode(html="<a>one</a>", target=[".a"], failure_summary="ratio 2:1"),
            IssueNode(html="<a>two</a>", target=[".b"], failure_summary="ratio 3:1"),
        ],
    )
    rows = _rows(issues_to_csv(_result([issue])))
    assert rows[0] == [
        "WCAG Criterion", "Rule", "Impact", "Description",
        "Element", "HTML", "Failure Summary", "Help", "Help URL",
    ]
    assert len(rows) == 3  # header + 2 nodes
    assert rows[1][0] == "1.4.3 Contrast (Minimum)"
    assert rows[1][1] == "color-contrast"
    assert rows[1][4] == ".a"
    assert rows[2][4] == ".b"


def test_starts_with_bom_for_excel():
    csv_text = issues_to_csv(_result([]))
    assert csv_text.startswith("﻿")
    assert "WCAG Criterion" in csv_text


def test_commas_and_newlines_are_quoted():
    issue = Issue(
        id="r", impact="minor", wcag_criterion=None, tags=[],
        description="has, comma\nand newline", help="h", help_url="u",
        node_count=1,
        nodes=[IssueNode(html="<b>x</b>", target=["b"], failure_summary=None)],
    )
    text = issues_to_csv(_result([issue]))
    rows = _rows(text)
    # csv round-trips the comma+newline field intact.
    assert rows[1][3] == "has, comma\nand newline"
    assert rows[1][0] == ""  # missing criterion -> empty cell


def test_issue_with_no_nodes_still_emits_a_row():
    issue = Issue(
        id="doc-title", impact="serious", wcag_criterion="2.4.2 Page Titled",
        tags=["wcag242"], description="Documents must have a title", help="Add a title",
        help_url="https://example.com/rules/document-title", node_count=0, nodes=[],
    )
    rows = _rows(issues_to_csv(_result([issue])))
    assert len(rows) == 2  # header + 1 row
    assert rows[1][1] == "doc-title"
    assert rows[1][4] == ""  # no element
