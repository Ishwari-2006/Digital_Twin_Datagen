# Antarctic Digital Twin — Dashboard

React + Recharts frontend for the Maitri/Bharati digital twin, per Section
3.1/3.5 of the team reference doc. Talks to the FastAPI backend (`api.py`
from `digital_twin_datagen`) — nothing here talks to Postgres or MQTT
directly.

## What it covers

- **Fleet view** (`/`) — both stations side by side: temperature, power,
  fuel, battery, days-of-autonomy at a glance, plus a comms-status pill and
  any active anomaly.
- **Per-station detail view** — click a station to open it. Four tabs match
  the doc's four domains: Environmental, Energy, Infrastructure, Logistics.
  Each tab shows current values as tiles plus a 6-hour history chart per
  signal.
- **Staleness / backfill indicator** — the status pill compares a record's
  `ts` (when it was sensed) against `received_at` (when it landed in the
  DB). If a record arrived 2+ minutes after it was sensed, the pill shows
  "Caught up · was Xm behind" instead of "Online" — this is the visible
  proof of the comms-blackout store-and-forward behavior from Section 3.3.
- Polls the API every 5s for current values, every 30s for chart history —
  no manual refresh needed during a demo.

## Setup

```bash
npm install
cp .env.example .env   # edit VITE_API_BASE_URL if your API isn't on localhost:8000
npm run dev
```

Requires the backend already running (see `digital_twin_datagen/README.md`):
Postgres + Mosquitto + `mqtt_subscriber.py` + `mqtt_publisher.py` +
`uvicorn api:app --port 8000`.

## Design notes

Dark "polar night" palette (deep navy, not pure black) with an ice-blue
primary accent, aurora green for nominal/good status, amber for caution,
and a warm flare-orange for critical/anomaly states — chosen to match the
subject (polar station, aurora, ice) rather than a generic dashboard theme.
Fraunces (serif) for station names/headings gives it a field-expedition-log
character; Inter handles body text and all numeric data.

## Project structure

```
src/
├── api.js                    # fetch wrapper for the FastAPI backend
├── theme.css                 # design tokens (colors, type) + base styles
├── App.jsx                   # fleet/detail view switcher
└── components/
    ├── TopBar.jsx             # title + live clock
    ├── FleetView.jsx          # both stations side by side
    ├── StationPanel.jsx       # one station's summary card (fleet view)
    ├── StationDetail.jsx      # per-station domain tabs + charts
    ├── DomainSection.jsx      # tiles + charts layout, reused per domain
    ├── MetricTile.jsx         # single current-value tile
    ├── TimeSeriesChart.jsx    # themed Recharts line chart wrapper
    └── StatusPill.jsx         # comms status + staleness indicator
```

## Next step (Section 3.4, hrs 24–30)

The anomaly detector. Once it exists, the natural hook-in point is the
`active_anomalies` banner already shown on both the fleet cards and the
station detail header — swap the generator's ground-truth string for the
detector's live output and the UI needs no other changes.
