import { useState } from "react";
import { downloadVpat, downloadIssuesCsv, downloadJson } from "../api.js";
import { trackEvent } from "../analytics.js";

export default function ExportBar({ result }) {
  const [busy, setBusy] = useState(null); // "vpat" | "csv" | "json" | null
  const [error, setError] = useState(null);

  async function run(kind, fn) {
    setError(null);
    setBusy(kind);
    try {
      await fn(result);
      trackEvent("report_exported", { format: kind, url: result?.final_url, score: result?.score ?? null });
    } catch (e) {
      setError(e.message || "Export failed. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="export-bar">
      <span className="export-label">Export report:</span>
      <button
        type="button"
        className="btn-secondary"
        onClick={() => run("vpat", downloadVpat)}
        disabled={busy !== null}
      >
        {busy === "vpat" ? "Preparing…" : "VPAT (HTML)"}
      </button>
      <button
        type="button"
        className="btn-secondary"
        onClick={() => run("csv", downloadIssuesCsv)}
        disabled={busy !== null}
      >
        {busy === "csv" ? "Preparing…" : "Issues (CSV)"}
      </button>
      <button
        type="button"
        className="btn-secondary"
        onClick={() => run("json", async (r) => downloadJson(r))}
        disabled={busy !== null}
      >
        Raw data (JSON)
      </button>
      {error && (
        <span className="export-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
