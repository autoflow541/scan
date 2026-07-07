# Free WCAG accessibility scanner -- single service.
# FastAPI (Playwright + axe-core) serves both the API and the built React
# frontend from one container, so this is the only thing that needs deploying
# (e.g. as one Render/Fly/Railway web service) -- no separate static host, no
# reverse proxy to wire up.
#
# Build (from the repo root, so backend/ and frontend/ are both in scope):
#   docker build -f docker/Dockerfile -t scan-engine .
# Run:
#   docker run --rm -p 8001:8001 scan-engine
#
# The runtime base image ships Chromium + all OS deps pre-installed and
# version-matched to the `playwright` pip package -- avoids hand-rolling
# Chromium's dependency list. IMPORTANT: the image tag's Playwright version
# MUST match the `playwright` pin in backend/requirements.txt exactly, or the
# bundled browser binaries won't match what the Python package expects to drive.

# ---- stage: fetch a pinned axe-core build via npm (provenance-checked,
#             rather than curl-ing an unpinned CDN URL) ----
FROM node:20-slim AS axe-fetch
RUN npm install axe-core@4.10.2 --no-save --prefix /tmp/axe

# ---- stage: build the frontend ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime ----
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --from=axe-fetch /tmp/axe/node_modules/axe-core/axe.min.js /app/app/vendor/axe.min.js
COPY --from=frontend-build /app/frontend/dist /app/static
COPY backend/app /app/app

# Run as a non-root user, matching the remediation engine's convention. The
# playwright/python image also ships a built-in `pwuser` account; fall back to
# that (or add --no-sandbox to the Chromium launch args in scanner.py) if
# sandboxing under this uid causes launch failures.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
