import { useState } from "react";
import { scanUrl } from "./api.js";
import UrlForm from "./components/UrlForm.jsx";
import LoadingState from "./components/LoadingState.jsx";
import ScoreGauge from "./components/ScoreGauge.jsx";
import IssueList from "./components/IssueList.jsx";
import PageScreenshot from "./components/PageScreenshot.jsx";
import ConformanceTable from "./components/ConformanceTable.jsx";
import VpatTable from "./components/VpatTable.jsx";
import ExportBar from "./components/ExportBar.jsx";
import PassList from "./components/PassList.jsx";
import CtaBand from "./components/CtaBand.jsx";
import ErrorState from "./components/ErrorState.jsx";

const COUNT_ORDER = ["critical", "serious", "moderate", "minor"];

export default function App() {
  const [screen, setScreen] = useState("idle"); // idle | scanning | results | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(url) {
    setScreen("scanning");
    setError(null);
    try {
      const data = await scanUrl(url);
      setResult(data);
      setScreen("results");
    } catch (e) {
      setError(e);
      setScreen("error");
    }
  }

  return (
    <>
      <header className="app-header">
        <p className="app-byline">
          <a href="https://auto-flow.co" target="_blank" rel="noopener noreferrer">Auto-Flow Automations Inc.</a>
        </p>
        <h1 className="app-title">Free WCAG Accessibility Scan</h1>
        <p className="app-subtitle">Paste a URL. We'll scan that one page and show you what to fix.</p>
      </header>

      <main id="main-content" className="app-main">
        <UrlForm onSubmit={handleSubmit} disabled={screen === "scanning"} />

        {screen === "scanning" && <LoadingState />}

        {screen === "error" && <ErrorState error={error} />}

        {screen === "results" && result && (
          <>
            <div className="results-summary">
              <ScoreGauge score={result.score} />
              <div className="results-meta">
                <p className="page-title">{result.page_title || "Untitled page"}</p>
                <p className="page-url">{result.final_url}</p>
                <div className="results-counts">
                  {COUNT_ORDER.filter((k) => result.counts?.[k] > 0).map((k) => (
                    <span className={`count-pill count-pill--${k}`} key={k}>
                      {result.counts[k]} {k}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <ExportBar result={result} />
            <PageScreenshot screenshot={result.screenshot} issues={result.issues} />
            <ConformanceTable rows={result.conformance} vpatRows={result.vpat} />
            <VpatTable rows={result.vpat} summary={result.vpat_summary} />
            <IssueList issues={result.issues} incompleteCount={result.incomplete_count} />
            <PassList passes={result.passes} />
          </>
        )}

        <CtaBand score={result?.score} scannedUrl={result?.final_url} />
      </main>

      <footer className="app-footer">
        <p>
          A free tool from <a href="https://auto-flow.co" target="_blank" rel="noopener noreferrer">Auto-Flow Automations Inc.</a>
          &middot; Not a substitute for a full manual audit.
        </p>
      </footer>
    </>
  );
}
