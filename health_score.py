"""Station-health scoring shared by the API's current and historical views.

The score is intentionally explainable: it starts at 100 and applies one
penalty per operational concern. Fuel and communications receive the heaviest
penalties because they most directly affect a remote Antarctic station's safety
and ability to be managed from afar.
"""

from __future__ import annotations

from typing import Any, Iterable


PENALTIES = {
    "comms": 35,
    "fuel": 30,
    "power": 20,
    "heater": 20,
    "temperature": 10,
    "weather": 10,
    "battery": 10,
    "backfilled": 5,
}

_DIRECT_CONCERNS = {
    "comms_blackout": "comms",
    "fuel_leak": "fuel",
    "power_spike": "power",
    "heater_failure": "heater",
    "storm": "weather",
}

_SIGNAL_CONCERNS = {
    "power_draw_kw": "power",
    "fuel_burn_rate_lph": "fuel",
    "ambient_temp_c": "temperature",
    "wind_speed_ms": "weather",
    "battery_soc_pct": "battery",
}


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _active_kinds(row: Any) -> set[str]:
    value = _value(row, "active_anomalies", "none") or "none"
    return {kind.strip() for kind in str(value).split(",") if kind.strip() and kind.strip() != "none"}


def _flag_value(flag: Any, key: str, default: Any = None) -> Any:
    if isinstance(flag, dict):
        return flag.get(key, default)
    return getattr(flag, key, default)


def _concerns(telemetry_row: Any, anomaly_flags: Iterable[Any] | None = None) -> set[str]:
    concerns = {_DIRECT_CONCERNS[kind] for kind in _active_kinds(telemetry_row) if kind in _DIRECT_CONCERNS}

    if _value(telemetry_row, "comms_status") == "blackout":
        concerns.add("comms")
    if _value(telemetry_row, "heater_status") == "fault":
        concerns.add("heater")
    if _value(telemetry_row, "comms_status") == "degraded":
        concerns.add("weather")
    if _value(telemetry_row, "delivered_live") is False:
        concerns.add("backfilled")

    for flag in anomaly_flags or []:
        concern = _SIGNAL_CONCERNS.get(_flag_value(flag, "signal"))
        if concern:
            concerns.add(concern)
    return concerns


def compute_health_score(telemetry_row: Any, anomaly_flags: Iterable[Any] | None = None) -> float:
    """Return an explainable station-health score in the inclusive range 0–100."""
    score = 100 - sum(PENALTIES[concern] for concern in _concerns(telemetry_row, anomaly_flags))
    return float(max(0, min(100, score)))


def classify_state(telemetry_row: Any, anomaly_flags: Iterable[Any] | None = None) -> str:
    """Classify one telemetry record into the dashboard's mutually exclusive state."""
    active = _active_kinds(telemetry_row)
    if "comms_blackout" in active or _value(telemetry_row, "comms_status") == "blackout":
        return "comms_blackout"
    if _value(telemetry_row, "delivered_live") is False:
        return "backfilled"

    concerns = _concerns(telemetry_row, anomaly_flags)
    critical_kinds = {"fuel_leak", "power_spike", "heater_failure"}
    if active & critical_kinds or any(_flag_value(flag, "severity") == "critical" for flag in anomaly_flags or []):
        return "critical"
    if concerns:
        return "warning"
    return "normal"
