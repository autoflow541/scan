"""Scan orchestration: launch headless Chromium, navigate to a validated URL,
inject axe-core, and shape the results into a ScanResult.
"""
from __future__ import annotations

import base64
import io
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from PIL import Image
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .axe_source import load_axe_source
from .conformance import build_conformance
from .contrast_check import evaluate_contrast
from .models import Bbox, ConformanceRow, Issue, IssueNode, PassItem, ScanResult, VpatRow
from .scoring import compute_score
from .state_checks import run_state_checks
from .url_safety import revalidate_landed_host, safe_resolve_target
from .vpat import build_vpat, vpat_summary
from .wcag_map import primary_criterion

log = logging.getLogger(__name__)

_MAX_NODES_PER_ISSUE = 5
_MAX_HTML_CHARS = 300
_AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
_USER_AGENT = "AutoFlowAccessibilityScanner/1.0 (+https://scan.auto-flow.co)"
# Pages taller than this (px) skip the full-page screenshot in favor of a
# viewport-only one -- guards against pathological/infinite-scroll pages
# blowing up capture time or memory on a memory-constrained instance.
_MAX_FULL_PAGE_HEIGHT = 8000

_AXE_RUN_SCRIPT = """
async () => {
  return await axe.run(document, {
    resultTypes: ["violations", "passes", "incomplete"],
    runOnly: { type: "tag", values: %s },
  });
}
""" % _AXE_TAGS

_BBOX_SCRIPT = """
(selectors) => selectors.map((sel) => {
  try {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return null;
    return { x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height };
  } catch (e) {
    return null;
  }
});
"""

# Computed text color + font metrics, used to resolve axe's "incomplete"
# color-contrast nodes by measuring the actual rendered screenshot pixels
# (see contrast_check.py for why axe can't always determine this itself).
_TEXT_STYLE_SCRIPT = """
(selectors) => selectors.map((sel) => {
  try {
    const el = document.querySelector(sel);
    if (!el) return null;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    const m = style.color.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const parts = m[1].split(',').map((s) => parseFloat(s.trim()));
    return {
      color: [Math.round(parts[0]), Math.round(parts[1]), Math.round(parts[2])],
      fontSize: parseFloat(style.fontSize) || 16,
      fontWeight: parseInt(style.fontWeight, 10) || 400,
      bbox: { x: rect.left + window.scrollX, y: rect.top + window.scrollY, width: rect.width, height: rect.height },
    };
  } catch (e) {
    return null;
  }
});
"""

_MAX_CONTRAST_NODES_TO_RESOLVE = 30


class ScanTimeoutError(Exception):
    """The scan did not complete within the allotted time."""


class ScanNavigationError(Exception):
    """The target page could not be loaded."""

    def __init__(self, reason: str, status_code: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


async def run_scan(url: str, *, nav_timeout_ms: int = 15_000, settle_timeout_ms: int = 5_000) -> ScanResult:
    t0 = time.monotonic()
    validated_url, pinned_ip = await safe_resolve_target(url)
    hostname = urlparse(validated_url).hostname

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                f"--host-resolver-rules=MAP {hostname} {pinned_ip}",
                "--disable-gpu",
            ],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=_USER_AGENT,
                ignore_https_errors=False,
            )
            page = await context.new_page()
            try:
                response = await page.goto(
                    validated_url, wait_until="domcontentloaded", timeout=nav_timeout_ms
                )
            except PlaywrightTimeoutError as exc:
                raise ScanTimeoutError(f"Navigation to {validated_url} timed out.") from exc
            except PlaywrightError as exc:
                reason = _classify_navigation_error(str(exc))
                raise ScanNavigationError(reason) from exc

            if response is None:
                raise ScanNavigationError("no_response")
            status = response.status
            if status >= 400:
                raise ScanNavigationError(f"http_{status}", status_code=status)

            # Redirect defense-in-depth: re-validate wherever we actually landed.
            await revalidate_landed_host(page.url)

            try:
                await page.wait_for_load_state("networkidle", timeout=settle_timeout_ms)
            except PlaywrightTimeoutError:
                pass  # best-effort settle; proceed with whatever rendered so far

            await page.add_script_tag(content=load_axe_source())
            axe_results = await page.evaluate(_AXE_RUN_SCRIPT)
            screenshot_bytes = await _capture_screenshot_bytes(page)
            axe_results = await _resolve_incomplete_contrast(page, axe_results, screenshot_bytes)
            # State-based checks (keyboard walk, 320px reflow) axe can't do on its
            # own; results are shaped like axe entries and merged in below.
            state = await run_state_checks(page)
            for bucket in ("violations", "passes", "incomplete"):
                axe_results.setdefault(bucket, []).extend(state.get(bucket, []))
            bboxes = await _compute_bboxes(page, axe_results.get("violations", []))
            page_title = await page.title()
            final_url = page.url
        finally:
            await browser.close()

    screenshot = (
        f"data:image/jpeg;base64,{base64.b64encode(screenshot_bytes).decode()}"
        if screenshot_bytes is not None
        else None
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    return _build_scan_result(url, final_url, page_title, axe_results, duration_ms, bboxes, screenshot)


async def _compute_bboxes(page: Page, violations: list[dict]) -> dict[str, dict]:
    """Bounding boxes (page-relative, matching a full-page screenshot's
    coordinate space) for violation nodes -- only for the simple case of a
    single plain CSS selector (same-document element). Cross-frame/shadow-DOM
    targets (where axe's target is a nested array) are skipped -- resolving
    those requires piercing into frames, out of scope for v1.
    """
    selectors = [
        n["target"][0]
        for v in violations
        for n in v.get("nodes", [])[:_MAX_NODES_PER_ISSUE]
        if len(n.get("target", [])) == 1 and isinstance(n["target"][0], str)
    ]
    if not selectors:
        return {}
    try:
        results = await page.evaluate(_BBOX_SCRIPT, selectors)
    except PlaywrightError:
        return {}
    return {sel: box for sel, box in zip(selectors, results) if box is not None}


async def _capture_screenshot_bytes(page: Page) -> bytes | None:
    """Full-page JPEG screenshot, used both for the frontend overlay and for
    sampling background pixels behind ambiguous-contrast text. Best-effort --
    a scan should still succeed even if the screenshot itself fails or the
    page is too unusual to capture.
    """
    try:
        page_height = await page.evaluate("document.documentElement.scrollHeight")
    except PlaywrightError:
        page_height = 0
    full_page = 0 < page_height <= _MAX_FULL_PAGE_HEIGHT

    try:
        return await page.screenshot(type="jpeg", quality=60, full_page=full_page, timeout=10_000)
    except PlaywrightError as exc:
        log.warning("Screenshot capture failed: %s", exc)
        return None


async def _resolve_incomplete_contrast(
    page: Page, axe_results: dict, screenshot_bytes: bytes | None
) -> dict:
    """axe-core marks color-contrast "incomplete" (needs manual review) when
    it can't read a plain CSS background color -- e.g. text over an image or
    gradient. Since we already have a rendered screenshot, sample the actual
    pixels instead and reclassify each node as a definite pass or violation,
    so it flows through the same conformance/scoring pipeline as everything
    axe *could* determine on its own.
    """
    if screenshot_bytes is None:
        return axe_results
    incomplete = axe_results.get("incomplete", [])
    idx = next((i for i, item in enumerate(incomplete) if item.get("id") == "color-contrast"), None)
    if idx is None:
        return axe_results

    item = incomplete[idx]
    nodes = item.get("nodes", [])
    eligible = [
        n for n in nodes if len(n.get("target", [])) == 1 and isinstance(n["target"][0], str)
    ]
    to_process = eligible[:_MAX_CONTRAST_NODES_TO_RESOLVE]
    if not to_process:
        return axe_results

    selectors = [n["target"][0] for n in to_process]
    try:
        style_info = await page.evaluate(_TEXT_STYLE_SCRIPT, selectors)
    except PlaywrightError:
        return axe_results

    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    resolved_pass: list[dict] = []
    resolved_fail: list[dict] = []
    unresolved: list[dict] = []
    for node, info in zip(to_process, style_info):
        result = (
            evaluate_contrast(image, info["bbox"], tuple(info["color"]), info["fontSize"], info["fontWeight"])
            if info is not None
            else None
        )
        if result is None:
            unresolved.append(node)
            continue
        node = dict(node)
        node["failureSummary"] = (
            f"Visually measured contrast ratio {result['ratio']:.2f}:1 "
            f"(needs {result['threshold']:.1f}:1) -- sampled from the rendered "
            "screenshot since the background couldn't be read from CSS alone "
            "(e.g. an image or gradient)."
        )
        (resolved_pass if result["passes"] else resolved_fail).append(node)

    processed_ids = {id(n) for n in to_process}
    leftover_nodes = [n for n in nodes if id(n) not in processed_ids] + unresolved
    if leftover_nodes:
        incomplete[idx] = {**item, "nodes": leftover_nodes}
    else:
        incomplete.pop(idx)

    if resolved_fail:
        _merge_nodes_into(axe_results.setdefault("violations", []), item, resolved_fail, default_impact="serious")
    if resolved_pass:
        _merge_nodes_into(axe_results.setdefault("passes", []), item, resolved_pass)

    return axe_results


def _merge_nodes_into(
    target_list: list[dict], template: dict, nodes: list[dict], default_impact: str | None = None
) -> None:
    existing = next((entry for entry in target_list if entry.get("id") == template.get("id")), None)
    if existing is not None:
        existing.setdefault("nodes", []).extend(nodes)
        return
    new_entry = {**template, "nodes": nodes}
    if default_impact is not None:
        new_entry["impact"] = default_impact
    target_list.append(new_entry)


def _classify_navigation_error(message: str) -> str:
    lowered = message.lower()
    if "err_name_not_resolved" in lowered:
        return "dns_failure"
    if "err_connection_refused" in lowered:
        return "connection_refused"
    if "err_connection_timed_out" in lowered:
        return "connection_timed_out"
    if "err_cert" in lowered or "ssl" in lowered:
        return "tls_error"
    return "navigation_failed"


def _build_scan_result(
    requested_url: str,
    final_url: str,
    page_title: str,
    axe_results: dict,
    duration_ms: int,
    bboxes: dict[str, dict],
    screenshot: str | None,
) -> ScanResult:
    violations = axe_results.get("violations", [])
    passes = axe_results.get("passes", [])
    incomplete = axe_results.get("incomplete", [])

    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    issues: list[Issue] = []
    for v in sorted(violations, key=lambda v: _IMPACT_ORDER.get(v.get("impact"), 99)):
        impact = v.get("impact") or "minor"
        counts[impact] = counts.get(impact, 0) + 1
        nodes = v.get("nodes", [])
        issues.append(
            Issue(
                id=v.get("id", ""),
                impact=impact,
                wcag_criterion=primary_criterion(v.get("tags", [])),
                tags=v.get("tags", []),
                description=v.get("description", ""),
                help=v.get("help", ""),
                help_url=v.get("helpUrl", ""),
                node_count=len(nodes),
                nodes=[
                    IssueNode(
                        html=(n.get("html") or "")[:_MAX_HTML_CHARS],
                        target=n.get("target", []),
                        failure_summary=n.get("failureSummary"),
                        bbox=Bbox(**bboxes[n["target"][0]])
                        if len(n.get("target", [])) == 1 and n["target"][0] in bboxes
                        else None,
                    )
                    for n in nodes[:_MAX_NODES_PER_ISSUE]
                ],
            )
        )

    pass_items = [
        PassItem(
            id=p.get("id", ""),
            wcag_criterion=primary_criterion(p.get("tags", [])),
            tags=p.get("tags", []),
            description=p.get("description", ""),
            help=p.get("help", ""),
            help_url=p.get("helpUrl", ""),
            node_count=len(p.get("nodes", [])),
        )
        for p in sorted(passes, key=lambda p: p.get("id", ""))
    ]

    conformance_rows = build_conformance(violations, passes, incomplete)
    conformance = [ConformanceRow(**row) for row in conformance_rows]

    vpat_rows = build_vpat(conformance_rows)
    vpat = [VpatRow(**row) for row in vpat_rows]

    return ScanResult(
        url=requested_url,
        final_url=final_url,
        page_title=page_title,
        scanned_at=datetime.now(timezone.utc),
        score=compute_score(conformance_rows),
        counts=counts,
        issues=issues,
        passes=pass_items,
        conformance=conformance,
        vpat=vpat,
        vpat_summary=vpat_summary(vpat_rows),
        incomplete_count=len(incomplete),
        scan_duration_ms=duration_ms,
        screenshot=screenshot,
    )


_IMPACT_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
