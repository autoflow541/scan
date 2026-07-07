"""Scan orchestration: launch headless Chromium, navigate to a validated URL,
inject axe-core, and shape the results into a ScanResult.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .axe_source import load_axe_source
from .conformance import build_conformance
from .models import ConformanceRow, Issue, IssueNode, PassItem, ScanResult
from .scoring import compute_score
from .url_safety import revalidate_landed_host, safe_resolve_target
from .wcag_map import primary_criterion

log = logging.getLogger(__name__)

_MAX_NODES_PER_ISSUE = 5
_MAX_HTML_CHARS = 300
_AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
_USER_AGENT = "AutoFlowAccessibilityScanner/1.0 (+https://scan.auto-flow.co)"

_AXE_RUN_SCRIPT = """
async () => {
  return await axe.run(document, {
    resultTypes: ["violations", "passes", "incomplete"],
    runOnly: { type: "tag", values: %s },
  });
}
""" % _AXE_TAGS


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
            page_title = await page.title()
            final_url = page.url
        finally:
            await browser.close()

    duration_ms = int((time.monotonic() - t0) * 1000)
    return _build_scan_result(url, final_url, page_title, axe_results, duration_ms)


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

    conformance = [ConformanceRow(**row) for row in build_conformance(violations, passes, incomplete)]

    return ScanResult(
        url=requested_url,
        final_url=final_url,
        page_title=page_title,
        scanned_at=datetime.now(timezone.utc),
        score=compute_score(violations),
        counts=counts,
        issues=issues,
        passes=pass_items,
        conformance=conformance,
        incomplete_count=len(incomplete),
        scan_duration_ms=duration_ms,
    )


_IMPACT_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
