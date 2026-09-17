"""
Validates the z-score detector against the generator's own ground-truth
`active_anomalies` column (only possible because we control the simulator --
a real deployment wouldn't have this). Run this whenever you tune the
window/threshold, and keep the printed numbers for your pitch deck --
"tested against N labeled events, X% caught" is a much stronger claim than
"trust me it works".

Scope note: comms_blackout isn't a numeric signal, so it's intentionally
NOT something this detector catches -- the dashboard already surfaces that
directly via `comms_status`. This script excludes blackout-only rows from
scoring so the reported numbers reflect what the detector is actually meant
to catch (fuel_leak, power_spike, heater_failure, storm).

Usage:
    python validate_detector.py data/maitri_demo.csv
    python validate_detector.py data/maitri_demo.csv --window 24 --threshold 2.5
"""

from __future__ import annotations

import argparse

import pandas as pd

from detector import DEFAULT_MIN_PERIODS, DEFAULT_THRESHOLD, DEFAULT_WINDOW, detect_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the anomaly detector against ground truth.")
    parser.add_argument("csv_path")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument("--min-periods", type=int, default=DEFAULT_MIN_PERIODS)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    df = pd.read_csv(args.csv_path, parse_dates=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    scored = detect_all(df, window=args.window, min_periods=args.min_periods, threshold=args.threshold)

    # Ground truth: a row counts as a "should detect" positive only if a
    # NUMERIC-signal anomaly is active (exclude comms_blackout -- out of scope,
    # see module docstring).
    numeric_kinds = {"fuel_leak", "power_spike", "heater_failure", "storm"}

    def truth_label(active: str) -> bool:
        kinds = set(active.split(",")) if active and active != "none" else set()
        return bool(kinds & numeric_kinds)

    scored["ground_truth"] = df["active_anomalies"].apply(truth_label)

    tp = int(((scored["is_anomaly"]) & (scored["ground_truth"])).sum())
    fp = int(((scored["is_anomaly"]) & (~scored["ground_truth"])).sum())
    fn = int(((~scored["is_anomaly"]) & (scored["ground_truth"])).sum())
    tn = int(((~scored["is_anomaly"]) & (~scored["ground_truth"])).sum())

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")

    print(f"Rows scored: {len(scored)} (window={args.window}, threshold={args.threshold})")
    print(f"Ground-truth anomalous rows (numeric kinds only): {int(scored['ground_truth'].sum())}")
    print()
    print(f"True positives:  {tp}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"True negatives:  {tn}")
    print()
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1:        {f1:.2f}")

    print()
    print("Per-event-window breakdown (did we catch each injected event at all?):")
    scored["_kinds"] = df["active_anomalies"]
    event_id = (scored["_kinds"] != scored["_kinds"].shift()).cumsum()
    for _, group in scored.groupby(event_id):
        kinds = group["_kinds"].iloc[0]
        if kinds == "none":
            continue
        caught = bool(group["is_anomaly"].any())
        start, end = group["timestamp"].iloc[0], group["timestamp"].iloc[-1]
        mark = "CAUGHT" if caught else "missed"
        print(f"  [{mark}] {kinds:20s} {start} -> {end} ({len(group)} rows)")


if __name__ == "__main__":
    main()