const STATUS_LABELS = {
  supports: "Supports",
  does_not_support: "Does Not Support",
  needs_review: "Needs Review",
  not_applicable: "Not Applicable",
};

// Always visible (unlike the collapsed Digital VPAT below) -- the whole
// point is to tell the user, up front, how much of WCAG 2.2 A/AA this
// specific scan actually evaluated, and name the gaps rather than bury them.
function CoverageSummary({ vpatRows }) {
  if (!vpatRows || vpatRows.length === 0) return null;
  const total = vpatRows.length;
  const gaps = vpatRows.filter((r) => r.conformance === "Not Evaluated");
  const evaluated = total - gaps.length;

  return (
    <div className="coverage-summary">
      <p className="coverage-stat">
        This scan automatically evaluated <strong>{evaluated} of {total}</strong> WCAG 2.2 Level A/AA success criteria.
      </p>
      {gaps.length > 0 && (
        <details className="coverage-gaps">
          <summary>{gaps.length} {gaps.length === 1 ? "criterion needs" : "criteria need"} manual review -- not automatically checked</summary>
          <ul className="coverage-gaps-list">
            {gaps.map((g) => (
              <li key={g.num}>
                <span className="coverage-gap-num">{g.num}</span> {g.title}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function ConformanceTable({ rows, vpatRows }) {
  if (!rows || rows.length === 0) return null;

  return (
    <div className="conformance">
      <h2 className="conformance-title">WCAG Conformance Summary</h2>
      <p className="conformance-sub">
        Every success criterion this scan actually tested, and whether the page supports it.
      </p>
      <CoverageSummary vpatRows={vpatRows} />
      <div className="table-scroll">
        <table className="conformance-table">
          <thead>
            <tr>
              <th scope="col">Success Criterion</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.criterion}>
                <td>{row.criterion}</td>
                <td>
                  <span className={`conformance-status conformance-status--${row.status}`}>
                    {STATUS_LABELS[row.status] || row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
