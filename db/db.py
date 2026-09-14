"""
Postgres access layer for the telemetry table. Deliberately raw psycopg2, no
ORM -- a hackathon backend doesn't need one, and it keeps the SQL visible and
easy to explain in a pitch.

Configure via environment variables (see .env.example):
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "digital_twin"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
}

# Fields on a generator record that map 1:1 onto telemetry columns.
# ("_delivered_live" from the generator maps to the "delivered_live" column.)
_COLUMNS = [
    "station_id", "ts",
    "ambient_temp_c", "wind_speed_ms", "weather_anomaly_flag", "comms_status",
    "power_draw_kw", "generator_load_pct", "battery_soc_pct", "battery_state",
    "fuel_tank_level_l", "fuel_tank_pct", "fuel_burn_rate_lph",
    "fuel_burn_rate_lph_avg24h", "days_of_autonomy",
    "hvac_status", "heater_status",
    "resupply_window_days_remaining", "resupply_recommendation",
    "active_anomalies", "delivered_live",
]

_INSERT_SQL = f"""
    INSERT INTO telemetry ({", ".join(_COLUMNS)})
    VALUES ({", ".join(["%s"] * len(_COLUMNS))})
    ON CONFLICT (station_id, ts) DO NOTHING
"""


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_record(record: dict) -> None:
    """Insert one generator record (as produced by StationSimulator.step()).

    `record["timestamp"]` (ISO string) maps to the `ts` column;
    `record["_delivered_live"]` maps to `delivered_live`.
    Unknown/extra keys on `record` are ignored.
    """
    row = {
        "station_id": record["station_id"],
        "ts": record["timestamp"],
        "delivered_live": record.get("_delivered_live", True),
        **{k: record.get(k) for k in _COLUMNS if k not in ("station_id", "ts", "delivered_live")},
    }
    values = [row[c] for c in _COLUMNS]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_INSERT_SQL, values)


def insert_records(records: list[dict]) -> None:
    """Bulk insert -- used for comms-blackout backlog catch-up."""
    if not records:
        return
    rows = []
    for record in records:
        row = {
            "station_id": record["station_id"],
            "ts": record["timestamp"],
            "delivered_live": record.get("_delivered_live", True),
            **{k: record.get(k) for k in _COLUMNS if k not in ("station_id", "ts", "delivered_live")},
        }
        rows.append([row[c] for c in _COLUMNS])
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, _INSERT_SQL, rows)


def fetch_latest(station_id: Optional[str] = None) -> list[dict]:
    """Latest row for one station, or the latest row per station if omitted."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if station_id:
                cur.execute(
                    "SELECT * FROM telemetry WHERE station_id = %s ORDER BY ts DESC LIMIT 1",
                    (station_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT ON (station_id) *
                    FROM telemetry
                    ORDER BY station_id, ts DESC
                    """
                )
            return [dict(r) for r in cur.fetchall()]


def fetch_history(station_id: str, hours: float = 24.0, limit: int = 5000) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM telemetry
                WHERE station_id = %s AND ts >= now() - (%s || ' hours')::interval
                ORDER BY ts ASC
                LIMIT %s
                """,
                (station_id, hours, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def fetch_stations() -> list[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT station_id FROM telemetry ORDER BY station_id")
            return [r[0] for r in cur.fetchall()]