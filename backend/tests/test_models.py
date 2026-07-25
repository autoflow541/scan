"""ScanResult and friends accept client-supplied JSON on /vpat and
/issues.csv (the export endpoints take a scan result back, not just return
one), so their Field(max_length=...) bounds are a real abuse control, not
just documentation -- a client could otherwise hand-craft a payload with a
million-element issues list. These tests confirm pydantic actually enforces
them rather than the limits being decorative.
"""
import pytest
from pydantic import ValidationError

from app.models import Issue, IssueNode, ScanResult


def _make_result(**overrides) -> dict:
    base = dict(
        url="https://example.com",
        final_url="https://example.com",
        page_title="Example",
        scanned_at="2026-01-01T00:00:00Z",
        score=100,
        counts={},
        issues=[],
        passes=[],
        conformance=[],
        incomplete_count=0,
        scan_duration_ms=100,
    )
    base.update(overrides)
    return base


def test_valid_minimal_result_is_accepted():
    ScanResult(**_make_result())


def test_issues_list_over_cap_is_rejected():
    issue = Issue(
        id="x", impact="minor", tags=[], description="d", help="h", help_url="u",
        node_count=0, nodes=[],
    ).model_dump()
    with pytest.raises(ValidationError):
        ScanResult(**_make_result(issues=[issue] * 501))


def test_issue_nodes_list_over_cap_is_rejected():
    node = IssueNode(html="x", target=["a"]).model_dump()
    with pytest.raises(ValidationError):
        Issue(
            id="x", impact="minor", tags=[], description="d", help="h", help_url="u",
            node_count=0, nodes=[node] * 51,
        )


def test_html_field_over_cap_is_rejected():
    with pytest.raises(ValidationError):
        IssueNode(html="x" * 2001, target=["a"])


def test_screenshot_field_over_cap_is_rejected():
    with pytest.raises(ValidationError):
        ScanResult(**_make_result(screenshot="data:image/jpeg;base64," + "A" * 15_000_000))


def test_tags_list_over_cap_is_rejected():
    with pytest.raises(ValidationError):
        Issue(
            id="x", impact="minor", tags=["t"] * 31, description="d", help="h",
            help_url="u", node_count=0, nodes=[],
        )
