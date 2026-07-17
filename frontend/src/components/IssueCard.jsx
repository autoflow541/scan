export default function IssueCard({ issue }) {
  return (
    <div className="issue-card">
      <div className="issue-card-head">
        <span className="issue-card-help">{issue.help}</span>
        {issue.wcag_criterion && (
          <span className="issue-card-criterion">{issue.wcag_criterion}</span>
        )}
      </div>
      <p className="issue-card-desc">{issue.description}</p>
      <p className="issue-card-footer">
        Affects {issue.node_count} element{issue.node_count === 1 ? "" : "s"} &middot;{" "}
        <a href={issue.help_url} target="_blank" rel="noopener noreferrer">
          How to fix this
        </a>
      </p>
      {issue.nodes.length > 0 && (
        <details>
          <summary>Show affected elements ({issue.nodes.length})</summary>
          {issue.nodes.map((node, i) => (
            <div className="issue-node" key={i}>
              {node.mobile_only && <span className="mobile-only-badge">Mobile only</span>}
              <code>{node.html}</code>
              {node.failure_summary && (
                <p style={{ marginTop: "0.4rem", color: "var(--text-3)" }}>{node.failure_summary}</p>
              )}
            </div>
          ))}
        </details>
      )}
    </div>
  );
}
