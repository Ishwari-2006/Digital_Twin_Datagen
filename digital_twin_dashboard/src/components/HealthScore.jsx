import './HealthScore.css'

const LABELS = {
  normal: 'Normal',
  warning: 'Warning',
  critical: 'Critical',
  comms_blackout: 'Comms blackout',
  backfilled: 'Catching up',
}

export default function HealthScore({ health, compact = false }) {
  if (!health) return null
  const score = Math.round(health.score)
  const tone = score >= 80 ? 'good' : score >= 50 ? 'warn' : 'critical'

  return (
    <div className={`health-score health-score--${tone} ${compact ? 'health-score--compact' : ''}`}>
      <div className="health-score__label">Station health</div>
      <div className="health-score__main">
        <strong className="health-score__value num">{score}</strong><span>/100</span>
      </div>
      <div className="health-score__state">{LABELS[health.state] || health.state}</div>
    </div>
  )
}
