export default function ScoreGauge({ score }) {
  return (
    <div
      className="score-gauge"
      role="img"
      aria-label={`${score}% of tested WCAG success criteria supported`}
    >
      <span className="score-gauge-value">{score}%</span>
      <span className="score-gauge-label">criteria supported</span>
      <div className="score-gauge-bar">
        <div className="score-gauge-fill" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
    </div>
  );
}
