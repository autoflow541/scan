from app.wcag_map import primary_criterion


def test_picks_specific_criterion_over_level_tags():
    tags = ["wcag2aa", "wcag143", "cat.color"]
    assert primary_criterion(tags) == "1.4.3 Contrast (Minimum)"


def test_returns_none_when_no_known_criterion_tag():
    assert primary_criterion(["wcag2aa", "best-practice"]) is None


def test_unknown_wcag_tag_is_skipped_not_crashed_on():
    assert primary_criterion(["wcag9999", "wcag111"]) == "1.1.1 Non-text Content"
