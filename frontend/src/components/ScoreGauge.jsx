export default function ScoreGauge({ score }) {
  return (
    <div className="score-gauge" role="img" aria-label={`Accessibility score ${score} out of 100`}>
      <span className="score-gauge-value">{score}</span>
      <span className="score-gauge-label">/ 100</span>
      <div className="score-gauge-bar">
        <div className="score-gauge-fill" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </div>
    </div>
  );
}
