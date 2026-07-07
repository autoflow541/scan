import { useState } from "react";

export default function PageScreenshot({ screenshot, issues }) {
  const [naturalSize, setNaturalSize] = useState(null);

  const boxes = [];
  for (const issue of issues) {
    for (const node of issue.nodes) {
      if (node.bbox) {
        boxes.push({ bbox: node.bbox, impact: issue.impact, help: issue.help });
      }
    }
  }

  // Nothing to point at -- a screenshot with no highlights on it isn't
  // useful, and the issue list already says the page came back clean.
  if (!screenshot || boxes.length === 0) return null;

  return (
    <div className="page-screenshot">
      <h2 className="page-screenshot-title">Where the issues are</h2>
      <p className="page-screenshot-sub">
        A snapshot of the page as scanned, with violations outlined by severity.
      </p>
      <div className="page-screenshot-frame">
        <img
          src={screenshot}
          alt="Screenshot of the scanned page"
          onLoad={(e) => setNaturalSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />
        {naturalSize &&
          boxes.map((b, i) => (
            <div
              key={i}
              className={`page-screenshot-box page-screenshot-box--${b.impact}`}
              title={b.help}
              style={{
                left: `${(b.bbox.x / naturalSize.w) * 100}%`,
                top: `${(b.bbox.y / naturalSize.h) * 100}%`,
                width: `${(b.bbox.width / naturalSize.w) * 100}%`,
                height: `${(b.bbox.height / naturalSize.h) * 100}%`,
              }}
            />
          ))}
      </div>
    </div>
  );
}
