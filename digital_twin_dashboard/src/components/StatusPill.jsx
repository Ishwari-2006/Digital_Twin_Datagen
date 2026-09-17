import './StatusPill.css'

/**
 * Two things worth showing at a glance:
 *  - comms_status from the station itself (online / degraded / blackout)
 *  - whether this particular record arrived live or was caught up after a
 *    blackout (received_at meaningfully later than ts -- Section 3.3's
 *    store-and-forward behavior, made visible)
 */
export default function StatusPill({ commsStatus, ts, receivedAt }) {
  const lagMinutes = ts && receivedAt
    ? Math.round((new Date(receivedAt) - new Date(ts)) / 60000)
    : 0
  const wasBackfilled = lagMinutes >= 2

  let tone = 'ok'
  let label = 'Online'
  if (commsStatus === 'blackout') {
    tone = 'critical'
    label = 'Comms blackout'
  } else if (commsStatus === 'degraded') {
    tone = 'warn'
    label = 'Degraded link'
  } else if (wasBackfilled) {
    tone = 'warn'
    label = `Caught up · was ${lagMinutes}m behind`
  }

  return (
    <span className={`status-pill status-pill--${tone}`}>
      <span className="status-pill__dot" />
      {label}
    </span>
  )
}
