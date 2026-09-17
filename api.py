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

from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db.db import fetch_history, fetch_latest, fetch_stations
from detector import DEFAULT_MIN_PERIODS, DEFAULT_WINDOW, detect_current
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