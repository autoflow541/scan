from app.scoring import compute_score


def test_no_violations_scores_100():
    assert compute_score([]) == 100


def test_critical_violation_reduces_score():
    violations = [{"impact": "critical", "nodes": [{}]}]
    assert compute_score(violations) == 90


def test_score_floors_at_zero():
    violations = [{"impact": "critical", "nodes": [{}] * 20}]
    assert compute_score(violations) == 0


def test_more_nodes_lowers_score_further():
    one_node = compute_score([{"impact": "moderate", "nodes": [{}]}])
    three_nodes = compute_score([{"impact": "moderate", "nodes": [{}, {}, {}]}])
    assert three_nodes < one_node
