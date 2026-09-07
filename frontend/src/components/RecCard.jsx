import { Clock, ShieldCheck, TrendingUp } from 'lucide-react';

export default function RecCard({ rec }) {
  return (
    <div className="rec-card">
      <h4>{rec.action}</h4>
      <div className="row"><b>Why:</b> {rec.why}</div>
      <div className="row"><b>Improves:</b> {rec.impacted_metrics.join(', ')}</div>
      <div className="metric-tags">
        {rec.impacted_metrics.map((m, i) => (
          <span className="metric-tag" key={i}>{m}</span>
        ))}
      </div>
      {rec.quantified_estimate && (
        <div className="row" style={{ marginTop: 8 }}>
          <b><TrendingUp size={13} style={{ verticalAlign: -2 }} /> Estimate:</b> {rec.quantified_estimate}
        </div>
      )}
      <div className="chips">
        <span className="chip horizon"><Clock size={11} style={{ verticalAlign: -2 }} /> {rec.time_horizon} term</span>
        <span className="chip conf"><ShieldCheck size={11} style={{ verticalAlign: -2 }} /> {rec.confidence} confidence</span>
      </div>
      {rec.sources?.length > 0 && (
        <div className="src-line">
          <span>Sources:</span>
          {rec.sources.map((s, i) => <span className="src-chip" key={i}>{s}</span>)}
        </div>
      )}
    </div>
  );
}
