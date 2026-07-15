import asyncio

from app.scanner import _compute_bboxes


class _FakePage:
    """Records the selectors it was asked to locate and returns a fixed bbox
    for each -- enough to verify _compute_bboxes' filtering without a real
    browser."""

    def __init__(self):
        self.requested_selectors: list[str] | None = None

    async def evaluate(self, script, selectors):
        self.requested_selectors = selectors
        return [{"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0} for _ in selectors]


def _violation(rule_id, selector):
    return {"id": rule_id, "nodes": [{"target": [selector]}]}


def test_af_reflow_violations_are_excluded_from_bbox_lookup():
    # af-reflow measures overflow at a 320px viewport (state_checks._reflow),
    # but bboxes are queried after the viewport is restored to desktop width
    # -- a bbox for it would show the element's normal desktop position, not
    # the overflow that was actually detected. See scanner._compute_bboxes.
    page = _FakePage()
    violations = [
        _violation("af-reflow", ".wide-thing"),
        _violation("color-contrast", ".low-contrast-text"),
    ]
    result = asyncio.run(_compute_bboxes(page, violations))

    assert page.requested_selectors == [".low-contrast-text"]
    assert ".wide-thing" not in result
    assert ".low-contrast-text" in result


def test_normal_violations_still_get_bboxes():
    page = _FakePage()
    violations = [_violation("image-alt", ".missing-alt")]
    result = asyncio.run(_compute_bboxes(page, violations))
    assert result[".missing-alt"] == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}


def test_no_selectors_skips_the_evaluate_call():
    page = _FakePage()
    result = asyncio.run(_compute_bboxes(page, [_violation("af-reflow", ".only-reflow")]))
    assert result == {}
    assert page.requested_selectors is None
