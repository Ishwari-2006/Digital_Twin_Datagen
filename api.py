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
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db.db import fetch_history, fetch_latest, fetch_stations
from station_config import STATIONS

app = FastAPI(title="Digital Twin API", version="0.1.0")

# Wide open for hackathon dev convenience -- tighten before anything real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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