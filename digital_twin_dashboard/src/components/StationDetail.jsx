import { useEffect, useState, useCallback } from 'react'
import { getLatest, getHistory, getAnomalies } from '../api'
import StatusPill from './StatusPill'
import DomainSection from './DomainSection'
import AnomalyBanner from './AnomalyBanner'
import './StationDetail.css'

const DOMAINS = ['Environmental', 'Energy', 'Infrastructure', 'Logistics']

function toneFor(value, warnAt, criticalAt, invert = false) {
  if (value == null) return 'neutral'
  const bad = invert ? value > warnAt : value < warnAt
  const worse = invert ? value > criticalAt : value < criticalAt
  if (worse) return 'critical'
  if (bad) return 'warn'
  return 'good'
}

export default function StationDetail({ station, onBack }) {
  const [latest, setLatest] = useState(null)
  const [history, setHistory] = useState([])
  const [anomalies, setAnomalies] = useState(null)
  const [domain, setDomain] = useState('Environmental')
  const [error, setError] = useState(null)

  const refreshLatest = useCallback(() => {
    getLatest(station.station_id).then(setLatest).catch((e) => setError(e.message))
  }, [station.station_id])

  const refreshHistory = useCallback(() => {
    getHistory(station.station_id, 6).then(setHistory).catch((e) => setError(e.message))
  }, [station.station_id])

  const refreshAnomalies = useCallback(() => {
    getAnomalies(station.station_id).then(setAnomalies).catch(() => {})
  }, [station.station_id])

  useEffect(() => {
    refreshLatest()
    refreshHistory()
    refreshAnomalies()
    const t1 = setInterval(refreshLatest, 5000)
    const t2 = setInterval(refreshHistory, 30000)
    const t3 = setInterval(refreshAnomalies, 5000)
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3) }
  }, [refreshLatest, refreshHistory, refreshAnomalies])

  if (error && !latest) {
    return (
      <div className="station-detail">
        <button className="back-link" onClick={onBack}>← Fleet</button>
        <p className="detail-error">Couldn't reach the API: {error}</p>
      </div>
    )
  }

  if (!latest) {
    return (
      <div className="station-detail">
        <button className="back-link" onClick={onBack}>← Fleet</button>
        <p className="detail-loading">Loading {station.display_name}…</p>
      </div>
    )
  }

  const content = {
    Environmental: (
      <DomainSection
        tiles={[
          { label: 'Ambient temperature', value: latest.ambient_temp_c?.toFixed(1), unit: '°C' },
          { label: 'Wind speed', value: latest.wind_speed_ms?.toFixed(1), unit: 'm/s' },
          {
            label: 'Weather', value: latest.weather_anomaly_flag ? 'Storm' : 'Clear',
            tone: latest.weather_anomaly_flag ? 'warn' : 'good',
          },
        ]}
        charts={[
          { title: 'Ambient temperature (6h)', unit: '°C', data: history, series: [{ key: 'ambient_temp_c', name: 'Temp', color: 'ice' }] },
          { title: 'Wind speed (6h)', unit: ' m/s', data: history, series: [{ key: 'wind_speed_ms', name: 'Wind', color: 'aurora' }] },
        ]}
      />
    ),
    Energy: (
      <DomainSection
        tiles={[
          { label: 'Power draw', value: latest.power_draw_kw?.toFixed(1), unit: 'kW' },
          {
            label: 'Generator load', value: latest.generator_load_pct?.toFixed(0), unit: '%',
            tone: toneFor(latest.generator_load_pct, 85, 95, true),
          },
          {
            label: 'Battery', value: latest.battery_soc_pct?.toFixed(0), unit: '%',
            tone: toneFor(latest.battery_soc_pct, 40, 20), note: latest.battery_state,
          },
        ]}
        charts={[
          { title: 'Power draw (6h)', unit: ' kW', data: history, series: [{ key: 'power_draw_kw', name: 'Power', color: 'ice' }] },
          { title: 'Battery state of charge (6h)', unit: '%', data: history, series: [{ key: 'battery_soc_pct', name: 'Battery', color: 'aurora' }] },
        ]}
      />
    ),
    Infrastructure: (
      <DomainSection
        tiles={[
          {
            label: 'Fuel tank', value: latest.fuel_tank_pct?.toFixed(0), unit: '%',
            tone: toneFor(latest.fuel_tank_pct, 40, 20),
          },
          { label: 'HVAC', value: latest.hvac_status },
          {
            label: 'Heater', value: latest.heater_status,
            tone: latest.heater_status === 'fault' ? 'critical' : 'neutral',
          },
        ]}
        charts={[
          { title: 'Fuel tank level (6h)', unit: '%', data: history, series: [{ key: 'fuel_tank_pct', name: 'Fuel', color: 'ice' }] },
        ]}
      />
    ),
    Logistics: (
      <DomainSection
        tiles={[
          {
            label: 'Days of autonomy', value: latest.days_of_autonomy?.toFixed(0), unit: 'd',
            tone: toneFor(latest.days_of_autonomy, 30, 15),
          },
          { label: 'Fuel burn rate', value: latest.fuel_burn_rate_lph?.toFixed(1), unit: 'L/h' },
          { label: 'Next resupply window', value: latest.resupply_window_days_remaining, unit: 'd' },
        ]}
        charts={[
          { title: 'Days of autonomy (6h)', unit: 'd', data: history, series: [{ key: 'days_of_autonomy', name: 'Autonomy', color: 'aurora' }] },
          { title: 'Fuel burn rate (6h)', unit: ' L/h', data: history, series: [{ key: 'fuel_burn_rate_lph', name: 'Burn rate', color: 'amber' }] },
        ]}
      />
    ),
  }

  return (
    <div className="station-detail">
      <button className="back-link" onClick={onBack}>← Fleet</button>

      <div className="station-detail__header">
        <div>
          <h1 className="station-detail__name">{station.display_name}</h1>
          <div className="station-detail__location">{station.location}</div>
        </div>
        <StatusPill commsStatus={latest.comms_status} ts={latest.ts} receivedAt={latest.received_at} />
      </div>

      {latest.active_anomalies && latest.active_anomalies !== 'none' && (
        <div className="station-detail__anomaly-banner">
          Active (ground truth): {latest.active_anomalies.split(',').join(', ')}
        </div>
      )}

      <AnomalyBanner data={anomalies} />

      {domain === 'Logistics' && latest.resupply_recommendation && (
        <div className="station-detail__recommendation">{latest.resupply_recommendation}</div>
      )}

      <div className="station-detail__tabs">
        {DOMAINS.map((d) => (
          <button
            key={d}
            className={`station-detail__tab ${domain === d ? 'is-active' : ''}`}
            onClick={() => setDomain(d)}
          >
            {d}
          </button>
        ))}
      </div>

      {content[domain]}
    </div>
  )
}