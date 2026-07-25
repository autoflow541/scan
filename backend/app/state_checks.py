"""State-based accessibility checks that axe-core cannot perform.

axe-core evaluates the DOM in a single rendered state. Several WCAG criteria
only reveal problems when the page is put into a *different* state -- narrowed
to a mobile viewport, or driven by the keyboard. These checks reuse the same
Playwright page axe ran against and emit results in axe's shape (id, tags with
a `wcagNNN` criterion tag, nodes) so they merge straight into the existing
conformance / VPAT / scoring pipeline.

Criteria added here:
  1.4.10 Reflow                  -- horizontal scrolling at a 320px viewport
  2.4.3  Focus Order             -- positive tabindex disrupts tab order
  2.4.7  Focus Visible           -- keyboard-focused element shows no indicator
  2.1.2  No Keyboard Trap        -- focus gets stuck while tabbing (review)
  2.4.11 Focus Not Obscured      -- focused element hidden behind fixed UI (review)
  4.1.3  Status Messages         -- live-region markup present (review only)

Everything is best-effort: any failure here is swallowed so a state-check bug
can never take down a scan that axe already completed.
"""
from __future__ import annotations

import logging

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

log = logging.getLogger(__name__)

_MOBILE_WIDTH = 320
_MOBILE_HEIGHT = 512
_DESKTOP = {"width": 1280, "height": 800}
_MAX_TABS = 60
_MAX_NODES = 8

_UNDERSTAND = "https://www.w3.org/WAI/WCAG22/Understanding"

# Shared JS helpers injected into each evaluate call.
_PRELUDE = r"""
const cssPath = (el) => {
  if (!el || el.nodeType !== 1) return '';
  if (el.id) return '#' + CSS.escape(el.id);
  const parts = [];
  let node = el;
  while (node && node.nodeType === 1 && parts.length < 5) {
    let sel = node.tagName.toLowerCase();
    if (node.classList.length) sel += '.' + [...node.classList].slice(0, 2).map(c => CSS.escape(c)).join('.');
    const parent = node.parentNode;
    if (parent && parent.children) {
      const sibs = [...parent.children].filter(c => c.tagName === node.tagName);
      if (sibs.length > 1) sel += ':nth-of-type(' + (sibs.indexOf(node) + 1) + ')';
    }
    parts.unshift(sel);
    node = node.parentElement;
  }
  return parts.join(' > ');
};
const isVisible = (el) => {
  const r = el.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return false;
  const cs = getComputedStyle(el);
  return cs.visibility !== 'hidden' && cs.display !== 'none';
};
"""


def _entry(rule_id, criterion_tag, level_tag, impact, description, help_text, url_slug, nodes):
    return {
        "id": rule_id,
        "impact": impact,
        "tags": ["cat.state", level_tag, criterion_tag],
        "description": description,
        "help": help_text,
        "helpUrl": f"{_UNDERSTAND}/{url_slug}.html",
        "nodes": nodes,
    }


def _node(html_str, selector, summary):
    return {"html": (html_str or "")[:300], "target": [selector], "failureSummary": summary}


async def run_state_checks(page: Page) -> dict[str, list]:
    """Return {'violations', 'passes', 'incomplete'} from state-based checks."""
    out: dict[str, list] = {"violations": [], "passes": [], "incomplete": []}
    try:
        await _focus_order(page, out)
        await _keyboard_walk(page, out)
        await _reflow(page, out)
        await _status_messages(page, out)
    except PlaywrightError as exc:  # pragma: no cover - defensive
        log.warning("state checks aborted: %s", exc)
    except Exception:  # pragma: no cover - never break a completed scan
        log.exception("unexpected error in state checks")
    return out


async def _focus_order(page: Page, out: dict) -> None:
    """2.4.3 Focus Order -- positive tabindex forces an author-defined tab
    sequence that almost always diverges from DOM/visual order."""
    script = "(() => {" + _PRELUDE + r"""
      const bad = [];
      for (const el of document.querySelectorAll('[tabindex]')) {
        const ti = parseInt(el.getAttribute('tabindex'), 10);
        if (Number.isFinite(ti) && ti > 0) bad.push({ html: el.outerHTML, sel: cssPath(el), ti });
      }
      return bad.slice(0, 8);
    })()"""
    bad = await page.evaluate(script)
    if bad:
        nodes = [
            _node(b["html"], b["sel"], f"Uses tabindex=\"{b['ti']}\" (positive), which overrides natural focus order.")
            for b in bad
        ]
        out["violations"].append(_entry(
            "af-focus-order-tabindex", "wcag243", "wcag2a", "serious",
            "Elements use a positive tabindex, which disrupts the natural focus order.",
            "Remove positive tabindex values; order elements in the DOM instead.",
            "focus-order", nodes,
        ))
    else:
        out["passes"].append(_entry(
            "af-focus-order-tabindex", "wcag243", "wcag2a", None,
            "No positive tabindex values found; tab order follows DOM order.",
            "Keep focus order aligned with DOM order.", "focus-order", [],
        ))


async def _keyboard_walk(page: Page, out: dict) -> None:
    """Tab through the page once, collecting three signals:
      2.4.7  focused elements with no visible focus indicator (violation)
      2.1.2  focus getting stuck on one element (review)
      2.4.11 focused element obscured by fixed/sticky UI (review)
    """
    try:
        count = await page.evaluate(
            "() => document.querySelectorAll('a[href],button,input,select,textarea,[tabindex],[contenteditable=\"true\"]').length"
        )
    except PlaywrightError:
        return
    if not count:
        return
    await page.evaluate("() => { try { document.activeElement && document.activeElement.blur(); } catch(e){} window.scrollTo(0,0); }")

    info_script = "(() => {" + _PRELUDE + r"""
      const el = document.activeElement;
      if (!el || el === document.body || el === document.documentElement) return null;
      const cs = getComputedStyle(el);
      const ow = parseFloat(cs.outlineWidth) || 0;
      const hasOutline = cs.outlineStyle !== 'none' && (cs.outlineStyle === 'auto' || ow > 0);
      const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
      const visible = hasOutline || hasShadow;
      const r = el.getBoundingClientRect();
      let obscured = false;
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (r.width > 0 && r.height > 0 && cx >= 0 && cy >= 0 && cx <= innerWidth && cy <= innerHeight) {
        const top = document.elementFromPoint(cx, cy);
        obscured = !!(top && top !== el && !el.contains(top) && !top.contains(el));
      }
      return { sel: cssPath(el), html: el.outerHTML.slice(0, 200), visible, obscured, focusable: isVisible(el) };
    })()"""

    max_tabs = min(max(count + 3, 5), _MAX_TABS)
    no_indicator: list[dict] = []
    obscured_nodes: list[dict] = []
    distinct: set[str] = set()
    prev = None
    same_run = 0
    trapped_on: dict | None = None
    walked = False

    for i in range(max_tabs):
        try:
            await page.keyboard.press("Tab")
            info = await page.evaluate(info_script)
        except PlaywrightError:
            break
        if not info:
            prev = None
            same_run = 0
            continue
        walked = True
        sel = info["sel"]
        distinct.add(sel)
        if sel == prev:
            same_run += 1
            if same_run >= 5 and i < max_tabs - 1 and len(distinct) <= 2:
                trapped_on = info
                break
        else:
            same_run = 0
        prev = sel
        if not info["visible"] and info["focusable"] and len(no_indicator) < _MAX_NODES:
            no_indicator.append(info)
        if info["obscured"] and len(obscured_nodes) < _MAX_NODES:
            obscured_nodes.append(info)

    if not walked:
        return

    # 2.4.7 Focus Visible
    if no_indicator:
        nodes = [_node(n["html"], n["sel"], "Keyboard-focused, but no visible focus indicator (no outline or box-shadow).") for n in no_indicator]
        out["violations"].append(_entry(
            "af-focus-visible", "wcag247", "wcag2aa", "serious",
            "Some elements show no visible focus indicator when focused by keyboard.",
            "Provide a clear :focus-visible outline or box-shadow on all interactive elements.",
            "focus-visible", nodes,
        ))
    else:
        out["passes"].append(_entry(
            "af-focus-visible", "wcag247", "wcag2aa", None,
            "All keyboard-focused elements showed a visible focus indicator.",
            "Keep a visible focus indicator on interactive elements.", "focus-visible", [],
        ))

    # 2.1.2 No Keyboard Trap (review, low-confidence)
    if trapped_on:
        out["incomplete"].append(_entry(
            "af-keyboard-trap", "wcag212", "wcag2a", "critical",
            "Keyboard focus may be trapped: tabbing did not move past an element. Verify manually.",
            "Ensure focus can always move away from any component using the keyboard.",
            "no-keyboard-trap", [_node(trapped_on["html"], trapped_on["sel"], "Focus stayed on this element across repeated Tab presses.")],
        ))
    else:
        out["passes"].append(_entry(
            "af-keyboard-trap", "wcag212", "wcag2a", None,
            "Keyboard tabbing moved through the page without getting stuck.",
            "Ensure focus is never trapped.", "no-keyboard-trap", [],
        ))

    # 2.4.11 Focus Not Obscured (review, geometry heuristic)
    if obscured_nodes:
        nodes = [_node(n["html"], n["sel"], "When focused, this element appears covered by another (e.g. a sticky header). Verify manually.") for n in obscured_nodes]
        out["incomplete"].append(_entry(
            "af-focus-not-obscured", "wcag2411", "wcag22aa", "serious",
            "A keyboard-focused element may be hidden behind fixed/sticky content. Verify manually.",
            "Ensure focused elements are not entirely hidden by author-created content such as sticky headers.",
            "focus-not-obscured-minimum", nodes,
        ))
    else:
        out["passes"].append(_entry(
            "af-focus-not-obscured", "wcag2411", "wcag22aa", None,
            "No keyboard-focused element was found obscured by fixed content.",
            "Keep focused elements visible.", "focus-not-obscured-minimum", [],
        ))


async def _reflow(page: Page, out: dict) -> None:
    """1.4.10 Reflow -- at a 320px-wide viewport, content should not require
    horizontal (two-dimensional) scrolling."""
    try:
        await page.set_viewport_size({"width": _MOBILE_WIDTH, "height": _MOBILE_HEIGHT})
        await page.wait_for_timeout(250)
        script = "(() => {" + _PRELUDE + r"""
          const de = document.documentElement;
          const overflow = Math.max(0, de.scrollWidth - de.clientWidth);
          const offenders = [];
          if (overflow > 5) {
            const vw = de.clientWidth;
            const all = document.body ? document.body.querySelectorAll('*') : [];
            for (const el of all) {
              const r = el.getBoundingClientRect();
              if (r.width > 1 && r.right > vw + 5 && r.width <= de.scrollWidth) {
                offenders.push({ html: el.outerHTML, sel: cssPath(el) });
                if (offenders.length >= 6) break;
              }
            }
          }
          return { overflow, clientWidth: de.clientWidth, scrollWidth: de.scrollWidth, offenders };
        })()"""
        res = await page.evaluate(script)
    except PlaywrightError:
        return
    finally:
        try:
            await page.set_viewport_size(_DESKTOP)
        except PlaywrightError:
            pass

    if res["overflow"] > 5:
        offenders = res.get("offenders", [])
        nodes = [_node(o["html"], o["sel"], f"Extends beyond the {_MOBILE_WIDTH}px viewport, forcing horizontal scrolling.") for o in offenders]
        if not nodes:
            nodes = [_node("<html>", "html", f"Page is {res['scrollWidth']}px wide at a {res['clientWidth']}px viewport, requiring horizontal scrolling.")]
        out["violations"].append(_entry(
            "af-reflow", "wcag1410", "wcag21aa", "serious",
            f"Content requires horizontal scrolling at a {_MOBILE_WIDTH}px viewport (overflows by {res['overflow']}px).",
            "Use responsive layout so content reflows to a single column at 320px without horizontal scrolling.",
            "reflow", nodes,
        ))
    else:
        out["passes"].append(_entry(
            "af-reflow", "wcag1410", "wcag21aa", None,
            f"Content reflowed to the {_MOBILE_WIDTH}px viewport without horizontal scrolling.",
            "Keep layouts responsive down to 320px.", "reflow", [],
        ))


async def _status_messages(page: Page, out: dict) -> None:
    """4.1.3 Status Messages -- positive-detection only. Finding live-region
    markup (role="status"/"alert"/"log" or aria-live) proves nothing about
    whether messages are actually announced correctly, so a hit is flagged
    for manual review, never a pass. Finding none proves nothing either --
    a page can add live regions dynamically, after some interaction this
    scan never triggers -- so absence emits nothing at all and the criterion
    stays honestly "Not Evaluated" rather than a false "Not Applicable"."""
    script = "(() => {" + _PRELUDE + r"""
      const els = document.querySelectorAll(
        '[role="status"],[role="alert"],[role="log"],[aria-live]:not([aria-live="off"])'
      );
      const found = [];
      for (const el of els) {
        found.push({ html: el.outerHTML, sel: cssPath(el) });
        if (found.length >= 8) break;
      }
      return found;
    })()"""
    try:
        found = await page.evaluate(script)
    except PlaywrightError:
        return
    if not found:
        return
    nodes = [
        _node(f["html"], f["sel"], "Live-region markup found; verify status messages are actually announced by assistive technology.")
        for f in found
    ]
    out["incomplete"].append(_entry(
        "af-status-messages", "wcag413", "wcag21aa", "moderate",
        "Live-region markup (role/aria-live) is present. Automated checks can't verify assistive technology actually announces these messages -- verify manually.",
        "Confirm status messages are announced without moving keyboard focus.",
        "status-messages", nodes,
    ))
