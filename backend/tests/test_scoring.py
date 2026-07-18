from app.scoring import compute_score


def test_no_criteria_tested_scores_100():
    assert compute_score([]) == 100


def test_all_criteria_support_scores_100():
    rows = [{"status": "supports"}, {"status": "supports"}]
    assert compute_score(rows) == 100


def test_all_criteria_fail_scores_0():
    rows = [{"status": "does_not_support"}, {"status": "does_not_support"}]
    assert compute_score(rows) == 0


def test_score_is_percentage_of_criteria_supporting():
    rows = [
        {"status": "supports"},
        {"status": "supports"},
        {"status": "supports"},
        {"status": "does_not_support"},
    ]
    assert compute_score(rows) == 75


def test_needs_review_does_not_count_as_supporting():
    rows = [{"status": "supports"}, {"status": "needs_review"}]
    assert compute_score(rows) == 50


def test_not_applicable_excluded_from_denominator():
    """A page with no video shouldn't score lower for "not supporting"
    caption criteria that don't even apply to it."""
    rows = [{"status": "supports"}, {"status": "not_applicable"}]
    assert compute_score(rows) == 100


def test_not_applicable_does_not_offset_a_real_failure():
    rows = [{"status": "does_not_support"}, {"status": "not_applicable"}]
    assert compute_score(rows) == 0


def test_all_not_applicable_scores_100():
    rows = [{"status": "not_applicable"}, {"status": "not_applicable"}]
    assert compute_score(rows) == 100
