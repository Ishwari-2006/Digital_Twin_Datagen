import { useState } from "react";
import "./StationTwin.css";

// Room geometry is kept in the UI because the telemetry contract describes
// systems, not architectural coordinates. The two plans follow the distinct
// footprints of the Maitri and Bharati research stations at a useful overview
// scale, while the live signals still determine each room's status.
const ZONES = [
  {
    id: "power",
    label: "Power Plant",
    shortLabel: "POWER",
    signals: ["power_draw_kw"],
    loadField: "generator_load_pct",
    loadWarnAt: 85,
    loadCriticalAt: 95,
  },
  {
    id: "fuel",
    label: "Fuel Depot",
    shortLabel: "FUEL",
    signals: ["fuel_burn_rate_lph"],
  },
  {
    id: "battery",
    label: "Battery Bank",
    shortLabel: "BATTERY",
    signals: ["battery_soc_pct"],
  },
  {
    id: "quarters",
    label: "Living Quarters",
    shortLabel: "LIVING",
    signals: [],
    statusField: "heater_status",
  },
  {
    id: "comms",
    label: "Comms & Antenna",
    shortLabel: "COMMS",
    signals: [],
    statusField: "comms_status",
  },
  {
    id: "weather",
    label: "Weather Mast",
    shortLabel: "WEATHER",
    signals: ["ambient_temp_c", "wind_speed_ms"],
  },
];

const FLOOR_PLANS = {
  maitri: {
    name: "Maitri",
    subtitle: "Dakshin Gangotri ridge · operational level",
    viewBox: "0 0 120 82",
    rooms: [
      {
        id: "comms",
        label: "Comms room",
        shortLabel: "COMMS",
        equipment: "radio / sat",
        x: 8,
        y: 8,
        width: 18,
        height: 14,
      },
      {
        id: "quarters",
        label: "Sleeping module",
        shortLabel: "SLEEP",
        equipment: "berths",
        x: 29,
        y: 8,
        width: 18,
        height: 14,
      },
      {
        id: "dining",
        label: "Mess & galley",
        shortLabel: "MESS",
        equipment: "galley",
        x: 50,
        y: 8,
        width: 20,
        height: 14,
      },
      {
        id: "medical",
        label: "Medical room",
        shortLabel: "MED",
        equipment: "clinic",
        x: 73,
        y: 8,
        width: 16,
        height: 14,
      },
      {
        id: "lab",
        label: "Science lab",
        shortLabel: "LAB",
        equipment: "sample bench",
        x: 92,
        y: 8,
        width: 19,
        height: 14,
      },
      {
        id: "power",
        label: "Power plant",
        shortLabel: "POWER",
        equipment: "gensets",
        x: 8,
        y: 29,
        width: 21,
        height: 18,
      },
      {
        id: "workshop",
        label: "Workshop",
        shortLabel: "WORK",
        equipment: "tools",
        x: 32,
        y: 29,
        width: 20,
        height: 18,
      },
      {
        id: "airlock",
        label: "Main airlock",
        shortLabel: "AIRLOCK",
        equipment: "entry",
        x: 55,
        y: 29,
        width: 11,
        height: 18,
      },
      {
        id: "battery",
        label: "Battery room",
        shortLabel: "BATTERY",
        equipment: "UPS bank",
        x: 69,
        y: 29,
        width: 19,
        height: 18,
      },
      {
        id: "server",
        label: "Server room",
        shortLabel: "SERVER",
        equipment: "network",
        x: 91,
        y: 29,
        width: 20,
        height: 18,
      },
      {
        id: "fuel",
        label: "Fuel store",
        shortLabel: "FUEL",
        equipment: "tanks",
        x: 8,
        y: 55,
        width: 21,
        height: 17,
      },
      {
        id: "stores",
        label: "Cold stores",
        shortLabel: "STORES",
        equipment: "provisions",
        x: 32,
        y: 55,
        width: 20,
        height: 17,
      },
      {
        id: "laundry",
        label: "Laundry",
        shortLabel: "LAUNDRY",
        equipment: "utility",
        x: 55,
        y: 55,
        width: 20,
        height: 17,
      },
      {
        id: "water",
        label: "Water plant",
        shortLabel: "WATER",
        equipment: "melt tanks",
        x: 78,
        y: 55,
        width: 19,
        height: 17,
      },
      {
        id: "weather",
        label: "Weather mast",
        shortLabel: "WEATHER",
        equipment: "mast",
        x: 101,
        y: 55,
        width: 10,
        height: 17,
      },
    ],
    corridors: [
      { x: 8, y: 24, width: 103, height: 4 },
      { x: 8, y: 49, width: 103, height: 4 },
      { x: 68, y: 24, width: 4, height: 29 },
    ],
    labels: [
      { text: "PLAN NORTH", x: 8, y: 5 },
      { text: "PRIMARY CORRIDOR", x: 8, y: 27 },
      { text: "SERVICE ACCESS", x: 8, y: 52 },
    ],
  },
  bharati: {
    name: "Bharati",
    subtitle: "Larsemann Hills · elevated module deck",
    viewBox: "0 0 120 82",
    rooms: [
      {
        id: "quarters",
        label: "Sleeping module",
        shortLabel: "SLEEP",
        equipment: "berths",
        x: 8,
        y: 8,
        width: 22,
        height: 15,
      },
      {
        id: "dining",
        label: "Mess & galley",
        shortLabel: "MESS",
        equipment: "galley",
        x: 33,
        y: 8,
        width: 18,
        height: 15,
      },
      {
        id: "medical",
        label: "Medical room",
        shortLabel: "MED",
        equipment: "clinic",
        x: 54,
        y: 8,
        width: 15,
        height: 15,
      },
      {
        id: "lab",
        label: "Science lab",
        shortLabel: "LAB",
        equipment: "sample bench",
        x: 72,
        y: 8,
        width: 18,
        height: 15,
      },
      {
        id: "comms",
        label: "Comms room",
        shortLabel: "COMMS",
        equipment: "radio / sat",
        x: 93,
        y: 8,
        width: 18,
        height: 15,
      },
      {
        id: "power",
        label: "Power plant",
        shortLabel: "POWER",
        equipment: "gensets",
        x: 8,
        y: 30,
        width: 20,
        height: 18,
      },
      {
        id: "workshop",
        label: "Workshop",
        shortLabel: "WORK",
        equipment: "tools",
        x: 31,
        y: 30,
        width: 22,
        height: 18,
      },
      {
        id: "airlock",
        label: "Cargo airlock",
        shortLabel: "AIRLOCK",
        equipment: "cargo",
        x: 56,
        y: 30,
        width: 12,
        height: 18,
      },
      {
        id: "battery",
        label: "Battery room",
        shortLabel: "BATTERY",
        equipment: "UPS bank",
        x: 71,
        y: 30,
        width: 19,
        height: 18,
      },
      {
        id: "server",
        label: "Server room",
        shortLabel: "SERVER",
        equipment: "network",
        x: 93,
        y: 30,
        width: 18,
        height: 18,
      },
      {
        id: "fuel",
        label: "Fuel store",
        shortLabel: "FUEL",
        equipment: "tanks",
        x: 8,
        y: 55,
        width: 20,
        height: 17,
      },
      {
        id: "water",
        label: "Water plant",
        shortLabel: "WATER",
        equipment: "melt tanks",
        x: 31,
        y: 55,
        width: 18,
        height: 17,
      },
      {
        id: "stores",
        label: "Stores",
        shortLabel: "STORES",
        equipment: "provisions",
        x: 52,
        y: 55,
        width: 21,
        height: 17,
      },
      {
        id: "generator",
        label: "Backup generator",
        shortLabel: "BACKUP",
        equipment: "genset",
        x: 76,
        y: 55,
        width: 19,
        height: 17,
      },
      {
        id: "weather",
        label: "Weather mast",
        shortLabel: "WEATHER",
        equipment: "mast",
        x: 98,
        y: 55,
        width: 13,
        height: 17,
      },
    ],
    corridors: [
      { x: 8, y: 25, width: 103, height: 4 },
      { x: 8, y: 50, width: 103, height: 4 },
      { x: 68, y: 25, width: 4, height: 29 },
    ],
    labels: [
      { text: "PLAN NORTH", x: 8, y: 5 },
      { text: "PRIMARY CORRIDOR", x: 8, y: 28 },
      { text: "SERVICE ACCESS", x: 8, y: 53 },
    ],
  },
};

const DEFAULT_FLOOR_PLAN = FLOOR_PLANS.maitri;

const TOP_DOWN_LAYOUTS = {
  maitri: {
    rooms: [
      {
        id: "comms",
        x: 8,
        y: 11,
        width: 22,
        height: 19,
        points: "8,8 30,8 30,30 8,30",
        equipment: "radio / sat",
      },
      {
        id: "quarters",
        x: 30,
        y: 8,
        width: 39,
        height: 22,
        points: "30,8 69,8 69,30 30,30",
        equipment: "berths",
      },
      {
        id: "power",
        x: 69,
        y: 10,
        width: 42,
        height: 20,
        points: "69,8 111,8 111,30 69,30",
        equipment: "gensets",
      },
      {
        id: "fuel",
        x: 8,
        y: 49,
        width: 32,
        height: 19,
        points: "8,49 40,49 40,72 8,72",
        equipment: "tanks",
      },
      {
        id: "battery",
        x: 40,
        y: 49,
        width: 24,
        height: 21,
        points: "40,49 64,49 64,72 40,72",
        equipment: "UPS bank",
      },
      {
        id: "weather",
        x: 64,
        y: 49,
        width: 47,
        height: 23,
        points: "64,49 111,49 111,72 64,72",
        equipment: "mast",
      },
    ],
    corridors: [{ x: 8, y: 30, width: 103, height: 19 }],
    connectors: [],
    doors: [
      { d: "M16 30h6" },
      { d: "M48 30h6" },
      { d: "M87 30h6" },
      { d: "M19 49h6" },
      { d: "M49 49h6" },
      { d: "M84 49h6" },
    ],
    building: { x: 8, y: 8, width: 103, height: 64 },
    labels: [
      { text: "NORTH", x: 8, y: 5 },
      { text: "PRIMARY ACCESS CORRIDOR", x: 41, y: 40.5 },
      { text: "OPEN FLOOR PLATE / SERVICE ACCESS", x: 8, y: 77 },
    ],
  },
  bharati: {
    rooms: [
      {
        id: "comms",
        x: 8,
        y: 9,
        width: 30,
        height: 21,
        points: "8,8 38,8 38,30 8,30",
        equipment: "radio / sat",
      },
      {
        id: "quarters",
        x: 38,
        y: 8,
        width: 30,
        height: 22,
        points: "38,8 68,8 68,30 38,30",
        equipment: "berths",
      },
      {
        id: "power",
        x: 68,
        y: 11,
        width: 43,
        height: 19,
        points: "68,8 111,8 111,30 68,30",
        equipment: "gensets",
      },
      {
        id: "fuel",
        x: 8,
        y: 49,
        width: 20,
        height: 20,
        points: "8,49 28,49 28,72 8,72",
        equipment: "tanks",
      },
      {
        id: "battery",
        x: 28,
        y: 49,
        width: 42,
        height: 22,
        points: "28,49 70,49 70,72 28,72",
        equipment: "UPS bank",
      },
      {
        id: "weather",
        x: 70,
        y: 49,
        width: 41,
        height: 19,
        points: "70,49 111,49 111,72 70,72",
        equipment: "mast",
      },
    ],
    corridors: [{ x: 8, y: 30, width: 103, height: 19 }],
    connectors: [],
    doors: [
      { d: "M18 30h6" },
      { d: "M51 30h6" },
      { d: "M88 30h6" },
      { d: "M15 49h6" },
      { d: "M46 49h6" },
      { d: "M85 49h6" },
    ],
    building: { x: 8, y: 8, width: 103, height: 64 },
    labels: [
      { text: "NORTH", x: 8, y: 5 },
      { text: "PRIMARY ACCESS CORRIDOR", x: 41, y: 40.5 },
      { text: "OPEN FLOOR PLATE / SERVICE ACCESS", x: 8, y: 77 },
    ],
  },
};

const COLOR = {
  normal: "var(--aurora)",
  warn: "var(--amber)",
  critical: "var(--flare)",
};

// Simulator events are direct, operational facts. They must colour their
// affected zone even when the statistical detector has not raised a signal.
const GROUND_TRUTH_ZONE_SEVERITY = {
  fuel_leak: { zoneId: "fuel", severity: "critical" },
  power_spike: { zoneId: "power", severity: "critical" },
  heater_failure: { zoneId: "quarters", severity: "critical" },
  comms_blackout: { zoneId: "comms", severity: "critical" },
  storm: { zoneId: "weather", severity: "warn" },
};

function zoneSeverity(zone, latest, anomalyMap) {
  if (!zone) return "normal";
  const activeKinds = (latest?.active_anomalies || "none")
    .split(",")
    .filter((kind) => kind && kind !== "none");
  const directSeverity = activeKinds.reduce((worst, kind) => {
    const event = GROUND_TRUTH_ZONE_SEVERITY[kind];
    if (!event || event.zoneId !== zone.id) return worst;
    return event.severity === "critical" ? "critical" : "warn";
  }, "normal");

  if (directSeverity === "critical") return "critical";
  if (zone.statusField === "comms_status") {
    if (latest?.comms_status === "blackout") return "critical";
    if (latest?.comms_status === "degraded") return "warn";
    return directSeverity;
  }
  if (zone.statusField === "heater_status") {
    return latest?.heater_status === "fault" ? "critical" : directSeverity;
  }
  let worst = directSeverity;
  for (const sig of zone.signals) {
    const flag = anomalyMap[sig];
    if (!flag) continue;
    if (flag.severity === "critical") return "critical";
    if (flag.severity === "warn") worst = "warn";
  }
  if (zone.loadField) {
    const load = latest?.[zone.loadField];
    if (typeof load === "number") {
      if (load >= zone.loadCriticalAt) return "critical";
      if (load >= zone.loadWarnAt && worst === "normal") worst = "warn";
    }
  }
  return worst;
}

const UNITS = {
  power_draw_kw: " kW",
  fuel_burn_rate_lph: " L/h",
  ambient_temp_c: "°C",
  wind_speed_ms: " m/s",
  battery_soc_pct: "%",
  generator_load_pct: "%",
  heater_setpoint_c: "°C",
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

const ROOM_LABEL_LINES = {
  "Living Quarters": ["Living", "Quarters"],
  "Comms & Antenna": ["Comms &", "Antenna"],
};

function zoneMetrics(zone, latest) {
  if (!zone.signals?.length && !zone.statusField) {
    return [
      {
        label: "Installed equipment",
        value: zone.equipment || "Facility area",
      },
    ];
  }
  if (zone.statusField === "comms_status") {
    return [{ label: "Comms status", value: latest?.comms_status }];
  }
  if (zone.statusField === "heater_status") {
    return [
      { label: "Heater", value: latest?.heater_status },
      { label: "HVAC", value: latest?.hvac_status },
      {
        label: "Heater setpoint",
        value: formatValue("heater_setpoint_c", latest?.heater_setpoint_c),
      },
    ];
  }
  const base = zone.signals.map((sig) => ({
    label: SIGNAL_LABELS[sig] || sig,
    value: formatValue(sig, latest?.[sig]),
  }));
  if (zone.loadField) {
    base.push(
      {
        label: "Generator load",
        value: formatValue(zone.loadField, latest?.[zone.loadField]),
      },
      { label: "Active generator", value: latest?.active_generator },
    );
  }
  return base;
}

export default function StationTwin({ latest, anomalies }) {
  const [selected, setSelected] = useState(null);

  const anomalyMap = {};
  (anomalies?.anomalies || []).forEach((a) => {
    anomalyMap[a.signal] = a;
  });

  const floorPlan = {
    ...(FLOOR_PLANS[latest.station_id] || DEFAULT_FLOOR_PLAN),
    ...(TOP_DOWN_LAYOUTS[latest.station_id] || {}),
  };
  // The floor plan is an architectural drawing, but the twin deliberately
  // keeps the six original monitored points as its only interactive rooms.
  const scored = ZONES.map((zone) => {
    const room = floorPlan.rooms.find((candidate) => candidate.id === zone.id);
    return {
      ...room,
      ...zone,
      severity: zoneSeverity(zone, latest, anomalyMap),
    };
  });
  const activeZone = scored.find((z) => z.id === selected) || null;
  const affectedRooms = scored.filter((z) => z.severity !== "normal");
  const hasCriticalRoom = affectedRooms.some((z) => z.severity === "critical");

  if (!latest) {
    return <div className="twin-empty">Loading twin…</div>;
  }

  return (
    <div className="station-twin">
      <div className="station-twin__heading">
        <div>
          <p className="station-twin__eyebrow">TOP-DOWN FACILITY PLAN</p>
          <h3>{floorPlan.name} research station</h3>
          <p>{floorPlan.subtitle}</p>
        </div>
        <div className="station-twin__orientation" aria-label="North is up">
          <span>N</span>
          <i />
        </div>
      </div>

      {affectedRooms.length > 0 && (
        <div
          className={`station-twin__alert station-twin__alert--${hasCriticalRoom ? "critical" : "warn"}`}
        >
          <span className="station-twin__alert-marker" />
          <div>
            <strong>
              {affectedRooms.length === 1
                ? "Anomaly detected in"
                : "Anomalies detected in"}
            </strong>
            <span>{affectedRooms.map((room) => room.label).join(" · ")}</span>
          </div>
        </div>
      )}

      <svg
        className="station-twin__svg"
        viewBox={floorPlan.viewBox}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`${floorPlan.name} top-down floor plan`}
      >
        <rect
          className="station-twin__ground"
          x="2"
          y="2"
          width="116"
          height="78"
          rx="1"
        />
        <rect
          className="station-twin__building-outline"
          {...floorPlan.building}
        />
        {floorPlan.corridors.map((corridor, index) => (
          <rect key={index} className="station-twin__corridor" {...corridor} />
        ))}
        {floorPlan.connectors.map((connector, index) => (
          <line
            key={index}
            className="station-twin__connector"
            {...connector}
          />
        ))}
        {floorPlan.labels.map((label) => (
          <text
            key={label.text}
            className="station-twin__plan-label"
            x={label.x}
            y={label.y}
          >
            {label.text}
          </text>
        ))}

        {scored.map((z) => (
          <g
            key={z.id}
            className={`station-twin__room station-twin__room--${z.severity} ${selected === z.id ? "is-selected" : ""}`}
            onClick={() => setSelected(z.id === selected ? null : z.id)}
            tabIndex={0}
            role="button"
            aria-label={`${z.label}: ${z.severity}`}
          >
            <polygon className="station-twin__room-fill" points={z.points} />
            {z.severity === "critical" && (
              <rect
                className="station-twin__pulse"
                x={z.x - 1}
                y={z.y - 1}
                width={z.width + 2}
                height={z.height + 2}
                rx="1.5"
              />
            )}
            <text
              className="station-twin__room-label"
              x={z.x + z.width / 2}
              y={z.y + z.height / 2 - (ROOM_LABEL_LINES[z.label] ? 1.5 : 0)}
              textAnchor="middle"
            >
              {(ROOM_LABEL_LINES[z.label] || [z.label]).map((line, index) => (
                <tspan
                  key={line}
                  x={z.x + z.width / 2}
                  dy={index === 0 ? 0 : 3}
                >
                  {line}
                </tspan>
              ))}
            </text>
            <text
              className="station-twin__room-size"
              x={z.x + z.width / 2}
              y={z.y + z.height / 2 + 4}
              textAnchor="middle"
            >
              {z.width} × {z.height} m
            </text>
            <text
              className="station-twin__room-equipment"
              x={z.x + z.width / 2}
              y={z.y + z.height / 2 + 7}
              textAnchor="middle"
            >
              {z.equipment}
            </text>
          </g>
        ))}
        {floorPlan.doors.map((door, index) => (
          <path key={index} className="station-twin__door" d={door.d} />
        ))}
        <text className="station-twin__scale" x="105" y="76">
          10 m
        </text>
        <path className="station-twin__scale-line" d="M94 77H103" />
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
            <span className="station-twin__panel-location">Room selected</span>
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
