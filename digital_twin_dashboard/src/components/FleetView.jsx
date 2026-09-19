import { useEffect, useState, useCallback } from "react";
import { getStations, getLatest, getAnomalies, getHealthCurrent } from "../api";
import StationPanel from "./StationPanel";
import "./FleetView.css";

export default function FleetView({ onOpen }) {
  const [stations, setStations] = useState([]);
  const [telemetryByStation, setTelemetryByStation] = useState({});
  const [anomaliesByStation, setAnomaliesByStation] = useState({});
  const [healthByStation, setHealthByStation] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    getStations()
      .then(setStations)
      .catch((e) => setError(e.message));
  }, []);

  const refresh = useCallback(() => {
    getLatest()
      .then((rows) => {
        const map = {};
        rows.forEach((r) => {
          map[r.station_id] = r;
        });
        setTelemetryByStation(map);
        setError(null);
      })
      .catch((e) => setError(e.message));

    getAnomalies()
      .then((rows) => {
        const map = {};
        rows.forEach((r) => {
          map[r.station_id] = r;
        });
        setAnomaliesByStation(map);
      })
      .catch(() => {});

    Promise.all(["maitri", "bharati"].map((stationId) => getHealthCurrent(stationId)))
      .then((rows) => {
        const map = {};
        rows.forEach((row) => { map[row.station_id] = row; });
        setHealthByStation(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const healthRows = Object.values(healthByStation);
  const healthy = healthRows.filter((row) => row.state === 'normal').length;
  const warnings = healthRows.filter((row) => row.state === 'warning').length;
  const blackouts = healthRows.filter((row) => row.state === 'comms_blackout').length;

  if (error) {
    return (
      <div className="fleet-error">
        <p>Can't reach the API at the configured URL.</p>
        <p className="fleet-error__detail">{error}</p>
        <p className="fleet-error__hint">
          Make sure mqtt_subscriber.py, mqtt_publisher.py and the FastAPI server
          (uvicorn api:app) are all running.
        </p>
      </div>
    );
  }

  return (
    <div className="fleet-view">
      <div className="fleet-view__intro">
        <div>
          <div className="fleet-view__eyebrow">Operations / Fleet overview</div>
          <h1>Antarctic stations</h1>
          <p>Live telemetry and operational readiness across the polar network.</p>
        </div>
        <div className="fleet-view__live"><i /> <strong>Live simulation</strong><span>Telemetry refreshes every 5 seconds</span></div>
      </div>
      <div className="fleet-view__summary">
        <div><span className="fleet-view__summary-label">Fleet status</span><strong><i /> {stations.length} / 2 online</strong></div>
        <div><span className="fleet-view__summary-label">Healthy</span><strong>{String(healthy).padStart(2, '0')}</strong></div>
        <div><span className="fleet-view__summary-label">Warnings</span><strong className="summary-warn">{String(warnings).padStart(2, '0')}</strong></div>
        <div><span className="fleet-view__summary-label">Blackouts</span><strong className="summary-critical">{String(blackouts).padStart(2, '0')}</strong></div>
        <div className="fleet-view__updated">↻ Updated 5s ago</div>
      </div>
      {stations.map((s) => (
        <StationPanel
          key={s.station_id}
          station={s}
          telemetry={telemetryByStation[s.station_id]}
          anomalies={anomaliesByStation[s.station_id]}
          health={healthByStation[s.station_id]}
          onOpen={onOpen}
        />
      ))}
    </div>
  );
}
