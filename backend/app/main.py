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
from .models import ScanRequest, ScanResult
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


@app.get("/health", tags=["status"], summary="Health check")
def health() -> dict:
    return {"status": "ok"}


@app.post("/scan", response_model=ScanResult, tags=["core"], summary="Scan a single URL for WCAG accessibility issues")
async def scan(req: ScanRequest, request: Request) -> ScanResult:
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.check(client_ip):
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
            raise HTTPException(status_code=503, detail="Scanner is busy. Try again shortly.")

        try:
            result = await asyncio.wait_for(run_scan(req.url), timeout=_OVERALL_TIMEOUT_S)
        finally:
            if acquired:
                _scan_semaphore.release()
    except UrlValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScanNavigationError as exc:
        raise HTTPException(status_code=422, detail=f"Could not load that page ({exc.reason}).") from exc
    except (ScanTimeoutError, asyncio.TimeoutError):
        raise HTTPException(status_code=504, detail="Scan timed out. The page may be too slow or unreachable.")

    log.info("SCAN done url=%r score=%d issues=%d", req.url, result.score, len(result.issues))
    return result


@app.post(
    "/vpat",
    tags=["core"],
    summary="Render a downloadable Digital VPAT (Accessibility Conformance Report) from a scan result",
    response_class=HTMLResponse,
)
async def vpat(result: ScanResult) -> HTMLResponse:
    """Turn a ScanResult (obtained from /scan) into a standalone, downloadable
    HTML VPAT / ACR document. Stateless formatting only -- no scanning, so it
    is not rate-limited alongside /scan.
    """
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
async def issues_csv(result: ScanResult) -> Response:
    """Turn a ScanResult (from /scan) into a downloadable CSV worklist -- one
    row per offending element. Stateless formatting only; no scanning."""
    csv_text = issues_to_csv(result)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="accessibility-issues.csv"'},
    )


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
