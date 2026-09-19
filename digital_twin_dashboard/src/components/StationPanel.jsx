import StatusPill from './StatusPill'
import AnomalyBanner from './AnomalyBanner'
import HealthScore from './HealthScore'
import './StationPanel.css'

function autonomyTone(days) {
  if (days == null) return 'neutral'
  if (days < 15) return 'critical'
  if (days < 30) return 'warn'
  return 'good'
}

export default function StationPanel({ station, telemetry, anomalies, health, onOpen }) {
  const hasData = Boolean(telemetry)

  return (
    <button className="station-panel" onClick={() => onOpen(station)}>
      <div className="station-panel__top">
        <div>
          <div className="station-panel__name">{station.display_name}</div>
          <div className="station-panel__location">{station.location}</div>
        </div>
        {hasData && (
          <StatusPill
            commsStatus={telemetry.comms_status}
            ts={telemetry.ts}
            receivedAt={telemetry.received_at}
          />
        )}
      </div>

      <HealthScore health={health} compact />

      {!hasData ? (
        <div className="station-panel__waiting">Waiting for data…</div>
      ) : (
        <>
          <div className="station-panel__temp">
            {telemetry.ambient_temp_c?.toFixed(1)}
            <span className="station-panel__temp-unit">°C</span>
          </div>

          <div className="station-panel__grid">
            <div>
              <div className="station-panel__grid-label">Power</div>
              <div className="station-panel__grid-value num">{telemetry.power_draw_kw?.toFixed(0)} kW</div>
            </div>
            <div>
              <div className="station-panel__grid-label">Fuel</div>
              <div className="station-panel__grid-value num">{telemetry.fuel_tank_pct?.toFixed(0)}%</div>
            </div>
            <div>
              <div className="station-panel__grid-label">Battery</div>
              <div className="station-panel__grid-value num">{telemetry.battery_soc_pct?.toFixed(0)}%</div>
            </div>
            <div>
              <div className="station-panel__grid-label">Autonomy</div>
              <div className={`station-panel__grid-value num tone-${autonomyTone(telemetry.days_of_autonomy)}`}>
                {telemetry.days_of_autonomy?.toFixed(0)}d
              </div>
            </div>
          </div>

          {telemetry.active_anomalies && telemetry.active_anomalies !== 'none' && (
            <div className="station-panel__anomaly">⚠ {telemetry.active_anomalies.split(',').join(', ')} (ground truth)</div>
          )}

          <AnomalyBanner data={anomalies} compact />
        </>
      )}

      <div className="station-panel__cta">View station →</div>
    </button>
  )
}
