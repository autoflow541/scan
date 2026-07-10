from app.vpat import (
    DOES_NOT,
    NOT_EVALUATED,
    PARTIALLY,
    SUPPORTS,
    build_vpat,
    render_vpat_html,
    vpat_summary,
)
from app.wcag_catalog import WCAG_22_A_AA


def _find(rows, num):
    return next(r for r in rows if r["num"] == num)


def test_vpat_covers_every_a_and_aa_criterion():
    rows = build_vpat([])
    assert len(rows) == len(WCAG_22_A_AA)
    # A criterion axe never exercised must be reported honestly, not omitted.
    assert _find(rows, "1.2.2")["conformance"] == NOT_EVALUATED


def test_failure_maps_to_does_not_support():
    conf = [{"criterion": "1.4.3 Contrast (Minimum)", "status": "does_not_support",
             "passed_rules": [], "failed_rules": ["color-contrast"], "review_rules": []}]
    row = _find(build_vpat(conf), "1.4.3")
    assert row["conformance"] == DOES_NOT
    assert "color-contrast" in row["remarks"]


def test_mixed_pass_and_fail_is_partial():
    conf = [{"criterion": "1.1.1 Non-text Content", "status": "does_not_support",
             "passed_rules": ["svg-img-alt"], "failed_rules": ["image-alt"], "review_rules": []}]
    assert _find(build_vpat(conf), "1.1.1")["conformance"] == PARTIALLY


def test_all_pass_maps_to_supports():
    conf = [{"criterion": "3.1.1 Language of Page", "status": "supports",
             "passed_rules": ["html-has-lang"], "failed_rules": [], "review_rules": []}]
    assert _find(build_vpat(conf), "3.1.1")["conformance"] == SUPPORTS


def test_only_review_is_not_evaluated():
    conf = [{"criterion": "1.4.3 Contrast (Minimum)", "status": "needs_review",
             "passed_rules": [], "failed_rules": [], "review_rules": ["color-contrast"]}]
    assert _find(build_vpat(conf), "1.4.3")["conformance"] == NOT_EVALUATED


def test_summary_counts_add_up():
    rows = build_vpat([])
    summary = vpat_summary(rows)
    assert sum(summary.values()) == len(rows)
    assert summary[NOT_EVALUATED] == len(rows)  # nothing exercised => all not evaluated


def test_rows_sorted_numerically():
    rows = build_vpat([])
    nums = [r["num"] for r in rows]
    assert nums.index("1.4.3") < nums.index("1.4.10")


def test_render_html_is_self_contained_and_escaped():
    conf = [{"criterion": "1.4.3 Contrast (Minimum)", "status": "does_not_support",
             "passed_rules": [], "failed_rules": ["color-contrast"], "review_rules": []}]
    rows = build_vpat(conf)
    doc = render_vpat_html(url="https://example.com/<x>", page_title="Home & Co", scanned_at=None, rows=rows)
    assert doc.startswith("<!DOCTYPE html>")
    assert "Level A" in doc and "Level AA" in doc
    assert "&lt;x&gt;" in doc  # URL is HTML-escaped
    assert "Home &amp; Co" in doc
    assert "axe-core" in doc
