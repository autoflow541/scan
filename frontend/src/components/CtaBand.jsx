import { useState } from "react";
import { submitLead } from "../api.js";
import { trackEvent } from "../analytics.js";

// Copy is tailored to the actual score so the pitch reads as earned, not
// boilerplate -- always honest about what automated testing can and can't
// tell you (matches the VPAT's own framing), never inflates the finding.
function pitchFor(score) {
  if (score === null || score === undefined) {
    return {
      heading: "Want the full picture?",
      body: "This automated scan catches what a script can see. Our audits add keyboard-only navigation, screen reader passes, and the WCAG 2.2 criteria automated tools miss -- then we do the fixes.",
    };
  }
  if (score < 60) {
    return {
      heading: "This page has real, fixable gaps.",
      body: `Automated checks alone put this page at ${score}% of testable WCAG criteria -- before even counting what a script can't check. Gaps like these carry real ADA and Section 508 exposure. We diagnose the rest and do the fixes.`,
    };
  }
  if (score < 90) {
    return {
      heading: "Good start -- not the whole picture yet.",
      body: `Automated checks put this page at ${score}%, but "no automated errors" isn't the same as compliant: keyboard flows, screen reader behavior, and several WCAG 2.2 criteria can't be tested by a script at all. Our audits cover what this scan can't.`,
    };
  }
  return {
    heading: "Strong automated score -- worth verifying it holds up.",
    body: `This page supports ${score}% of what a scanner can check, which is a good sign. The criteria that cause the most real-world friction -- keyboard-only use, screen readers, focus behavior -- can't be automated at all. A manual audit confirms it's actually solid.`,
  };
}

// Worst-first, so a human following up sees the highest-impact findings --
// the ones most worth leading a sales conversation with -- not whatever
// happened to scan first.
const IMPACT_ORDER = ["critical", "serious", "moderate", "minor"];

function topIssuesFor(issues) {
  if (!Array.isArray(issues)) return [];
  return [...issues]
    .sort((a, b) => IMPACT_ORDER.indexOf(a.impact) - IMPACT_ORDER.indexOf(b.impact))
    .slice(0, 5)
    .map((i) => `${i.impact}: ${i.help}`);
}

export default function CtaBand({ score, scannedUrl, issues }) {
  const { heading, body } = pitchFor(score);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle"); // idle | submitting | success | error
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMessage("");
    try {
      const topIssues = topIssuesFor(issues);
      await submitLead({ email, scannedUrl, score: score ?? null, topIssues });
      setStatus("success");
      trackEvent("lead_submitted", { url: scannedUrl, score: score ?? null });
    } catch (err) {
      setErrorMessage(err.message || "Something went wrong. Please try again.");
      setStatus("error");
    }
  }

  return (
    <div className="cta-band">
      <h2>{heading}</h2>
      <p>{body}</p>
      <a className="btn-primary" href="https://auto-flow.co" target="_blank" rel="noopener noreferrer">
        Request a full audit
      </a>

      {status === "success" ? (
        <p className="cta-lead-success" role="status">
          Thanks -- we'll follow up at {email}.
        </p>
      ) : (
        <form className="cta-lead-form" onSubmit={handleSubmit}>
          <label htmlFor="cta-lead-email" className="cta-lead-label">
            Or leave your email and we'll reach out about a full audit
          </label>
          <div className="cta-lead-row">
            <input
              id="cta-lead-email"
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={status === "submitting"}
              aria-invalid={status === "error"}
              aria-describedby={status === "error" ? "cta-lead-error" : undefined}
            />
            <button type="submit" className="btn-secondary" disabled={status === "submitting"}>
              {status === "submitting" ? "Sending..." : "Contact me"}
            </button>
          </div>
          {status === "error" && (
            <p id="cta-lead-error" className="cta-lead-error" role="alert">{errorMessage}</p>
          )}
        </form>
      )}
    </div>
  );
}
