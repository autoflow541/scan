# Free WCAG Accessibility Scan

Paste a URL. Get an instant scan of that one page: issues ranked by severity, mapped to the exact WCAG success criterion.

**Live:** [scan.auto-flow.co](https://scan.auto-flow.co)

---

## What it does

- Renders the page with headless Chromium (Playwright) so JS-rendered/SPA pages get scanned correctly, not just static HTML
- Runs [axe-core](https://github.com/dequelabs/axe-core) against the DOM
- Groups violations by severity (critical/serious/moderate/minor) and maps each to its WCAG 2.x criterion
- Gives a simple 0-100 relative score -- not a conformance certification
- Ends with a CTA to request a full manual audit (this is a lead-gen tool, not a replacement for one)

Single page only in v1 -- no crawling, no accounts, no saved history.

## Safety

Since this fetches and renders arbitrary public URLs, it validates every request against SSRF:
rejects private/loopback/link-local/reserved IPs (including `169.254.169.254` metadata endpoints and CGNAT),
re-checks DNS at resolution time (not just string matching, to catch DNS-rebinding), and re-validates
the host after following redirects. See `backend/app/url_safety.py`.

Also rate-limited per IP (in-memory token bucket) and capped on total concurrent scans, since each scan
spins up a real browser process. See `backend/app/rate_limit.py`.

## Stack

- **Backend:** FastAPI + Playwright + axe-core (Docker)
- **Frontend:** React + Vite -- built and served by the same FastAPI process (see `backend/app/main.py`'s
  static file mount), so this is one deployable service, not two.

## Run it

Full stack in one container (this is what actually ships):

```bash
docker build -f docker/Dockerfile -t scan-engine .
docker run --rm -p 8001:8001 scan-engine
# -> http://localhost:8001 serves both the UI and the API
```

For frontend-only iteration with hot reload, run the backend separately and let Vite proxy to it
(see `frontend/vite.config.js`'s `server.proxy`):

```bash
cd backend && python3 -m uvicorn app.main:app --port 8001   # terminal 1
cd frontend && npm install && npm run dev                    # terminal 2 -> http://localhost:5174
```

### Backend tests

```bash
cd backend
python3 -m pytest tests/
```

(Requires `pytest`, `pydantic`, and `fastapi` installed -- no native Python interpreter is required
inside the Docker image itself since it's a browser-driving service, but a local interpreter is needed
to run these unit tests outside the container.)

## API

| Endpoint | Description |
|---|---|
| `POST /scan` | `{ "url": "https://..." }` -> scan report JSON |
| `GET /health` | Health check |

Full docs: [scan.auto-flow.co/docs](https://scan.auto-flow.co/docs)

## Deployment

Runs on the same DreamCompute VM as [pdf.auto-flow.co](https://pdf.auto-flow.co) (the `remediation/`
project), sharing one Caddy instance. See `deploy/setup-vm.sh` -- it never overwrites the shared
`/etc/caddy/Caddyfile` wholesale; it only ever writes `/etc/caddy/sites/scan.conf`, relying on an
`import /etc/caddy/sites/*.conf` line in the main Caddyfile (a one-time manual migration if this is
the first product moved to that layout -- the script checks for it and explains the steps if missing).

```bash
scp -r ./scan user@VM_IP:~/scan
ssh user@VM_IP
REPO_DIR=~/scan bash ~/scan/deploy/setup-vm.sh
```

The single container (frontend + API, one image, see `docker/Dockerfile`) runs on `127.0.0.1:8001`;
Caddy reverse-proxies `scan.auto-flow.co` to it and handles TLS via Let's Encrypt automatically.
To update after a code change: `docker build`, then `docker stop scan-engine && docker rm scan-engine`,
then re-run `deploy/run-engine.sh`.

## License

Code: see `LICENSE`. Bundled tools retain their own licenses (axe-core: MPL-2.0; Playwright: Apache-2.0).
