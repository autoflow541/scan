"""FastAPI app for the free WCAG accessibility scanner (scan.auto-flow.co)."""
from __future__ import annotations

import asyncio
import logging
import os
import time

from .log_config import configure as _configure_logging
_configure_logging()
log = logging.getLogger(__name__)

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .csv_export import issues_to_csv
from .leads import InvalidEmailError, record_lead, validate_email
from .models import LeadRequest, ScanRequest, ScanResult
from .rate_limit import RateLimiter
from .scanner import ScanNavigationError, ScanTimeoutError, run_scan
from .url_safety import UrlValidationError
from .vpat import render_vpat_html

_API_KEY = os.environ.get("API_KEY", "")  # unused for this public tool; kept for parity with remediation
_OPEN_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

_TAGS = [
    {"name": "core", "description": "Submit a URL, get a WCAG accessibility scan report."},
    {"name": "status", "description": "Health check."},
]

app = FastAPI(
    title="Auto-Flow Accessibility Scanner API",
    version="0.1.0",
    description=(
        "Free, instant, single-page WCAG accessibility scan. Renders the page "
        "with headless Chromium and runs axe-core against the DOM.\n\n"
        "Public endpoint -- rate limited per IP, no auth required."
    ),
    openapi_tags=_TAGS,
)

_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _auth(request: Request, call_next):
    """Enforce API key when API_KEY env var is set (unused by default)."""
    if _API_KEY and request.url.path not in _OPEN_PATHS:
        provided = request.headers.get("X-API-Key", "")
        if provided != _API_KEY:
            return JSONResponse({"detail": "Invalid or missing API key. Pass X-API-Key header."}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    log.info("%s %s -> %d  (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


_rate_limiter = RateLimiter(capacity=5, refill_per_sec=1 / 30)
_scan_semaphore = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_SCANS", "3")))
_SEMAPHORE_WAIT_S = 2.0
_OVERALL_TIMEOUT_S = 35.0

# /vpat and /issues.csv don't launch a browser (cheap string formatting), so
# they get a more generous limit than /scan -- but unlike /scan they had NO
# rate limiting at all before, which let anyone hammer them for free with
# arbitrary client-supplied JSON bodies. A separate bucket keeps that traffic
# from being able to starve real scans' tokens on the main limiter.
_export_rate_limiter = RateLimiter(capacity=20, refill_per_sec=1 / 5)

# Deliberately tight -- a real visitor submits this once per scan at most;
# anything bursty here is spam, not legitimate use.
_lead_rate_limiter = RateLimiter(capacity=3, refill_per_sec=1 / 60)


def _client_ip(request: Request) -> str:
    """The real visitor IP, for per-IP rate limiting.

    In production this process is only reachable through Caddy (the
    container binds 127.0.0.1:8001 -- see deploy/setup-vm.sh -- so nothing
    external can hit it directly), and Caddy's reverse_proxy sets
    X-Forwarded-For on every request by default. Without this, every request
    arrives from Caddy's own connection and request.client.host is the same
    for every visitor -- meaning everyone would share one rate-limit bucket
    instead of getting their own, so one busy visitor could lock everyone
    else out.

    Take the LAST entry, not the first. Caddy *appends* to any
    X-Forwarded-For a client already sent rather than replacing it, so nothing
    stops a client from sending their own "X-Forwarded-For: 1.2.3.4" directly.
    With exactly one trusted hop in front of this process, the last entry is
    the one Caddy itself added from the real TCP connection -- the only value
    a client can't forge. Taking the first entry would trust attacker-supplied
    data and make the limiter trivially bypassable by rotating a fake value
    on every request -- worse than not reading the header at all.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@app.get("/health", tags=["status"], summary="Health check")
def health() -> dict:
    return {"status": "ok"}


@app.post("/scan", response_model=ScanResult, tags=["core"], summary="Scan a single URL for WCAG accessibility issues")
async def scan(req: ScanRequest, request: Request) -> ScanResult:
    client_ip = _client_ip(request)
    if not _rate_limiter.check(client_ip):
        log.warning("Rate limited: ip=%s url=%r", client_ip, req.url)
        raise HTTPException(
            status_code=429,
            detail="Too many scans from this address. Try again in a bit.",
            headers={"Retry-After": "30"},
        )

    try:
        acquired = False
        try:
            await asyncio.wait_for(_scan_semaphore.acquire(), timeout=_SEMAPHORE_WAIT_S)
            acquired = True
        except asyncio.TimeoutError:
            log.warning("Scanner busy, rejected: ip=%s url=%r", client_ip, req.url)
            raise HTTPException(status_code=503, detail="Scanner is busy. Try again shortly.")

        try:
            result = await asyncio.wait_for(run_scan(req.url), timeout=_OVERALL_TIMEOUT_S)
        finally:
            if acquired:
                _scan_semaphore.release()
    except UrlValidationError as exc:
        log.info("Rejected URL: ip=%s url=%r reason=%s", client_ip, req.url, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScanNavigationError as exc:
        log.info("Navigation failed: ip=%s url=%r reason=%s", client_ip, req.url, exc.reason)
        if exc.reason == "script_injection_blocked":
            detail = "This page's security policy blocks our scanner from running (a strict Content-Security-Policy). We couldn't test it automatically -- a manual audit can still cover it."
        else:
            detail = f"Could not load that page ({exc.reason})."
        raise HTTPException(status_code=422, detail=detail) from exc
    except (ScanTimeoutError, asyncio.TimeoutError):
        log.warning("Scan timed out: ip=%s url=%r", client_ip, req.url)
        raise HTTPException(status_code=504, detail="Scan timed out. The page may be too slow or unreachable.")

    log.info(
        "SCAN done ip=%s url=%r score=%d issues=%d duration_ms=%d",
        client_ip, req.url, result.score, len(result.issues), result.scan_duration_ms,
    )
    return result


@app.post(
    "/vpat",
    tags=["core"],
    summary="Render a downloadable Digital VPAT (Accessibility Conformance Report) from a scan result",
    response_class=HTMLResponse,
)
async def vpat(result: ScanResult, request: Request) -> HTMLResponse:
    """Turn a ScanResult (obtained from /scan) into a standalone, downloadable
    HTML VPAT / ACR document. Stateless formatting only -- no browser launch,
    so it's on a lighter, separate rate limit than /scan rather than none.
    """
    client_ip = _client_ip(request)
    if not _export_rate_limiter.check(client_ip):
        log.warning("Export rate limited: ip=%s path=%s", client_ip, request.url.path)
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a bit.", headers={"Retry-After": "5"})
    doc = render_vpat_html(
        url=result.url,
        page_title=result.page_title,
        scanned_at=result.scanned_at,
        rows=[row.model_dump() for row in result.vpat],
    )
    filename = "accessibility-conformance-report.html"
    return HTMLResponse(
        content=doc,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post(
    "/issues.csv",
    tags=["core"],
    summary="Export a scan result's issues as CSV (one row per element)",
)
async def issues_csv(result: ScanResult, request: Request) -> Response:
    """Turn a ScanResult (from /scan) into a downloadable CSV worklist -- one
    row per offending element. Stateless formatting only; no scanning."""
    client_ip = _client_ip(request)
    if not _export_rate_limiter.check(client_ip):
        log.warning("Export rate limited: ip=%s path=%s", client_ip, request.url.path)
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a bit.", headers={"Retry-After": "5"})
    csv_text = issues_to_csv(result)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="accessibility-issues.csv"'},
    )


@app.post("/lead", tags=["core"], summary="Capture a lead from the CTA band")
async def lead(req: LeadRequest, request: Request) -> dict:
    """Someone liked what the scan showed and wants to be contacted about a
    full audit. No email service wired up yet (see leads.py) -- appended to
    a host-mounted file for now; check it via the deploy docs."""
    client_ip = _client_ip(request)
    if not _lead_rate_limiter.check(client_ip):
        log.warning("Lead rate limited: ip=%s", client_ip)
        raise HTTPException(status_code=429, detail="Too many requests. Try again in a bit.", headers={"Retry-After": "60"})
    try:
        email = validate_email(req.email)
    except InvalidEmailError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        record_lead(email=email, scanned_url=req.scanned_url, score=req.score, client_ip=client_ip)
    except OSError:
        raise HTTPException(status_code=500, detail="Couldn't save that right now. Please try again shortly.")
    return {"status": "ok"}


# Serve the built frontend (React/Vite) from the same container/process as the
# API -- one deployable service, no separate static host or reverse proxy
# needed. The Docker build copies frontend/dist here (see docker/Dockerfile);
# in local dev without a build present, skip the mount so `uvicorn` still
# starts (the frontend is served by its own `npm run dev` instead). Routes
# above are matched before this catch-all mount, so /health and /scan still
# resolve to the API handlers.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
