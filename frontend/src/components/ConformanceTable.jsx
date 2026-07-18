const STATUS_LABELS = {
  supports: "Supports",
  does_not_support: "Does Not Support",
  needs_review: "Needs Review",
  not_applicable: "Not Applicable",
};

export default function ConformanceTable({ rows }) {
  if (!rows || rows.length === 0) return null;

  return (
    <div className="conformance">
      <h2 className="conformance-title">WCAG Conformance Summary</h2>
      <p className="conformance-sub">
        Every success criterion this scan actually tested, and whether the page supports it.
      </p>
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
  );
}
