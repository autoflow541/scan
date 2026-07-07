"""Scan orchestration: launch headless Chromium, navigate to a validated URL,
inject axe-core, and shape the results into a ScanResult.
"""
from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .axe_source import load_axe_source
from .conformance import build_conformance
from .models import Bbox, ConformanceRow, Issue, IssueNode, PassItem, ScanResult
from .scoring import compute_score
from .url_safety import revalidate_landed_host, safe_resolve_target
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
            bboxes = await _compute_bboxes(page, axe_results.get("violations", []))
            screenshot = await _capture_screenshot(page)
            page_title = await page.title()
            final_url = page.url
        finally:
            await browser.close()

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


async def _capture_screenshot(page: Page) -> str | None:
    """Full-page JPEG screenshot as a data URI, for overlaying issue bounding
    boxes on the frontend. Best-effort -- a scan should still succeed even if
    the screenshot itself fails or the page is too unusual to capture.
    """
    try:
        page_height = await page.evaluate("document.documentElement.scrollHeight")
    except PlaywrightError:
        page_height = 0
    full_page = 0 < page_height <= _MAX_FULL_PAGE_HEIGHT

    try:
        image_bytes = await page.screenshot(type="jpeg", quality=60, full_page=full_page, timeout=10_000)
    except PlaywrightError as exc:
        log.warning("Screenshot capture failed: %s", exc)
        return None
    return f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"


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
        incomplete_count=len(incomplete),
        scan_duration_ms=duration_ms,
        screenshot=screenshot,
    )


_IMPACT_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
