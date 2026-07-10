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

// --- Exports ---------------------------------------------------------------
// The VPAT and CSV endpoints are stateless formatters: POST the scan result
// back and get a downloadable file. JSON is built client-side from the result
// we already hold.

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function postForBlob(path, result) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(result),
  });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  return res.blob();
}

export async function downloadVpat(result) {
  const blob = await postForBlob("/vpat", result);
  triggerDownload(blob, "accessibility-conformance-report.html");
}

export async function downloadIssuesCsv(result) {
  const blob = await postForBlob("/issues.csv", result);
  triggerDownload(blob, "accessibility-issues.csv");
}

export function downloadJson(result) {
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
  triggerDownload(blob, "accessibility-scan.json");
}
