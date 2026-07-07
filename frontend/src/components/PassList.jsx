export default function PassList({ passes }) {
  if (!passes || passes.length === 0) return null;

  return (
    <details className="pass-list">
      <summary>Passed checks ({passes.length})</summary>
      <div className="pass-list-items">
        {passes.map((p) => (
          <div className="pass-card" key={p.id}>
            <div className="pass-card-help">{p.help}</div>
            <div className="pass-card-meta">
              {p.wcag_criterion ? `${p.wcag_criterion} · ` : ""}
              Checked {p.node_count} element{p.node_count === 1 ? "" : "s"}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
