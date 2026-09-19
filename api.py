"""
Read API over the telemetry table -- what the dashboard (Section 12-24 hrs)
will call. Deliberately thin: a handful of endpoints, no auth, no write
routes (writing happens via the MQTT subscriber, not the API).

Run:
    uvicorn api:app --reload --port 8000

Then:
    GET /health
    GET /stations
    GET /telemetry/latest                -> latest row per station (fleet view)
    GET /telemetry/latest?station=maitri -> latest row for one station
    GET /telemetry/history?station=maitri&hours=24
    GET /anomalies/latest                -> current anomaly flags, all stations
    GET /anomalies/latest?station=maitri -> current anomaly flags, one station
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Optional

import pandas as pd
import paho.mqtt.publish as mqtt_publish
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.db import fetch_commands, fetch_history, fetch_latest, fetch_stations, insert_command
from detector import (
    CRITICAL_MULTIPLIER,
    DEFAULT_MIN_PERIODS,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW,
    SIGNAL_LABELS,
    detect_all,
    detect_current,
)
from health_score import classify_state, compute_health_score
from station_config import STATIONS

app = FastAPI(title="Digital Twin API", version="0.1.0")

# Wide open for hackathon dev convenience -- tighten before anything real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# The detector needs at least (window + min_periods) points of history to
# say anything -- at a 5-minute tick that's a bit over 4 hours. Fetch a
# generous margin (6h) so a slightly irregular publish cadence still gives
# the detector enough to work with.
ANOMALY_HISTORY_HOURS = 6.0

# --------------------------------------------------------------------------- #
# Remote Management Action Layer
# --------------------------------------------------------------------------- #
# mqtt_publisher.py and mqtt_subscriber.py take --broker-host/--broker-port
# CLI flags (default localhost:1883); api.py runs under uvicorn instead, so
# it reads the same defaults from the environment.
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))

# Must match the branches StationSimulator.apply_command() handles in generator.py.
ALLOWED_COMMANDS = {
    "switch_generator",
    "force_resupply_request",
    "adjust_heater_setpoint",
    "acknowledge_anomaly",
}


class CommandIn(BaseModel):
    command: str
    target: Optional[str] = None       # switch_generator: "primary" | "backup"
    value: Optional[float] = None      # adjust_heater_setpoint: new setpoint in °C
    anomaly_id: Optional[str] = None   # acknowledge_anomaly: one of ANOMALY_TYPES, e.g. "fuel_leak"
    issued_by: str = "operator"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stations")
def stations():
    """Configured stations (static) alongside which ones actually have data."""
    with_data = set(fetch_stations())
    return [
        {
            "station_id": key,
            "display_name": cfg.display_name,
            "location": cfg.location,
            "latitude": cfg.latitude,
            "longitude": cfg.longitude,
            "has_data": key in with_data,
        }
        for key, cfg in STATIONS.items()
    ]


@app.get("/telemetry/latest")
def telemetry_latest(station: Optional[str] = Query(default=None)):
    if station and station not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station}'")
    rows = fetch_latest(station)
    if station and not rows:
        raise HTTPException(status_code=404, detail=f"No data yet for '{station}'")
    return rows if station is None else rows[0]


@app.get("/telemetry/history")
def telemetry_history(
    station: str,
    hours: float = Query(default=24.0, gt=0, le=24 * 30),
):
    if station not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station}'")
    return fetch_history(station, hours)


def _anomalies_for(station_id: str) -> dict:
    history = fetch_history(station_id, ANOMALY_HISTORY_HOURS)
    flags = detect_current(pd.DataFrame(history)) if history else []
    return {
        "station_id": station_id,
        "ready": len(history) >= DEFAULT_WINDOW + DEFAULT_MIN_PERIODS,
        "history_points": len(history),
        "anomalies": [
            {"signal": f.signal, "label": f.label, "value": f.value, "z_score": f.z_score, "severity": f.severity}
            for f in flags
        ],
    }


def _flags_for_scored_row(row: pd.Series) -> list[dict]:
    """Convert detector columns on one historical row into health-score flags."""
    flags = []
    for signal in SIGNAL_LABELS:
        flagged = row.get(f"{signal}_flag", False)
        if not (pd.notna(flagged) and bool(flagged)):
            continue
        z_score = row.get(f"{signal}_z")
        severity = (
            "critical"
            if pd.notna(z_score) and abs(float(z_score)) >= DEFAULT_THRESHOLD * CRITICAL_MULTIPLIER
            else "warn"
        )
        flags.append({"signal": signal, "severity": severity})
    return flags


@app.get("/anomalies/latest")
def anomalies_latest(station: Optional[str] = Query(default=None)):
    """Current anomaly flags -- for one station, or all configured stations
    if `station` is omitted. `ready: false` means there isn't enough history
    yet for the detector to say anything (needs ~4h of data)."""
    if station:
        if station not in STATIONS:
            raise HTTPException(status_code=404, detail=f"Unknown station '{station}'")
        return _anomalies_for(station)
    return [_anomalies_for(key) for key in STATIONS]


@app.get("/stations/{station_id}/health/current")
def health_current(station_id: str):
    """Explainable current health score and operational state for one station."""
    if station_id not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station_id}'")
    latest_rows = fetch_latest(station_id)
    if not latest_rows:
        raise HTTPException(status_code=404, detail=f"No data yet for '{station_id}'")

    history = fetch_history(station_id, ANOMALY_HISTORY_HOURS)
    flags = detect_current(pd.DataFrame(history)) if history else []
    latest = latest_rows[0]
    return {
        "station_id": station_id,
        "score": compute_health_score(latest, flags),
        "state": classify_state(latest, flags),
    }


@app.get("/stations/{station_id}/health/breakdown")
def health_breakdown(
    station_id: str,
    hours: float = Query(default=24.0, gt=0, le=24 * 30),
):
    """Hourly counts of classified telemetry states for the requested period."""
    if station_id not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station_id}'")
    history = fetch_history(station_id, hours)
    if not history:
        return []

    df = pd.DataFrame(history)
    if "ts" not in df.columns:
        return []
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    scored = detect_all(df.sort_values("ts").reset_index(drop=True))

    states = ("normal", "warning", "critical", "comms_blackout", "backfilled")
    buckets: dict[str, dict] = defaultdict(lambda: {state: 0 for state in states})
    for _, row in scored.iterrows():
        hour = row["ts"].floor("h").isoformat()
        buckets[hour][classify_state(row, _flags_for_scored_row(row))] += 1

    return [
        {"hour": hour, **buckets[hour]}
        for hour in sorted(buckets)
    ]


@app.post("/stations/{station_id}/commands")
def post_command(station_id: str, cmd: CommandIn):
    """
    Issue an operator command: validated here, logged to the `commands` audit
    table as status='pending', then published to station/<id>/command over
    MQTT. mqtt_publisher.py's command listener applies it to the live
    StationSimulator and flips the audit row to 'applied' or 'failed'.
    """
    if station_id not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station_id}'")
    if cmd.command not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unsupported command '{cmd.command}'")

    payload = cmd.model_dump(exclude_none=True)
    record = insert_command(station_id, cmd.command, payload, cmd.issued_by)

    mqtt_payload = dict(payload)
    mqtt_payload["command_id"] = record["id"]  # lets the publisher report back status

    try:
        mqtt_publish.single(
            f"station/{station_id}/command",
            payload=json.dumps(mqtt_payload),
            hostname=MQTT_BROKER_HOST,
            port=MQTT_BROKER_PORT,
            qos=1,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach MQTT broker: {exc}")

    return record


@app.get("/stations/{station_id}/commands")
def get_commands(station_id: str, limit: int = Query(default=50, gt=0, le=200)):
    """Recent command history for a station -- the dashboard's audit log."""
    if station_id not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Unknown station '{station_id}'")
    return fetch_commands(station_id, limit=limit)
