const LEVEL_CLASS = {
  "Supports": "supports",
  "Partially Supports": "partial",
  "Does Not Support": "does_not_support",
  "Not Applicable": "not_applicable",
  "Not Evaluated": "not_evaluated",
};

function LevelTable({ caption, rows }) {
  if (rows.length === 0) return null;
  return (
    <div className="table-scroll">
      <table className="conformance-table vpat-table">
        <caption className="vpat-caption">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Criteria</th>
            <th scope="col">Conformance Level</th>
            <th scope="col">Remarks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.num}>
              <th scope="row" className="vpat-sc">
                {row.num} {row.title}
              </th>
              <td>
                <span className={`conformance-status conformance-status--${LEVEL_CLASS[row.conformance] || "not_evaluated"}`}>
                  {row.conformance}
                </span>
              </td>
              <td className="vpat-remarks">{row.remarks}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function VpatTable({ rows, summary }) {
  if (!rows || rows.length === 0) return null;

  const levelA = rows.filter((r) => r.level === "A");
  const levelAA = rows.filter((r) => r.level === "AA");
  const summaryLine = summary
    ? Object.entries(summary)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => `${v} ${k}`)
        .join(" · ")
    : "";

  return (
    <details className="vpat">
      <summary>
        <span className="vpat-title">Digital VPAT — full WCAG 2.2 A/AA report</span>
        {summaryLine && <span className="vpat-summary">{summaryLine}</span>}
      </summary>
      <p className="vpat-note">
        Generated from this automated scan. Rows marked <strong>Not Evaluated</strong> are outside the reach of
        automated testing and require manual review — they are not conformance claims. Use the VPAT (HTML) export
        for a shareable document.
      </p>
      <LevelTable caption="Table 1 — Level A" rows={levelA} />
      <LevelTable caption="Table 2 — Level AA" rows={levelAA} />
    </details>
  );
}
