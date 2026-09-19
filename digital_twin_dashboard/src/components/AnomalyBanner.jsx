import { useState } from 'react'
import { postCommand } from '../api'
import './AnomalyBanner.css'

/**
 * `data` is one entry from GET /anomalies/latest -- the detector's actual
 * live output, not the generator's ground-truth active_anomalies field.
 * `compact` renders a single worst-signal line for the fleet cards; the
 * full station detail view shows every flagged signal.
 *
 * `groundTruthKinds` (Remote Management Action Layer) is the station's
 * *actual* active anomaly kinds -- StationSimulator's active_anomalies
 * field, split on ",". These are the only anomalies that can genuinely be
 * "acknowledged" (StationSimulator.apply_command's acknowledge_anomaly
 * calls clear_anomaly(kind) on exactly these kind strings). The detector's
 * `data.anomalies` signals above are statistical flags recomputed every
 * poll, not something a single command can clear, so they get no button.
 * Both `groundTruthKinds` and `stationId` are optional -- StationPanel's
 * compact fleet-card usage doesn't pass them, so nothing changes there.
 */
export default function AnomalyBanner({ data, compact = false, stationId, groundTruthKinds = [] }) {
  const [ackBusy, setAckBusy] = useState(null)
  const [ackError, setAckError] = useState(null)

  const acknowledge = async (kind) => {
    setAckBusy(kind)
    setAckError(null)
    try {
      await postCommand(stationId, { command: 'acknowledge_anomaly', anomaly_id: kind })
    } catch (e) {
      setAckError(e.message)
    } finally {
      setAckBusy(null)
    }
  }

  const ackSection = !compact && stationId && groundTruthKinds.length > 0 && (
    <div className="anomaly-banner anomaly-banner--full anomaly-banner__ack">
      <div className="anomaly-banner__title">Active (ground truth) — acknowledge to clear</div>
      {groundTruthKinds.map((kind) => (
        <div key={kind} className="anomaly-banner__row anomaly-banner__row--warn">
          <span className="anomaly-banner__dot" />
          <span className="anomaly-banner__label">{kind.replaceAll('_', ' ')}</span>
          <button
            className="anomaly-banner__ack-button"
            disabled={ackBusy === kind}
            onClick={() => acknowledge(kind)}
          >
            {ackBusy === kind ? 'Acknowledging…' : 'Acknowledge'}
          </button>
        </div>
      ))}
      {ackError && <div className="anomaly-banner__ack-error">{ackError}</div>}
    </div>
  )

  if (!data) return ackSection || null

  if (!data.ready) {
    return (
      <>
        <div className="anomaly-banner anomaly-banner--pending">
          Building detection baseline… ({data.history_points} readings so far)
        </div>
        {ackSection}
      </>
    )
  }

  if (!data.anomalies.length) return ackSection || null

  if (compact) {
    const worst = data.anomalies[0]
    return (
      <div className={`anomaly-banner anomaly-banner--${worst.severity}`}>
        ⚠ Detected: {worst.label}{data.anomalies.length > 1 ? ` +${data.anomalies.length - 1} more` : ''}
      </div>
    )
  }

  return (
    <>
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
      {ackSection}
    </>
  )
}