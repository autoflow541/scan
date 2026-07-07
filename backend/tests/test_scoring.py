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
