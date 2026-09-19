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

-- --------------------------------------------------------------------------
-- Remote Management Action Layer
-- --------------------------------------------------------------------------

-- New fields StationSimulator.apply_command() adds to every record (see
-- generator.py). ADD COLUMN IF NOT EXISTS keeps this file idempotent even
-- if the `telemetry` table already exists from an earlier run.
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS active_generator   TEXT;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS heater_setpoint_c  DOUBLE PRECISION;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS resupply_requested BOOLEAN;

-- Audit log for operator commands issued via
-- POST /stations/{station_id}/commands (api.py).
CREATE TABLE IF NOT EXISTS commands (
    id            BIGSERIAL PRIMARY KEY,
    station_id    TEXT NOT NULL,
    command_type  TEXT NOT NULL,
    payload       JSONB NOT NULL,
    issued_by     TEXT NOT NULL DEFAULT 'operator',
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'applied', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_commands_station_ts ON commands (station_id, ts DESC);