export default function RecCard({ rec }) {
  return (
    <div className="rec-card">
      <h4>{rec.action}</h4>
      <div className="row"><b>Why:</b> {rec.why}</div>
      <div className="row"><b>Improves:</b> {rec.impacted_metrics.join(', ')} — {rec.quantified_estimate}</div>
      <div className="chips">
        <span className="chip horizon">{rec.time_horizon} term</span>
        <span className="chip conf">{rec.confidence} confidence</span>
      </div>
      <div className="src-line">Sources: {rec.sources.join('; ')}</div>
    </div>
  );
}
