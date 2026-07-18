from app.conformance import build_conformance


def test_criterion_with_violation_does_not_support():
    violations = [{"id": "color-contrast", "tags": ["wcag143"]}]
    rows = build_conformance(violations, [], [])
    assert rows == [
        {
            "criterion": "1.4.3 Contrast (Minimum)",
            "status": "does_not_support",
            "passed_rules": [],
            "failed_rules": ["color-contrast"],
            "review_rules": [],
            "na_rules": [],
        }
    ]


def test_criterion_with_only_passes_supports():
    passes = [{"id": "html-has-lang", "tags": ["wcag311"]}]
    rows = build_conformance([], passes, [])
    assert rows[0]["status"] == "supports"
    assert rows[0]["passed_rules"] == ["html-has-lang"]


def test_criterion_with_only_incomplete_needs_review():
    incomplete = [{"id": "color-contrast", "tags": ["wcag143"]}]
    rows = build_conformance([], [], incomplete)
    assert rows[0]["status"] == "needs_review"


def test_violation_takes_precedence_over_pass_for_same_criterion():
    violations = [{"id": "image-alt", "tags": ["wcag111"]}]
    passes = [{"id": "svg-img-alt", "tags": ["wcag111"]}]
    rows = build_conformance(violations, passes, [])
    assert len(rows) == 1
    assert rows[0]["status"] == "does_not_support"
    assert rows[0]["passed_rules"] == ["svg-img-alt"]
    assert rows[0]["failed_rules"] == ["image-alt"]


def test_sorted_numerically_not_lexicographically():
    passes = [
        {"id": "a", "tags": ["wcag1410"]},
        {"id": "b", "tags": ["wcag143"]},
    ]
    rows = build_conformance([], passes, [])
    criteria = [r["criterion"] for r in rows]
    assert criteria == ["1.4.3 Contrast (Minimum)", "1.4.10 Reflow"]


def test_untagged_rules_are_skipped():
    passes = [{"id": "untagged-rule", "tags": ["best-practice"]}]
    rows = build_conformance([], passes, [])
    assert rows == []


def test_criterion_with_only_inapplicable_is_not_applicable():
    """axe checked (e.g. video-caption ran) and confirmed the content this
    criterion governs (a <video> element) isn't present at all -- a real,
    positive result distinct from "we never checked"."""
    inapplicable = [{"id": "video-caption", "tags": ["wcag122"]}]
    rows = build_conformance([], [], [], inapplicable)
    assert rows[0]["status"] == "not_applicable"
    assert rows[0]["na_rules"] == ["video-caption"]


def test_pass_takes_precedence_over_inapplicable_for_same_criterion():
    """If a DIFFERENT rule mapped to the same criterion actually ran and
    passed, the criterion is genuinely supported -- the inapplicable rule
    for this page just isn't relevant evidence either way."""
    passes = [{"id": "scrollable-region-focusable", "tags": ["wcag211"]}]
    inapplicable = [{"id": "server-side-image-map", "tags": ["wcag211"]}]
    rows = build_conformance([], passes, [], inapplicable)
    assert len(rows) == 1
    assert rows[0]["status"] == "supports"


def test_fail_takes_precedence_over_inapplicable_for_same_criterion():
    violations = [{"id": "frame-focusable-content", "tags": ["wcag211"]}]
    inapplicable = [{"id": "server-side-image-map", "tags": ["wcag211"]}]
    rows = build_conformance(violations, [], [], inapplicable)
    assert rows[0]["status"] == "does_not_support"
