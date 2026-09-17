import { useState } from "react";
import "./StationTwin.css";

// Each zone maps to the telemetry/anomaly signals that determine its health.
// Power/Fuel/Battery/Weather are backed by the actual z-score detector
// (anomalies.anomalies); Comms and Quarters use direct status fields from
// telemetry instead, since comms_status/heater_status are categorical, not
// something a z-score applies to. Both are shown as "live" -- the inspect
// panel is honest about which is which.
const ZONES = [
  {
    id: "power",
    label: "Power Plant",
    x: 22,
    y: 26,
    signals: ["power_draw_kw"],
  },
  {
    id: "fuel",
    label: "Fuel Depot",
    x: 12,
    y: 66,
    signals: ["fuel_burn_rate_lph"],
  },
  {
    id: "battery",
    label: "Battery Bank",
    x: 38,
    y: 80,
    signals: ["battery_soc_pct"],
  },
  {
    id: "quarters",
    label: "Living Quarters",
    x: 55,
    y: 46,
    signals: [],
    statusField: "heater_status",
  },
  {
    id: "comms",
    label: "Comms & Antenna",
    x: 80,
    y: 20,
    signals: [],
    statusField: "comms_status",
  },
  {
    id: "weather",
    label: "Weather Mast",
    x: 86,
    y: 66,
    signals: ["ambient_temp_c", "wind_speed_ms"],
  },
];

const LINKS = [
  ["fuel", "power"],
  ["power", "battery"],
  ["power", "quarters"],
  ["quarters", "comms"],
  ["weather", "quarters", "dashed"],
];

const COLOR = {
  normal: "var(--aurora)",
  warn: "var(--amber)",
  critical: "var(--flare)",
};

function zoneSeverity(zone, latest, anomalyMap) {
  if (zone.statusField === "comms_status") {
    if (latest?.comms_status === "blackout") return "critical";
    if (latest?.comms_status === "degraded") return "warn";
    return "normal";
  }
  if (zone.statusField === "heater_status") {
    return latest?.heater_status === "fault" ? "critical" : "normal";
  }
  let worst = "normal";
  for (const sig of zone.signals) {
    const flag = anomalyMap[sig];
    if (!flag) continue;
    if (flag.severity === "critical") return "critical";
    if (flag.severity === "warn") worst = "warn";
  }
  return worst;
}

const UNITS = {
  power_draw_kw: " kW",
  fuel_burn_rate_lph: " L/h",
  ambient_temp_c: "°C",
  wind_speed_ms: " m/s",
  battery_soc_pct: "%",
};

function formatValue(sig, value) {
  if (typeof value !== "number") return value;
  return `${value.toFixed(1)}${UNITS[sig] || ""}`;
}

const SIGNAL_LABELS = {
  power_draw_kw: "Power draw",
  fuel_burn_rate_lph: "Fuel burn rate",
  ambient_temp_c: "Ambient temp",
  wind_speed_ms: "Wind speed",
  battery_soc_pct: "Battery charge",
};

function zoneMetrics(zone, latest) {
  if (zone.statusField === "comms_status") {
    return [{ label: "Comms status", value: latest?.comms_status }];
  }
  if (zone.statusField === "heater_status") {
    return [
      { label: "Heater", value: latest?.heater_status },
      { label: "HVAC", value: latest?.hvac_status },
    ];
  }
  return zone.signals.map((sig) => ({
    label: SIGNAL_LABELS[sig] || sig,
    value: formatValue(sig, latest?.[sig]),
  }));
}

function findZonePoint(id) {
  return ZONES.find((z) => z.id === id);
}

export default function StationTwin({ latest, anomalies }) {
  const [selected, setSelected] = useState(null);

  const anomalyMap = {};
  (anomalies?.anomalies || []).forEach((a) => {
    anomalyMap[a.signal] = a;
  });

  const scored = ZONES.map((z) => ({
    ...z,
    severity: zoneSeverity(z, latest, anomalyMap),
  }));
  const activeZone = scored.find((z) => z.id === selected) || null;

  if (!latest) {
    return <div className="twin-empty">Loading twin…</div>;
  }

  return (
    <div className="station-twin">
      <svg
        className="station-twin__svg"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
      >
        {LINKS.map(([a, b, style], i) => {
          const pa = findZonePoint(a);
          const pb = findZonePoint(b);
          return (
            <line
              key={i}
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              className={`station-twin__link ${style === "dashed" ? "station-twin__link--dashed" : ""}`}
            />
          );
        })}

        {scored.map((z) => (
          <g
            key={z.id}
            className={`station-twin__zone station-twin__zone--${z.severity} ${selected === z.id ? "is-selected" : ""}`}
            transform={`translate(${z.x}, ${z.y})`}
            onClick={() => setSelected(z.id === selected ? null : z.id)}
            tabIndex={0}
            role="button"
            aria-label={`${z.label}: ${z.severity}`}
          >
            {z.severity === "critical" && (
              <circle className="station-twin__pulse" r="7" />
            )}
            <circle
              className="station-twin__node"
              r="4.2"
              fill={COLOR[z.severity]}
            />
            <text className="station-twin__label" y="8.5" textAnchor="middle">
              {z.label}
            </text>
          </g>
        ))}
      </svg>

      <div className="station-twin__legend">
        <span>
          <i style={{ background: COLOR.normal }} /> Normal
        </span>
        <span>
          <i style={{ background: COLOR.warn }} /> Warning
        </span>
        <span>
          <i style={{ background: COLOR.critical }} /> Critical
        </span>
      </div>

      {activeZone && (
        <div className="station-twin__panel">
          <div className="station-twin__panel-header">
            <span
              className={`station-twin__panel-dot station-twin__panel-dot--${activeZone.severity}`}
            />
            <span className="station-twin__panel-title">
              {activeZone.label}
            </span>
            <button
              className="station-twin__panel-close"
              onClick={() => setSelected(null)}
            >
              ✕
            </button>
          </div>
          <div className="station-twin__panel-body">
            {zoneMetrics(activeZone, latest).map((m) => (
              <div key={m.label} className="station-twin__metric">
                <span className="station-twin__metric-label">{m.label}</span>
                <span className="station-twin__metric-value num">
                  {String(m.value)}
                </span>
              </div>
            ))}
            {activeZone.signals
              .filter((sig) => anomalyMap[sig])
              .map((sig) => (
                <div
                  key={sig}
                  className={`station-twin__flag station-twin__flag--${anomalyMap[sig].severity}`}
                >
                  Detected: {anomalyMap[sig].label} is unusual (z=
                  {anomalyMap[sig].z_score})
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
