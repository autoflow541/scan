import { useState } from "react";

// Issues that have at least one locatable element, numbered in list order so a
// marker on the snapshot maps to a row in the key below it.
function locatedIssues(issues) {
  const out = [];
  for (const issue of issues) {
    const boxes = issue.nodes.filter((n) => n.bbox).map((n) => n.bbox);
    if (boxes.length > 0) {
      out.push({ criterion: issue.wcag_criterion, impact: issue.impact, help: issue.help, boxes });
    }
  }
  return out.map((it, i) => ({ ...it, number: i + 1 }));
}

export default function PageScreenshot({ screenshot, issues }) {
  const [size, setSize] = useState(null); // { w, h } natural pixels of the screenshot

  const located = locatedIssues(issues);

  // A screenshot with nothing to point at isn't useful; the issue list already
  // reports a clean scan.
  if (!screenshot || located.length === 0) return null;

  // Boxes are in full-page document coordinates. The screenshot may only cover
  // the top of a very tall page, so a marker is only drawn if it falls inside
  // the captured image -- otherwise it would point at empty space below.
  const inBounds = (b) => !size || (b.y + b.height <= size.h + 2 && b.x <= size.w);

  const markers = [];
  let offscreen = 0;
  for (const it of located) {
    const visible = it.boxes.filter(inBounds);
    if (visible.length === 0) {
      offscreen += 1;
      continue;
    }
    visible.forEach((b, j) => markers.push({ ...it, bbox: b, key: `${it.number}-${j}` }));
  }

  return (
    <div className="page-screenshot">
      <h2 className="page-screenshot-title">Where the issues are</h2>
      <p className="page-screenshot-sub">
        The page as scanned. Each numbered marker points to an element that failed a check; the key below says what.
      </p>
      <div className="page-screenshot-frame">
        <img
          src={screenshot}
          alt="Screenshot of the scanned page with numbered markers on the elements that have accessibility issues"
          onLoad={(e) => setSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />
        {size &&
          markers.map((m) => (
            <div
              key={m.key}
              aria-hidden="true"
              className={`page-screenshot-box page-screenshot-box--${m.impact}`}
              style={{
                left: `${(m.bbox.x / size.w) * 100}%`,
                top: `${(m.bbox.y / size.h) * 100}%`,
                width: `${(m.bbox.width / size.w) * 100}%`,
                height: `${(m.bbox.height / size.h) * 100}%`,
              }}
            >
              <span className={`page-screenshot-pin page-screenshot-pin--${m.impact}`}>{m.number}</span>
            </div>
          ))}
      </div>

      <ol className="page-screenshot-key">
        {located.map((it) => {
          const hidden = size && it.boxes.every((b) => !inBounds(b));
          return (
            <li key={it.number} className="page-screenshot-key-item">
              <span className={`page-screenshot-pin page-screenshot-pin--${it.impact} page-screenshot-pin--static`}>
                {it.number}
              </span>
              <span className="page-screenshot-key-text">
                {it.criterion && <strong>{it.criterion}</strong>} {it.help}
                {hidden && <span className="page-screenshot-key-off"> (below the captured area)</span>}
              </span>
            </li>
          );
        })}
      </ol>

      {offscreen > 0 && (
        <p className="page-screenshot-note">
          {offscreen} issue{offscreen > 1 ? "s are" : " is"} located below the part of the page captured here — they're
          numbered in the key and detailed in the full list below.
        </p>
      )}
    </div>
  );
}
