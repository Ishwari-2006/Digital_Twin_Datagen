"""
Anomaly detector (Section 3.4) — rolling z-score over recent history, per
station, per signal. Deliberately not a black box: it flags "this specific
reading is unusual for this station recently" per signal, rather than
guessing a root-cause category (fuel leak vs. power spike vs. storm). That's
an honest scope for a hackathon detector, and it's easy to defend in a Q&A:
"we flag abnormal readings; we don't diagnose cause."

Method: for each signal, maintain a rolling baseline (mean/std over recent
history) built ONLY from points that were NOT themselves flagged anomalous.
Flag the current reading if it's more than `threshold` standard deviations
from that clean baseline.

Why "clean baseline" instead of a plain rolling window over everything: a
plain rolling window has two blind spots on a *sustained* anomaly (a fuel
leak lasting hours, not one bad tick) --
  1. it gradually absorbs the anomalous readings into "recent normal", so
     the z-score decays back under threshold while the problem is still
     happening, and
  2. once that happens, the moment things return to ACTUALLY normal, that
     return looks like a big deviation relative to the now-contaminated
     window, firing a second false alarm.
Excluding flagged points from the baseline avoids both: the baseline never
learns to treat the anomaly as normal, so it doesn't fade during the event
and doesn't false-fire on recovery either.

A `severity` (warn / critical) is derived from how far past the threshold
the z-score is — not a second independent method — so this stays simple by
design (Section 3.5: "don't over-build the ML").

An optional IsolationForest path is included for the stretch goal ("smarter"
version, same interface) but is NOT the default -- z-score is what the API
uses unless asked otherwise.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Signal -> human label. Only signals in this dict are monitored.
SIGNAL_LABELS = {
    "power_draw_kw": "Power draw",
    "fuel_burn_rate_lph": "Fuel burn rate",
    "ambient_temp_c": "Ambient temperature",
    "wind_speed_ms": "Wind speed",
    "battery_soc_pct": "Battery charge",
}

DEFAULT_WINDOW = 36          # how many CLEAN (non-flagged) points to keep as baseline
DEFAULT_MIN_PERIODS = 12     # don't flag anything until we have some baseline
DEFAULT_THRESHOLD = 3.0      # |z| beyond this = flagged
DEFAULT_RECOVERY_RATIO = 0.6 # once flagged, needs |z vs freeze-point baseline| under threshold*this to clear
CRITICAL_MULTIPLIER = 1.5    # |z| beyond threshold * this = "critical" not "warn"

# Floor on baseline std per signal -- without this, a signal that's briefly
# almost perfectly flat gets a near-zero std, and then completely normal
# small wiggles produce enormous, meaningless z-scores. Set from the
# generator's own noise parameters (station_config.py) -- roughly "don't
# call it anomalous if it's within the noise band the simulator itself
# injects".
MIN_STD = {
    "power_draw_kw": 1.0,
    "fuel_burn_rate_lph": 1.4,
    "ambient_temp_c": 0.4,
    "wind_speed_ms": 0.5,
    "battery_soc_pct": 0.6,
}

# Two scoring strategies, chosen per signal:
#   "latch"  -- clean-baseline + freeze/persist (see module docstring). Right
#               for signals that are flat/steady under normal operation, so a
#               frozen reference point stays valid for as long as an event lasts.
#   "plain"  -- ordinary rolling z-score against the last `window` raw points,
#               no freezing. Right for signals with their own legitimate
#               trend (temperature and power draw both cycle over the day) --
#               freezing a baseline against a moving target causes false
#               "still anomalous" alerts once the trend moves on for
#               unrelated, normal reasons. Short-lived anomalies (a brief
#               power spike) still show up clearly against a plain window;
#               it just won't stay latched for hours the way "latch" does.
SIGNAL_MODE = {
    "power_draw_kw": "plain",
    "fuel_burn_rate_lph": "latch",
    "ambient_temp_c": "plain",
    "wind_speed_ms": "plain",
    "battery_soc_pct": "latch",
}


@dataclass
class AnomalyFlag:
    signal: str
    label: str
    value: float
    z_score: float
    severity: str  # "warn" | "critical"


def _score_latched(
    values: pd.Series,
    window: int,
    min_periods: int,
    threshold: float,
    min_std: float,
    recovery_ratio: float,
) -> tuple[pd.Series, pd.Series]:
    """Clean-baseline + freeze/persist. See module docstring."""
    clean: deque[float] = deque(maxlen=window)
    z_out: list[float] = []
    flag_out: list[bool] = []

    active = False
    frozen_mean = frozen_std = None

    for v in values:
        if pd.isna(v):
            z_out.append(np.nan)
            flag_out.append(active)
            continue

        if len(clean) >= min_periods:
            arr = np.array(clean)
            mean = float(arr.mean())
            std = max(float(arr.std(ddof=0)), min_std)
            z = (v - mean) / std
        else:
            z = np.nan

        if not active:
            if pd.notna(z) and abs(z) >= threshold:
                active = True
                frozen_mean, frozen_std = mean, std
        else:
            frozen_z = (v - frozen_mean) / frozen_std
            if abs(frozen_z) < threshold * recovery_ratio:
                active = False

        z_out.append(z)
        flag_out.append(active)

        if not active:
            clean.append(v)  # only clean points feed the baseline -- an
            # anomalous stretch (or its immediate recovery) never pollutes
            # what "normal" means going forward.

    return (
        pd.Series(z_out, index=values.index),
        pd.Series(flag_out, index=values.index),
    )


def _score_plain(
    values: pd.Series,
    window: int,
    min_periods: int,
    threshold: float,
    min_std: float,
) -> tuple[pd.Series, pd.Series]:
    """Ordinary rolling z-score against the prior `window` raw points (no
    freezing). Right for signals with their own legitimate trend -- see
    SIGNAL_MODE above."""
    prior = values.shift(1)
    roll_mean = prior.rolling(window, min_periods=min_periods).mean()
    roll_std = prior.rolling(window, min_periods=min_periods).std(ddof=0).clip(lower=min_std)
    z = (values - roll_mean) / roll_std.replace(0, np.nan)
    flag = z.abs() >= threshold
    return z, flag.fillna(False)


def score_history(
    df: pd.DataFrame,
    signals: Optional[list[str]] = None,
    window: int = DEFAULT_WINDOW,
    min_periods: int = DEFAULT_MIN_PERIODS,
    threshold: float = DEFAULT_THRESHOLD,
    recovery_ratio: float = DEFAULT_RECOVERY_RATIO,
) -> pd.DataFrame:
    """Return a copy of df with `<signal>_z` and `<signal>_flag` columns
    for each monitored signal. `df` must be sorted ascending by time."""
    signals = signals or list(SIGNAL_LABELS.keys())
    out = df.copy()
    for sig in signals:
        if sig not in out.columns:
            continue
        values = out[sig].astype(float)
        min_std = MIN_STD.get(sig, 0.0)
        if SIGNAL_MODE.get(sig, "plain") == "latch":
            z, flag = _score_latched(values, window, min_periods, threshold, min_std, recovery_ratio)
        else:
            z, flag = _score_plain(values, window, min_periods, threshold, min_std)
        out[f"{sig}_z"] = z
        out[f"{sig}_flag"] = flag
    return out


def detect_current(
    history_df: pd.DataFrame,
    signals: Optional[list[str]] = None,
    window: int = DEFAULT_WINDOW,
    min_periods: int = DEFAULT_MIN_PERIODS,
    threshold: float = DEFAULT_THRESHOLD,
    recovery_ratio: float = DEFAULT_RECOVERY_RATIO,
) -> list[AnomalyFlag]:
    """
    Score a station's history (ascending by time) and return flags for the
    LAST row only -- i.e. "is the most recent reading anomalous". This is
    what the live API calls.
    """
    if history_df is None or len(history_df) < min_periods + 1:
        return []

    signals = signals or list(SIGNAL_LABELS.keys())
    scored = score_history(history_df, signals, window, min_periods, threshold, recovery_ratio)
    last = scored.iloc[-1]

    flags = []
    for sig in signals:
        z_col, flag_col = f"{sig}_z", f"{sig}_flag"
        if z_col not in scored.columns or not last.get(flag_col, False):
            continue
        z = last[z_col]
        if pd.isna(z):
            continue
        severity = "critical" if abs(z) >= threshold * CRITICAL_MULTIPLIER else "warn"
        flags.append(AnomalyFlag(
            signal=sig,
            label=SIGNAL_LABELS.get(sig, sig),
            value=float(last[sig]),
            z_score=round(float(z), 2),
            severity=severity,
        ))
    # Worst first.
    flags.sort(key=lambda f: -abs(f.z_score))
    return flags


def detect_all(
    df: pd.DataFrame,
    signals: Optional[list[str]] = None,
    window: int = DEFAULT_WINDOW,
    min_periods: int = DEFAULT_MIN_PERIODS,
    threshold: float = DEFAULT_THRESHOLD,
    recovery_ratio: float = DEFAULT_RECOVERY_RATIO,
) -> pd.DataFrame:
    """
    Score every row in df (not just the last one) -- used for offline
    validation against the generator's ground-truth `active_anomalies`
    column. Adds an `is_anomaly` bool column (True if ANY monitored signal
    is flagged on that row) plus the per-signal z/flag columns.
    """
    signals = signals or list(SIGNAL_LABELS.keys())
    scored = score_history(df, signals, window, min_periods, threshold, recovery_ratio)
    flag_cols = [f"{s}_flag" for s in signals if f"{s}_flag" in scored.columns]
    scored["is_anomaly"] = scored[flag_cols].any(axis=1)
    return scored


# --------------------------------------------------------------------------- #
# Optional stretch: IsolationForest, same interface as detect_current.
# Not used by default -- opt in explicitly.
# --------------------------------------------------------------------------- #

def detect_current_isolation_forest(
    history_df: pd.DataFrame,
    signals: Optional[list[str]] = None,
    contamination: float = 0.05,
) -> list[AnomalyFlag]:
    from sklearn.ensemble import IsolationForest  # imported lazily -- optional dependency

    signals = signals or list(SIGNAL_LABELS.keys())
    signals = [s for s in signals if s in history_df.columns]
    if history_df is None or len(history_df) < 20 or not signals:
        return []

    X = history_df[signals].astype(float).fillna(method="ffill").fillna(method="bfill")
    model = IsolationForest(contamination=contamination, random_state=0)
    model.fit(X.iloc[:-1])  # fit on history excluding the current point
    last_row = X.iloc[[-1]]
    pred = model.predict(last_row)[0]  # -1 = anomaly, 1 = normal
    if pred != -1:
        return []

    score = -model.score_samples(last_row)[0]  # higher = more anomalous
    # Report against whichever monitored signal deviates most from the recent mean,
    # just for a human-readable label -- IsolationForest itself is multivariate.
    means = X.iloc[:-1].mean()
    stds = X.iloc[:-1].std().replace(0, np.nan)
    per_signal_z = ((last_row.iloc[0] - means) / stds).abs()
    worst_signal = per_signal_z.idxmax() if not per_signal_z.isna().all() else signals[0]

    return [AnomalyFlag(
        signal=worst_signal,
        label=SIGNAL_LABELS.get(worst_signal, worst_signal),
        value=float(last_row.iloc[0][worst_signal]),
        z_score=round(float(score), 2),
        severity="critical" if score > 0.6 else "warn",
    )]