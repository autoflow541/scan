from app.wcag_map import primary_criterion


def test_picks_specific_criterion_over_level_tags():
    tags = ["wcag2aa", "wcag143", "cat.color"]
    assert primary_criterion(tags) == "1.4.3 Contrast (Minimum)"


def test_returns_none_when_no_known_criterion_tag():
    assert primary_criterion(["wcag2aa", "best-practice"]) is None


def test_unknown_wcag_tag_is_skipped_not_crashed_on():
    assert primary_criterion(["wcag9999", "wcag111"]) == "1.1.1 Non-text Content"


def test_rule_id_override_used_when_no_tag_match():
    assert primary_criterion(["cat.semantics", "best-practice"], "heading-order") == "2.4.6 Headings and Labels"
    assert primary_criterion(["cat.keyboard", "best-practice"], "accesskeys") == "2.1.4 Character Key Shortcuts"


def test_rule_id_override_does_not_win_over_a_real_tag_match():
    assert primary_criterion(["wcag2aa", "wcag143"], "heading-order") == "1.4.3 Contrast (Minimum)"


def test_unmapped_rule_id_still_returns_none():
    assert primary_criterion(["best-practice"], "landmark-one-main") is None
