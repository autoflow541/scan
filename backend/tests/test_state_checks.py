import asyncio

from app.conformance import build_conformance
from app.state_checks import run_state_checks
from app.vpat import DOES_NOT, build_vpat
from app.wcag_map import primary_criterion


class FakePage:
    """Scripts Playwright's `evaluate`/keyboard/viewport calls so the state
    checks can be exercised without a real browser. Returns are dispatched by
    matching on distinctive substrings of each injected script."""

    def __init__(self, *, tabindex_bad=None, count=3, infos=None, reflow=None):
        self._tabindex_bad = tabindex_bad or []
        self._count = count
        self._infos = list(infos or [])
        self._reflow = reflow or {"overflow": 0, "clientWidth": 320, "scrollWidth": 320, "offenders": []}
        self.keyboard = self

    async def evaluate(self, script, *args):
        s = script
        if "document.querySelectorAll('a[href]" in s:
            return self._count
        if "blur()" in s and "scrollTo" in s:
            return None
        if "getAttribute('tabindex')" in s and "bad" in s:
            return self._tabindex_bad
        if "obscured" in s and "activeElement" in s:
            return self._infos.pop(0) if self._infos else None
        if "overflow" in s and "offenders" in s:
            return self._reflow
        return None

    async def press(self, key):
        return None

    async def set_viewport_size(self, size):
        return None

    async def wait_for_timeout(self, ms):
        return None


def _ids(entries):
    return {e["id"] for e in entries}


def _criteria(entries):
    return {primary_criterion(e["tags"]) for e in entries}


def test_clean_page_passes_all_state_criteria():
    page = FakePage(
        tabindex_bad=[],
        count=2,
        infos=[
            {"sel": "a", "html": "<a>", "visible": True, "obscured": False, "focusable": True},
            {"sel": "button", "html": "<button>", "visible": True, "obscured": False, "focusable": True},
        ],
        reflow={"overflow": 0, "clientWidth": 320, "scrollWidth": 320, "offenders": []},
    )
    out = asyncio.run(run_state_checks(page))
    assert out["violations"] == []
    assert out["incomplete"] == []
    passed = _criteria(out["passes"])
    for sc in ("2.4.3 Focus Order", "2.4.7 Focus Visible", "2.1.2 No Keyboard Trap",
               "1.4.10 Reflow", "2.4.11 Focus Not Obscured (Minimum)"):
        assert sc in passed


def test_problems_are_flagged_on_correct_criteria():
    page = FakePage(
        tabindex_bad=[{"html": '<div tabindex="3">', "sel": "div", "ti": 3}],
        count=1,
        infos=[{"sel": "a.x", "html": "<a class=x>", "visible": False, "obscured": True, "focusable": True}],
        reflow={"overflow": 140, "clientWidth": 320, "scrollWidth": 460,
                "offenders": [{"html": "<table>", "sel": "table"}]},
    )
    out = asyncio.run(run_state_checks(page))

    assert "af-focus-order-tabindex" in _ids(out["violations"])
    assert "af-focus-visible" in _ids(out["violations"])
    assert "af-reflow" in _ids(out["violations"])
    # Focus-not-obscured is review-grade, not a hard violation.
    assert "af-focus-not-obscured" in _ids(out["incomplete"])

    vio_criteria = _criteria(out["violations"])
    assert "2.4.3 Focus Order" in vio_criteria
    assert "2.4.7 Focus Visible" in vio_criteria
    assert "1.4.10 Reflow" in vio_criteria


def test_results_flow_through_conformance_and_vpat():
    page = FakePage(
        tabindex_bad=[{"html": '<div tabindex="2">', "sel": "div", "ti": 2}],
        count=1,
        infos=[{"sel": "a", "html": "<a>", "visible": False, "obscured": False, "focusable": True}],
        reflow={"overflow": 200, "clientWidth": 320, "scrollWidth": 520, "offenders": []},
    )
    out = asyncio.run(run_state_checks(page))
    rows = build_conformance(out["violations"], out["passes"], out["incomplete"])
    vpat = build_vpat(rows)
    by_num = {r["num"]: r for r in vpat}
    # These criteria were previously "Not Evaluated"; now they carry a verdict.
    assert by_num["1.4.10"]["conformance"] == DOES_NOT
    assert by_num["2.4.7"]["conformance"] == DOES_NOT
    assert by_num["2.4.3"]["conformance"] == DOES_NOT
