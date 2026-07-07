// Backend client. Calls are same-origin: FastAPI serves this frontend's
// static build alongside the API (see backend/app/main.py), so no base URL
// needs configuring in production. In local dev, vite.config.js proxies
// /scan and /health to the local uvicorn backend.

export async function scanUrl(targetUrl) {
  const res = await fetch("/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: targetUrl }),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error((body && body.detail) || `Scan failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return body;
}
