"""
Command-line entry point for batch-generating synthetic Digital Twin data.

Examples
--------
# 72 hours of both stations at 5-minute resolution -> data/fleet_72h.csv
python cli.py --station both --hours 72 --interval 5 --out data/fleet_72h.csv

# Maitri only, force a fuel leak at hour 10 and a comms blackout at hour 20,
# for a demo dataset with guaranteed, well-timed events.
python cli.py --station maitri --hours 24 --out data/maitri_demo.csv \
    --anomaly 10:fuel_leak --anomaly 20:comms_blackout

# JSON instead of CSV
python cli.py --station bharati --hours 48 --out data/bharati.json --format json
"""

from __future__ import annotations

import argparse
import os

from generator import ANOMALY_TYPES, generate_batch, generate_fleet_batch
from station_config import STATIONS


def parse_anomaly_arg(spec: str) -> tuple[float, str]:
    try:
        hour_str, kind = spec.split(":", 1)
        hour = float(hour_str)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Anomaly spec must be HOUR:KIND (e.g. 10:fuel_leak), got '{spec}'"
        ) from e
    if kind not in ANOMALY_TYPES:
        raise argparse.ArgumentTypeError(f"Unknown anomaly kind '{kind}'. Options: {ANOMALY_TYPES}")
    return hour, kind


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Digital Twin sensor data.")
    parser.add_argument("--station", choices=[*STATIONS.keys(), "both"], default="both")
    parser.add_argument("--start", default="2026-01-01T00:00:00", help="ISO start timestamp")
    parser.add_argument("--hours", type=float, default=72.0)
    parser.add_argument("--interval", type=float, default=5.0, help="Sample interval in minutes")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default="data/output.csv")
    parser.add_argument("--format", choices=["csv", "json"], default=None,
                         help="Defaults to the --out file extension")
    parser.add_argument(
        "--anomaly", action="append", default=[], type=parse_anomaly_arg,
        help="HOUR:KIND, repeatable. Only applies when --station is a single station.",
    )
    args = parser.parse_args()

    fmt = args.format or ("json" if args.out.lower().endswith(".json") else "csv")

    if args.station == "both":
        if args.anomaly:
            parser.error("--anomaly requires a single --station, not 'both'")
        df = generate_fleet_batch(args.start, args.hours, args.interval, rng_seed=args.seed)
    else:
        df = generate_batch(
            args.station, args.start, args.hours, args.interval,
            rng_seed=args.seed, scripted_anomalies=args.anomaly,
        )

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if fmt == "csv":
        df.to_csv(args.out, index=False)
    else:
        df.to_json(args.out, orient="records", indent=2)

    print(f"Wrote {len(df)} rows x {len(df.columns)} cols -> {args.out}")
    print(f"Stations: {sorted(df['station_id'].unique())}")
    print(f"Time range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    anomaly_rows = df[df["active_anomalies"] != "none"]
    print(f"Rows with an active anomaly: {len(anomaly_rows)} ({100*len(anomaly_rows)/len(df):.1f}%)")


if __name__ == "__main__":
    main()