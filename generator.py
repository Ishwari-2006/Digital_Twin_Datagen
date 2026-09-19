"""
Digital Twin synthetic data generator for Maitri & Bharati (SIH2026).

Stands in for the "Physical layer" of the four-layer architecture (Section 3.1
of the team reference doc) until real IoT hardware exists. Every record is
tagged with station_id from the very first row (Section 3.2) so the two-station
scope never has to be retrofitted.

Model per domain, per station:
  - Environmental: seasonal sinusoid (annual + diurnal) + random-walk noise,
    station-specific climate anchors from station_config.py.
  - Energy: diurnal load cycle + noise; generator load derived from total load;
    battery SoC integrates (generation - load) over time.
  - Infrastructure: fuel tank level drains with generator fuel burn; HVAC/heater
    on/off state derived from ambient temperature; battery "state" label.
  - Logistics: fuel burn rate (rolling), days-of-autonomy estimate, resupply
    window countdown and a simple recommendation.
  - Cross-cutting: comms/connectivity state (online / degraded / blackout) with
    store-and-forward queuing while offline (Section 3.3).

Anomalies (fuel leak, power spike, heater failure, comms blackout, storm) can be
triggered manually (for the live demo) or left to fire at a low random rate so a
long batch run looks organically messy rather than suspiciously clean.

Usage:
    from generator import StationSimulator
    sim = StationSimulator("maitri")
    record = sim.step(timestamp)   # -> dict, one row

    from generator import generate_batch
    df = generate_batch("maitri", start="2026-01-01", hours=72, interval_minutes=5)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from station_config import STATIONS, StationConfig


# --------------------------------------------------------------------------- #
# Anomaly definitions
# --------------------------------------------------------------------------- #

ANOMALY_TYPES = (
    "fuel_leak",
    "power_spike",
    "heater_failure",
    "comms_blackout",
    "storm",
)

# Base hourly probability an anomaly of each type spontaneously starts,
# if none of that type is currently active. Kept low -- these are rare events,
# not a constant carnival. Tune freely for demo pacing.
_SPONTANEOUS_HOURLY_PROB = {
    "fuel_leak": 0.0015,
    "power_spike": 0.003,
    "heater_failure": 0.002,
    "comms_blackout": 0.004,
    "storm": None,  # storms use the per-station climate.storm_prob_per_hour instead
}

# How long an anomaly lasts once triggered (minutes), sampled uniformly in range.
_ANOMALY_DURATION_MIN = {
    "fuel_leak": (120, 360),
    "power_spike": (5, 20),
    "heater_failure": (60, 240),
    "comms_blackout": (30, 180),
    "storm": (180, 720),
}


@dataclass
class ActiveAnomaly:
    kind: str
    started_at: datetime
    ends_at: datetime
    magnitude: float = 1.0  # severity multiplier, randomised per-instance


# --------------------------------------------------------------------------- #
# Simulator
# --------------------------------------------------------------------------- #

class StationSimulator:
    """
    Stateful, tick-by-tick simulator for one station. Call .step(timestamp) in
    increasing time order to get one record at a time -- this is what a
    real-time publisher (MQTT/WebSocket loop) would call on a timer, and it's
    also what generate_batch() calls in a loop for offline CSV generation.
    """

    def __init__(self, station_key: str, rng_seed: Optional[int] = None):
        if station_key not in STATIONS:
            raise ValueError(f"Unknown station '{station_key}'. Options: {list(STATIONS)}")
        self.cfg: StationConfig = STATIONS[station_key]

        # Seed deterministically (reproducible runs) but always salted by
        # station_key, so passing the same --seed to both stations still gives
        # each an independent noise stream instead of identical, correlated
        # output (station_key's own hash covers the case where rng_seed is None).
        base = rng_seed if rng_seed is not None else 0
        salt = int.from_bytes(station_key.encode(), "little") % (2**16)
        seed = (base * 100003 + salt) % (2**32)
        self._rng = np.random.default_rng(seed)
        self._py_rng = random.Random(seed)

        # Rolling state carried between ticks.
        self._last_ambient_c: Optional[float] = None
        self._battery_soc_pct: float = 78.0
        self._fuel_tank_l: float = self.cfg.power.fuel_tank_capacity_l * self.cfg.power.fuel_tank_start_frac
        self._fuel_burn_history: list[float] = []  # recent L/hr samples, for a rolling average
        self._comms_queue: list[dict] = []          # buffered records while blacked out
        self._last_step_time: Optional[datetime] = None

        self._active: dict[str, ActiveAnomaly] = {}  # kind -> ActiveAnomaly

        self._days_since_resupply = 0

        # Remote Management Action Layer: operator-controllable state.
        # Defaults reproduce this simulator's original hardcoded behavior
        # exactly (5.0C heater threshold, full generator bank, no manual
        # resupply flag) -- nothing changes until apply_command() is called.
        self._active_generator: str = "primary"   # "primary" | "backup"
        self._heater_setpoint_c: float = 5.0
        self._resupply_requested: bool = False

    # ------------------------------------------------------------------- #
    # Public controls (used by the "simulate event" / "simulate blackout" demo
    # triggers described in Section 3.3 and 5.1 of the reference doc).
    # ------------------------------------------------------------------- #

    def trigger_anomaly(self, kind: str, at: datetime, duration_minutes: Optional[int] = None,
                         magnitude: Optional[float] = None) -> None:
        if kind not in ANOMALY_TYPES:
            raise ValueError(f"Unknown anomaly kind '{kind}'. Options: {ANOMALY_TYPES}")
        lo, hi = _ANOMALY_DURATION_MIN[kind]
        dur = duration_minutes if duration_minutes is not None else self._py_rng.randint(lo, hi)
        mag = magnitude if magnitude is not None else self._py_rng.uniform(0.8, 1.6)
        self._active[kind] = ActiveAnomaly(
            kind=kind, started_at=at, ends_at=at + timedelta(minutes=dur), magnitude=mag
        )

    def clear_anomaly(self, kind: str) -> None:
        self._active.pop(kind, None)

    def is_blacked_out(self) -> bool:
        return "comms_blackout" in self._active

    def apply_command(self, cmd: dict) -> dict:
        """
        Apply one operator command from the Remote Management Action Layer
        (POST /stations/{station_id}/commands -> MQTT station/<id>/command ->
        mqtt_publisher.py's command listener -> here). Mutates internal state;
        the effect is reflected starting with the very next step() call.

        Returns {"applied": bool, "detail": str}, used both for the console
        log line in mqtt_publisher.py and to flip the command's audit-log
        status ("applied" vs "failed") back in Postgres.
        """
        command = cmd.get("command")

        if command == "switch_generator":
            target = cmd.get("target", "backup")
            if target not in ("primary", "backup"):
                return {"applied": False, "detail": f"unknown generator target '{target}'"}
            self._active_generator = target
            return {"applied": True, "detail": f"active generator -> {target}"}

        if command == "force_resupply_request":
            self._resupply_requested = True
            return {"applied": True, "detail": "resupply_requested -> True"}

        if command == "adjust_heater_setpoint":
            value = cmd.get("value")
            if value is None:
                return {"applied": False, "detail": "missing 'value'"}
            self._heater_setpoint_c = float(value)
            return {"applied": True, "detail": f"heater_setpoint_c -> {value}"}

        if command == "acknowledge_anomaly":
            # anomaly_id is one of ANOMALY_TYPES (e.g. "fuel_leak"), matching
            # the keys of self._active -- the same ground-truth kind shown in
            # the record's active_anomalies field. Reuses clear_anomaly() so
            # there's exactly one code path that removes an active anomaly.
            kind = cmd.get("anomaly_id")
            was_active = kind in self._active
            self.clear_anomaly(kind)
            return {
                "applied": was_active,
                "detail": f"cleared '{kind}'" if was_active else f"'{kind}' was not active",
            }

        return {"applied": False, "detail": f"unknown command '{command}'"}

    # ------------------------------------------------------------------- #
    # Internals
    # ------------------------------------------------------------------- #

    def _expire_anomalies(self, now: datetime) -> None:
        expired = [k for k, a in self._active.items() if now >= a.ends_at]
        for k in expired:
            del self._active[k]

    def _maybe_spawn_anomalies(self, now: datetime, dt_hours: float) -> None:
        # Storms use the station's own climate-driven probability.
        if "storm" not in self._active:
            p = 1 - (1 - self.cfg.climate.storm_prob_per_hour) ** dt_hours
            if self._py_rng.random() < p:
                self.trigger_anomaly("storm", now)

        for kind, hourly_p in _SPONTANEOUS_HOURLY_PROB.items():
            if kind == "storm" or hourly_p is None:
                continue
            if kind in self._active:
                continue
            p = 1 - (1 - hourly_p) ** dt_hours
            if self._py_rng.random() < p:
                self.trigger_anomaly(kind, now)

    def _environmental(self, now: datetime) -> dict:
        c = self.cfg.climate
        doy = now.timetuple().tm_yday
        hour = now.hour + now.minute / 60.0

        seasonal = c.annual_mean_c + c.seasonal_amplitude_c * math.cos(
            2 * math.pi * (doy - c.peak_warmth_doy) / 365.0
        )
        diurnal = c.diurnal_amplitude_c * math.cos(2 * math.pi * (hour - 15) / 24.0)

        if self._last_ambient_c is None:
            walk = 0.0
        else:
            # mean-reverting random walk around the seasonal+diurnal baseline
            target = seasonal + diurnal
            walk = (self._last_ambient_c - target) * 0.6 + self._rng.normal(0, c.noise_std_c)

        storm = self._active.get("storm")
        storm_temp_drop = 0.0
        wind = self._rng.normal(c.wind_mean_ms, c.wind_std_ms)
        if storm:
            storm_temp_drop = -4.0 * storm.magnitude
            wind += 12.0 * storm.magnitude

        ambient_c = seasonal + diurnal + walk + storm_temp_drop
        self._last_ambient_c = ambient_c
        wind = max(0.0, wind)

        return {
            "ambient_temp_c": round(ambient_c, 2),
            "wind_speed_ms": round(wind, 2),
            "weather_anomaly_flag": bool(storm),
        }

    def _comms(self, now: datetime) -> dict:
        if "comms_blackout" in self._active:
            status = "blackout"
        elif self._active.get("storm") is not None:
            status = "degraded"
        else:
            status = "online"
        return {"comms_status": status}

    def _power_and_infra(self, now: datetime, env: dict) -> dict:
        p = self.cfg.power
        hour = now.hour + now.minute / 60.0

        load_kw = (
            p.base_load_kw
            + p.load_diurnal_amplitude_kw * math.cos(2 * math.pi * (hour - 12) / 24.0)
            + self._rng.normal(0, p.load_noise_std_kw)
        )

        # Colder outside -> heaters work harder -> higher load.
        cold_penalty = max(0.0, -env["ambient_temp_c"]) * 0.15
        load_kw += cold_penalty

        heater_status = "on" if env["ambient_temp_c"] < self._heater_setpoint_c else "standby"
        hvac_status = "on"

        spike = self._active.get("power_spike")
        if spike:
            load_kw *= 1.0 + 0.9 * spike.magnitude

        heater_fail = self._active.get("heater_failure")
        if heater_fail:
            heater_status = "fault"
            # ambient inside effect isn't modeled directly here, but load drops
            # because the failed heater draws no power while broken.
            load_kw *= max(0.4, 1.0 - 0.3 * heater_fail.magnitude)

        load_kw = max(5.0, load_kw)
        if self._active_generator == "backup":
            # Running on the single backup unit instead of the full bank --
            # switch_generator's visible effect: generator_load_pct jumps.
            generator_capacity_kw = p.generator_rated_kw
        else:
            generator_capacity_kw = p.n_generators * p.generator_rated_kw
        generator_load_pct = min(100.0, 100.0 * load_kw / generator_capacity_kw)

        # Battery bank acts as a short-term load buffer, not primary storage --
        # diesel gensets carry the base load directly. SoC mean-reverts to a
        # ~85% set point with gentle noise, and gets drawn down when the
        # generators are heavily loaded (a spike, or too few gensets online).
        dt_hours_soc = self._dt_hours(now) or (5.0 / 60.0)
        soc_target = 85.0
        reversion = (soc_target - self._battery_soc_pct) * 0.15 * dt_hours_soc
        overload_drain = max(0.0, generator_load_pct - 85.0) * 0.08 * dt_hours_soc
        soc_noise = self._rng.normal(0, 0.15)
        soc_delta = reversion - overload_drain + soc_noise
        self._battery_soc_pct = float(np.clip(self._battery_soc_pct + soc_delta, 5.0, 100.0))
        battery_state = "charging" if soc_delta > 0.05 else ("discharging" if soc_delta < -0.05 else "idle")

        # Fuel burn: generator specific fuel consumption * kWh produced this tick.
        dt_hours = self._dt_hours(now)
        fuel_burn_lph = load_kw * p.specific_fuel_consumption_l_per_kwh

        leak = self._active.get("fuel_leak")
        if leak:
            fuel_burn_lph *= 1.0 + 2.5 * leak.magnitude

        fuel_used_l = fuel_burn_lph * dt_hours
        self._fuel_tank_l = max(0.0, self._fuel_tank_l - fuel_used_l)

        self._fuel_burn_history.append(fuel_burn_lph)
        if len(self._fuel_burn_history) > 24 * 12:  # ~24h at 5-min ticks; harmless at other intervals
            self._fuel_burn_history.pop(0)
        avg_burn_lph = float(np.mean(self._fuel_burn_history)) if self._fuel_burn_history else fuel_burn_lph

        fuel_tank_pct = 100.0 * self._fuel_tank_l / p.fuel_tank_capacity_l
        days_of_autonomy = (
            self._fuel_tank_l / (avg_burn_lph * 24.0) if avg_burn_lph > 1e-6 else float("inf")
        )

        return {
            "power_draw_kw": round(load_kw, 2),
            "generator_load_pct": round(generator_load_pct, 1),
            "battery_soc_pct": round(self._battery_soc_pct, 1),
            "battery_state": battery_state,
            "fuel_tank_level_l": round(self._fuel_tank_l, 1),
            "fuel_tank_pct": round(fuel_tank_pct, 2),
            "fuel_burn_rate_lph": round(fuel_burn_lph, 2),
            "fuel_burn_rate_lph_avg24h": round(avg_burn_lph, 2),
            "days_of_autonomy": round(min(days_of_autonomy, 999.0), 1),
            "hvac_status": hvac_status,
            "heater_status": heater_status,
            "active_generator": self._active_generator,
            "heater_setpoint_c": round(self._heater_setpoint_c, 1),
        }

    def _logistics(self, now: datetime, infra: dict, env: dict) -> dict:
        cfg = self.cfg
        doy = now.timetuple().tm_yday
        days_to_window = (cfg.resupply_window_open_doy - doy) % 365

        # Simple recommendation: flag early if autonomy is short relative to
        # how far away the next resupply window is, or weather is currently bad.
        risk = infra["days_of_autonomy"] < (days_to_window + 20)
        weather_ok = env["wind_speed_ms"] < 20.0 and not env["weather_anomaly_flag"]

        if infra["days_of_autonomy"] < 15:
            recommendation = "URGENT: request emergency resupply / airlift fuel"
        elif risk:
            recommendation = "Advance resupply timing within current window"
        elif weather_ok:
            recommendation = "On track — no action needed"
        else:
            recommendation = "Weather unfavorable — monitor before scheduling"

        # force_resupply_request's visible effect: flagged on every record
        # until an operator/ops process clears it, and folded into the
        # recommendation text unless it's already at the URGENT level.
        if self._resupply_requested and not recommendation.startswith("URGENT"):
            recommendation = f"Manual resupply requested by operator — {recommendation}"

        return {
            "resupply_window_days_remaining": int(days_to_window),
            "resupply_recommendation": recommendation,
            "resupply_requested": self._resupply_requested,
        }

    def _dt_hours(self, now: datetime) -> float:
        if self._last_step_time is None:
            dt = 5.0 / 60.0  # assume a 5-minute tick for the very first sample
        else:
            dt = max(0.0, (now - self._last_step_time).total_seconds() / 3600.0)
        return dt

    # ------------------------------------------------------------------- #
    # Main entry point
    # ------------------------------------------------------------------- #

    def step(self, now: datetime) -> dict:
        """Advance the simulation to `now` and return one record (dict)."""
        dt_hours = self._dt_hours(now)
        self._expire_anomalies(now)
        self._maybe_spawn_anomalies(now, dt_hours)

        env = self._environmental(now)
        comms = self._comms(now)
        infra = self._power_and_infra(now, env)
        logi = self._logistics(now, infra, env)

        record = {
            "timestamp": now.isoformat(),
            "station_id": self.cfg.station_id,
            **env,
            **comms,
            **infra,
            **logi,
            "active_anomalies": ",".join(sorted(self._active.keys())) or "none",
        }

        self._last_step_time = now

        # Store-and-forward: while blacked out, queue records instead of
        # "transmitting" them; caller decides what "transmitted" means for
        # their pipeline (e.g. don't publish to MQTT, but do log to disk).
        record["_delivered_live"] = not self.is_blacked_out()
        if not record["_delivered_live"]:
            self._comms_queue.append(record)

        return record

    def drain_queue(self) -> list[dict]:
        """Call after comms recover to retrieve buffered records (Section 3.3)."""
        queued, self._comms_queue = self._comms_queue, []
        return queued


# --------------------------------------------------------------------------- #
# Batch generation helper
# --------------------------------------------------------------------------- #

def generate_batch(
    station_key: str,
    start: str | datetime,
    hours: float,
    interval_minutes: float = 5.0,
    rng_seed: Optional[int] = None,
    scripted_anomalies: Optional[list[tuple[float, str]]] = None,
) -> pd.DataFrame:
    """
    Generate `hours` worth of records at `interval_minutes` cadence for one station.

    scripted_anomalies: optional list of (hour_offset, anomaly_kind) to force-trigger
    at specific points in the run, useful for producing a demo dataset with a
    guaranteed, well-timed anomaly instead of relying on random chance.
    """
    start_dt = pd.Timestamp(start).to_pydatetime()
    sim = StationSimulator(station_key, rng_seed=rng_seed)

    n_steps = int(hours * 60 / interval_minutes)
    scripted = sorted(scripted_anomalies or [])
    scripted_idx = 0

    rows = []
    for i in range(n_steps):
        now = start_dt + timedelta(minutes=i * interval_minutes)
        while scripted_idx < len(scripted) and scripted[scripted_idx][0] * 60 <= i * interval_minutes:
            _, kind = scripted[scripted_idx]
            sim.trigger_anomaly(kind, now)
            scripted_idx += 1
        rows.append(sim.step(now))

    df = pd.DataFrame(rows)
    return df


def generate_fleet_batch(
    start: str | datetime,
    hours: float,
    interval_minutes: float = 5.0,
    rng_seed: Optional[int] = None,
) -> pd.DataFrame:
    """Generate both stations at once and concatenate (station_id column distinguishes them)."""
    frames = [
        generate_batch(key, start, hours, interval_minutes, rng_seed=rng_seed)
        for key in STATIONS
    ]
    return pd.concat(frames, ignore_index=True).sort_values(["timestamp", "station_id"]).reset_index(drop=True)