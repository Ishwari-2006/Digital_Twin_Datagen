import './AnomalyBanner.css'

/**
 * `data` is one entry from GET /anomalies/latest -- the detector's actual
 * live output, not the generator's ground-truth active_anomalies field.
 * `compact` renders a single worst-signal line for the fleet cards; the
 * full station detail view shows every flagged signal.
 */
export default function AnomalyBanner({ data, compact = false }) {
  if (!data) return null

  if (!data.ready) {
    return (
      <div className="anomaly-banner anomaly-banner--pending">
        Building detection baseline… ({data.history_points} readings so far)
      </div>
    )
  }

  if (!data.anomalies.length) return null

  if (compact) {
    const worst = data.anomalies[0]
    return (
      <div className={`anomaly-banner anomaly-banner--${worst.severity}`}>
        ⚠ Detected: {worst.label}{data.anomalies.length > 1 ? ` +${data.anomalies.length - 1} more` : ''}
      </div>
    )
  }

  return (
    <div className="anomaly-banner anomaly-banner--full">
      <div className="anomaly-banner__title">Detected anomalies</div>
      {data.anomalies.map((a) => (
        <div key={a.signal} className={`anomaly-banner__row anomaly-banner__row--${a.severity}`}>
          <span className="anomaly-banner__dot" />
          <span className="anomaly-banner__label">{a.label}</span>
          <span className="anomaly-banner__detail num">{a.value} · z={a.z_score}</span>
        </div>
      ))}
    </div>
  )
}