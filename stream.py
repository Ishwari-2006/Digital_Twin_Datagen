"""
Real-time-ish streaming mode: prints one JSON record per line, at a wall-clock
pace (optionally sped up), for both stations. This is the seam where the
Data layer (Section 3.1 -- MQTT/Mosquitto or a plain WebSocket) plugs in:
pipe this into `mosquitto_pub -t station/<id>/telemetry -l` per line, or adapt
`emit()` below to publish directly instead of printing.

Examples
--------
# Real-time pace, one line every 5 simulated minutes = every 5 minutes wall clock
python stream.py --interval 5

# 60x speed: 5 simulated minutes every 5 real seconds -- good for a live demo
python stream.py --interval 5 --speed 60

# Trigger a fuel leak 30 seconds after starting (handy for demoing the
# anomaly-detection feature live on stage)
python stream.py --interval 5 --speed 60 --demo-trigger 30:maitri:fuel_leak
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

from generator import ANOMALY_TYPES, StationSimulator
from station_config import STATIONS


def emit(record: dict) -> None:
    """Replace this with an MQTT publish / WebSocket send / DB insert later."""
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def parse_trigger(spec: str) -> tuple[float, str, str]:
    secs, station, kind = spec.split(":")
    if station not in STATIONS:
        raise argparse.ArgumentTypeError(f"Unknown station '{station}'")
    if kind not in ANOMALY_TYPES:
        raise argparse.ArgumentTypeError(f"Unknown anomaly '{kind}'")
    return float(secs), station, kind


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream synthetic telemetry in (accelerated) real time.")
    parser.add_argument("--start", default=None, help="ISO sim start time; default = now")
    parser.add_argument("--interval", type=float, default=5.0, help="Sim minutes per tick")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed-up factor vs wall clock")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--demo-trigger", action="append", default=[], type=parse_trigger,
        help="WALL_SECONDS:STATION:ANOMALY, repeatable -- fires N wall-clock seconds after start",
    )
    args = parser.parse_args()

    sim_time = datetime.fromisoformat(args.start) if args.start else datetime.now()
    sims = {key: StationSimulator(key, rng_seed=args.seed) for key in STATIONS}

    pending_triggers = sorted(args.demo_trigger)
    t0 = time.monotonic()
    tick_wall_seconds = (args.interval * 60.0) / max(args.speed, 1e-6)

    print(f"# streaming {list(sims)} | sim {args.interval} min/tick | "
          f"{args.speed}x speed | ~{tick_wall_seconds:.2f}s/tick (wall)", file=sys.stderr)

    try:
        while True:
            elapsed_wall = time.monotonic() - t0

            while pending_triggers and pending_triggers[0][0] <= elapsed_wall:
                secs, station, kind = pending_triggers.pop(0)
                sims[station].trigger_anomaly(kind, sim_time)
                print(f"# TRIGGER {kind} on {station} at {sim_time.isoformat()}", file=sys.stderr)

            for sim in sims.values():
                emit(sim.step(sim_time))

            sim_time += timedelta(minutes=args.interval)
            time.sleep(tick_wall_seconds)
    except KeyboardInterrupt:
        print("# stopped", file=sys.stderr)


if __name__ == "__main__":
    main()