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
