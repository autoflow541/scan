import IssueCard from "./IssueCard.jsx";

const IMPACT_ORDER = ["critical", "serious", "moderate", "minor"];
const IMPACT_LABELS = {
  critical: "Critical",
  serious: "Serious",
  moderate: "Moderate",
  minor: "Minor",
};

export default function IssueList({ issues, incompleteCount }) {
  if (issues.length === 0) {
    return (
      <div className="issue-group">
        <p>No automated WCAG violations found on this page. Nice work!</p>
        {incompleteCount > 0 && (
          <p className="incomplete-note">
            {incompleteCount} item{incompleteCount === 1 ? "" : "s"} need manual review to fully confirm.
          </p>
        )}
      </div>
    );
  }

  const grouped = IMPACT_ORDER.map((impact) => ({
    impact,
    items: issues.filter((issue) => issue.impact === impact),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="results">
      {grouped.map(({ impact, items }) => (
        <div className="issue-group" key={impact}>
          <h2 className="issue-group-title">
            {IMPACT_LABELS[impact]} ({items.length})
          </h2>
          {items.map((issue) => (
            <IssueCard issue={issue} key={issue.id} />
          ))}
        </div>
      ))}
      {incompleteCount > 0 && (
        <p className="incomplete-note">
          {incompleteCount} additional item{incompleteCount === 1 ? "" : "s"} need manual review.
        </p>
      )}
    </div>
  );
}
