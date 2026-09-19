import { useState, useEffect, useCallback } from "react";
import { postCommand, getCommands } from "../api";
import "./ControlPanel.css";

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

/**
 * Remote Management Action Layer control surface for one station.
 * `stationId` must be a key from station_config.STATIONS ("maitri" | "bharati") --
 * the same value StationDetail.jsx already carries as station.station_id.
 * `activeGenerator` is the live telemetry field of the same name (added by
 * StationSimulator.apply_command()) so the button always offers the *other*
 * generator instead of blindly re-sending "backup".
 */
export default function ControlPanel({ stationId, activeGenerator, heaterSetpointC }) {
  const [heaterValue, setHeaterValue] = useState(heaterSetpointC ?? 18.5);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  const [history, setHistory] = useState([]);
  const [seeded, setSeeded] = useState(heaterSetpointC != null);

  // Seed the input from the station's real current setpoint the first time
  // it arrives, without overwriting whatever the operator is mid-typing.
  useEffect(() => {
    if (!seeded && heaterSetpointC != null) {
      setHeaterValue(heaterSetpointC);
      setSeeded(true);
    }
  }, [seeded, heaterSetpointC]);

  const loadHistory = useCallback(() => {
    getCommands(stationId, 20)
      .then(setHistory)
      .catch((e) => console.error(e));
  }, [stationId]);

  useEffect(() => {
    loadHistory();
    const id = setInterval(loadHistory, 5000);
    return () => clearInterval(id);
  }, [loadHistory]);

  const showToast = (message, ok = true) => {
    setToast({ message, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const send = async (command) => {
    setBusy(true);
    try {
      await postCommand(stationId, command);
      showToast(`Sent: ${command.command}`);
      loadHistory();
    } catch (err) {
      showToast(err.message, false);
    } finally {
      setBusy(false);
    }
  };

  const otherGenerator = activeGenerator === "backup" ? "primary" : "backup";

  return (
    <div className="control-panel">
      <div className="control-panel__header">
        <h3 className="control-panel__title">Station Control</h3>
        {toast && (
          <span className={`control-panel__toast ${toast.ok ? "is-ok" : "is-error"}`}>
            {toast.message}
          </span>
        )}
      </div>

      <div className="control-panel__actions">
        <button
          className="control-panel__button"
          disabled={busy}
          onClick={() => send({ command: "switch_generator", target: otherGenerator })}
        >
          Switch to {otherGenerator} generator
          {activeGenerator && (
            <span className="control-panel__current"> (current: {activeGenerator})</span>
          )}
        </button>

        <button
          className="control-panel__button"
          disabled={busy}
          onClick={() => send({ command: "force_resupply_request" })}
        >
          Force resupply request
        </button>

        <div className="control-panel__heater">
          <input
            type="number"
            step="0.5"
            value={heaterValue}
            onChange={(e) => setHeaterValue(e.target.value)}
          />
          <button
            className="control-panel__button"
            disabled={busy}
            onClick={() =>
              send({
                command: "adjust_heater_setpoint",
                value: parseFloat(heaterValue),
              })
            }
          >
            Set heater setpoint (°C)
          </button>
        </div>
      </div>

      <div className="control-panel__history">
        <h4>Recent Actions</h4>
        {history.length === 0 && (
          <p className="control-panel__empty">No commands issued yet.</p>
        )}
        <ul>
          {history.map((row) => (
            <li
              key={row.id}
              className={`control-panel__history-row control-panel__history-row--${row.status}`}
            >
              <span className="control-panel__history-time num">{formatTime(row.ts)}</span>
              <span className="control-panel__history-command">{row.command_type}</span>
              <span className="control-panel__history-issuer">{row.issued_by}</span>
              <span className="control-panel__history-status">{row.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
