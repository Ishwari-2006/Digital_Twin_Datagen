-- Digital Twin telemetry schema.
--
-- Plain Postgres table by default. If you have the TimescaleDB extension
-- available (your own machine, or most managed Postgres/Timescale Cloud
-- providers), run the two commented lines at the bottom to turn this into a
-- hypertable -- everything else (queries, inserts, the API) works unchanged
-- either way, since a hypertable is just a regular table underneath.

CREATE TABLE IF NOT EXISTS telemetry (
    id                              BIGSERIAL PRIMARY KEY,
    station_id                      TEXT NOT NULL,
    ts                              TIMESTAMPTZ NOT NULL,
    received_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),

    ambient_temp_c                  DOUBLE PRECISION,
    wind_speed_ms                   DOUBLE PRECISION,
    weather_anomaly_flag            BOOLEAN,
    comms_status                    TEXT,

    power_draw_kw                   DOUBLE PRECISION,
    generator_load_pct              DOUBLE PRECISION,
    battery_soc_pct                 DOUBLE PRECISION,
    battery_state                   TEXT,

    fuel_tank_level_l               DOUBLE PRECISION,
    fuel_tank_pct                   DOUBLE PRECISION,
    fuel_burn_rate_lph              DOUBLE PRECISION,
    fuel_burn_rate_lph_avg24h       DOUBLE PRECISION,
    days_of_autonomy                DOUBLE PRECISION,

    hvac_status                     TEXT,
    heater_status                   TEXT,

    resupply_window_days_remaining  INTEGER,
    resupply_recommendation         TEXT,

    active_anomalies                TEXT,
    delivered_live                  BOOLEAN,

    UNIQUE (station_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_station_ts ON telemetry (station_id, ts DESC);

-- --- Optional: only if TimescaleDB extension is installed on this Postgres ---
-- CREATE EXTENSION IF NOT EXISTS timescaledb;
-- SELECT create_hypertable('telemetry', 'ts', if_not_exists => TRUE, migrate_data => TRUE);