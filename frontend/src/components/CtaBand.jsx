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

export default function CtaBand({ score }) {
  const { heading, body } = pitchFor(score);
  return (
    <div className="cta-band">
      <h2>{heading}</h2>
      <p>{body}</p>
      <a className="btn-primary" href="https://auto-flow.co" target="_blank" rel="noopener noreferrer">
        Request a full audit
      </a>
    </div>
  );
}
