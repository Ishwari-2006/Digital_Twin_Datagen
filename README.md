# Digital Twin Data Generator — Maitri & Bharati (SIH2026)

This is the **Physical layer** stand-in from Section 3.1 of the team reference
doc: a synthetic sensor generator for both stations, across all four domains
(infrastructure, energy, logistics, environmental), tagged with `station_id`
from the very first record (Section 3.2).

## Files

| File                | Purpose                                                                                                                                      |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `station_config.py` | Per-station climate + equipment parameters, anchored to public historical data for Schirmacher Oasis (Maitri) and Larsemann Hills (Bharati). |
| `generator.py`      | Core simulator — `StationSimulator` (stateful, tick-by-tick) and `generate_batch()` / `generate_fleet_batch()` (batch CSV/JSON generation).  |
| `cli.py`            | Command-line batch generation.                                                                                                               |
| `stream.py`         | Real-time-ish streaming mode (JSON lines, speed-up factor) — the seam where MQTT/WebSocket plugs in for Section 3.1's Data layer.            |

## Quick start

```bash
pip install -r requirements.txt

# 72 hours, both stations, 5-minute resolution
python cli.py --station both --hours 72 --interval 5 --out data/fleet_72h.csv

# A single-station demo dataset with anomalies at known times (for slides/testing
# the anomaly-detection feature against ground truth)
python cli.py --station maitri --hours 24 --out data/maitri_demo.csv \
    --anomaly 6:fuel_leak --anomaly 14:comms_blackout --anomaly 18:power_spike

# Live-ish streaming for the actual demo (60x speed = 5 sim-min every 5 wall-sec)
python stream.py --interval 5 --speed 60 --demo-trigger 30:maitri:fuel_leak
```

## Record schema

One row per station per tick:

| Field                                                                                                       | Domain                        | Notes                                                                                                                                                                                              |
| ----------------------------------------------------------------------------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `timestamp`, `station_id`                                                                                   | —                             | Always present; `station_id` is `maitri` or `bharati`.                                                                                                                                             |
| `ambient_temp_c`, `wind_speed_ms`, `weather_anomaly_flag`                                                   | Environmental                 | Seasonal + diurnal sinusoid, mean-reverting noise, storm events spike wind and drop temp.                                                                                                          |
| `comms_status`                                                                                              | Environmental / cross-cutting | `online` / `degraded` (during storms) / `blackout`.                                                                                                                                                |
| `power_draw_kw`, `generator_load_pct`, `battery_soc_pct`, `battery_state`                                   | Energy                        | Diurnal load cycle, cold-weather heating penalty, battery buffers short-term load (not primary storage).                                                                                           |
| `fuel_tank_level_l`, `fuel_tank_pct`, `fuel_burn_rate_lph`, `fuel_burn_rate_lph_avg24h`, `days_of_autonomy` | Infrastructure / Energy       | Fuel burn tracks generator output; tank drains accordingly.                                                                                                                                        |
| `hvac_status`, `heater_status`                                                                              | Infrastructure                | `heater_status` goes to `fault` during a heater-failure anomaly.                                                                                                                                   |
| `resupply_window_days_remaining`, `resupply_recommendation`                                                 | Logistics                     | Simple rule combining days-of-autonomy vs. time to the next seasonal resupply window and current weather.                                                                                          |
| `active_anomalies`                                                                                          | —                             | Comma-joined list of currently active anomaly kinds, or `none` — ground truth for testing the intelligence feature (Section 3.4).                                                                  |
| `_delivered_live`                                                                                           | —                             | `False` while `comms_status == blackout`; those records are also buffered in `sim._comms_queue` and returned by `sim.drain_queue()` once comms recover — the store-and-forward demo (Section 3.3). |

## Anomaly types

`fuel_leak`, `power_spike`, `heater_failure`, `comms_blackout`, `storm` — each
can fire spontaneously at a low random rate (tune `_SPONTANEOUS_HOURLY_PROB` in
`generator.py`) or be forced via `StationSimulator.trigger_anomaly(kind, at)` /
the `--anomaly HOUR:KIND` CLI flag / `--demo-trigger SECONDS:STATION:KIND` in
streaming mode — this is what "simulate event" and "simulate comms blackout"
in Section 5.1's demo checklist hook into.

## What's anchored to real data vs. assumed

Climate parameters (annual mean, seasonal swing, wind) are anchored to public
historical figures for each station's location — say so explicitly in the
pitch (Section 4's "no real sensor data" mitigation). Power/fuel/logistics
baselines (generator sizing, tank capacity, fuel consumption rates) are
reasonable hackathon-scale assumptions, not measured station data — the doc's
"name the simulation gap upfront" framing (Section 2.2) applies to these too.

## Pipeline: MQTT → Postgres/TimescaleDB → API (Section 3.1 Data layer)

Three new pieces turn the generator into an actual running pipeline:

| File                 | Role                                                                                                                                                                                                                                                                                               |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `db/schema.sql`      | Postgres table for telemetry (TimescaleDB-hypertable-ready — see below).                                                                                                                                                                                                                           |
| `db/db.py`           | Insert/query helpers, used by both the subscriber and the API.                                                                                                                                                                                                                                     |
| `mqtt_publisher.py`  | Steps the generator forward and publishes each record to `station/<id>/telemetry` over MQTT. Handles the comms-blackout backlog: while a station is blacked out, nothing is published live; the moment it recovers, the whole buffered backlog is flushed in one burst, tagged `"backfill": true`. |
| `mqtt_subscriber.py` | Subscribes to `station/+/telemetry` and writes every record into Postgres. Run this continuously — it's the thing keeping the DB in sync.                                                                                                                                                          |
| `api.py`             | FastAPI read layer for the future dashboard: latest reading (per station or fleet-wide), and history over a time window.                                                                                                                                                                           |

### One-time setup

```bash
# Postgres
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres psql -c "CREATE DATABASE digital_twin;"
sudo -u postgres psql -d digital_twin -f db/schema.sql

# Mosquitto (MQTT broker)
sudo apt-get install mosquitto mosquitto-clients
sudo service mosquitto start   # or: mosquitto -d

# Python deps
pip install -r requirements.txt
cp .env.example .env   # edit if your DB creds differ, then `export $(cat .env | xargs)`
```

**TimescaleDB (optional):** the schema works on plain Postgres as-is. If you
install the TimescaleDB extension (not available via plain `apt` on every
system — see [timescale.com/docs](https://docs.timescale.com) for your OS),
uncomment the two lines at the bottom of `db/schema.sql` and re-run it to turn
`telemetry` into a hypertable. Nothing else changes — inserts, queries, and
the API work identically either way, since a hypertable is a normal table
underneath.

### Running it (3 terminals)

```bash
# Terminal 1 — keeps the DB in sync, leave running
python mqtt_subscriber.py

# Terminal 2 — the "sensors": generates + publishes telemetry
python mqtt_publisher.py --interval 5 --speed 60
# For a demo with a guaranteed event:
python mqtt_publisher.py --interval 5 --speed 60 --demo-trigger 30:maitri:comms_blackout

# Terminal 3 — the read API
uvicorn api:app --reload --port 8000
```

Then:

```bash
curl localhost:8000/stations
curl localhost:8000/telemetry/latest                 # fleet view — latest row per station
curl localhost:8000/telemetry/latest?station=maitri
curl "localhost:8000/telemetry/history?station=maitri&hours=2"
```

This was tested end-to-end while building it, including triggering a comms
blackout on Maitri and confirming: Maitri stops appearing in the DB live,
Bharati keeps updating unaffected, and the moment the blackout ends, all of
Maitri's buffered readings land in the DB in one burst — `received_at` on
those rows is nearly identical while `ts` spans the whole blackout window,
which is the visible proof of "stale, then caught up" for a dashboard to show.

## Next step (Section 3.1 Data layer, continued / hours 12–24)

The pipeline is done — next is the dashboard (React + Recharts) consuming
the API above: per-station views, a fleet health summary tile, and a visible
staleness indicator that uses exactly the `received_at` vs `ts` gap described
above. The anomaly detector (Section 3.4, hrs 24–30) comes after that, once
the dashboard has somewhere to show its output.

## Anomaly detector (Section 3.4)

`detector.py` — rolling z-score per signal (power draw, fuel burn rate,
ambient temp, wind, battery charge), with two scoring modes chosen per
signal: a "latch" mode for steady signals (fuel burn, battery) that stays
alerted for the full duration of a sustained event instead of fading as its
own rolling window absorbs it, and a "plain" mode for signals with their
own daily trend (temperature, power draw) where freezing a baseline would
cause false alarms once the trend legitimately moves on.

Validate it against the generator's own ground-truth `active_anomalies`
column:

```bash
python validate_detector.py data/maitri_demo.csv
```

Current numbers on that dataset: **precision 0.85, recall 1.00, F1 0.92**,
all 3 injected anomalies caught, ~3–4% false-alarm rate on otherwise-quiet
data (see `data/fleet_72h.csv`). Keep this script handy — rerun it any time
you tune `window` / `threshold` / `min_periods`.

Exposed via the API:

```
GET /anomalies/latest                -> current flags, all stations
GET /anomalies/latest?station=maitri -> current flags, one station
```

Needs ~4 hours of history before it can say anything (`ready: false` until
then) — this is a real constraint, not a bug: there's no baseline to compare
against on a station that just started reporting.
