"""_build_scan_result must correctly attach (or omit) the optional AI review
without disturbing anything else in ScanResult -- the wiring point between
scanner.py's orchestration and the new ai_page_review.py module."""

from __future__ import annotations

from app.scanner import _build_scan_result


def test_ai_review_none_by_default():
    result = _build_scan_result(
        "http://x.test", "http://x.test", "Title", {}, 100, {}, None,
    )
    assert result.ai_review is None


def test_ai_review_dict_is_attached_when_present():
    ai_review = {
        "summary": "One weak alt text found.",
        "findings": [
            {"criterion": "1.1.1", "verdict": "concern", "subject": "img1.jpg", "detail": "Filename, not descriptive."},
            {"criterion": "2.4.4", "verdict": "ok", "subject": "Download the 2026 report (PDF)", "detail": "Clear out of context."},
        ],
        "model": "claude-sonnet-5",
        "inputTokens": 1200,
        "outputTokens": 150,
        "disclaimer": "AI-assisted preliminary judgment -- not a conformance determination.",
    }
    result = _build_scan_result(
        "http://x.test", "http://x.test", "Title", {}, 100, {}, None, ai_review,
    )
    assert result.ai_review is not None
    assert result.ai_review.summary == "One weak alt text found."
    assert len(result.ai_review.findings) == 2
    assert result.ai_review.findings[0].criterion == "1.1.1"
    assert result.ai_review.findings[0].verdict == "concern"
    assert result.ai_review.input_tokens == 1200
    assert result.ai_review.output_tokens == 150
    # Never touches conformance/vpat -- the whole point of keeping this a
    # separate, clearly-disclosed layer rather than upgrading a verdict.
    assert result.vpat_summary  # still built normally from empty axe results


def test_empty_findings_list_is_valid():
    ai_review = {
        "summary": "Nothing confidently judgeable on this page.",
        "findings": [],
        "model": "claude-sonnet-5",
        "inputTokens": 400,
        "outputTokens": 30,
        "disclaimer": "AI-assisted preliminary judgment -- not a conformance determination.",
    }
    result = _build_scan_result(
        "http://x.test", "http://x.test", "Title", {}, 100, {}, None, ai_review,
    )
    assert result.ai_review.findings == []
