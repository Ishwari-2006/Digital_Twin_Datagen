"""
Publishes synthetic telemetry to MQTT (Mosquitto), one topic per station:

    station/maitri/telemetry
    station/bharati/telemetry

This is the real version of stream.py's `emit()` seam. Behavior during a
comms blackout matches Section 3.3 of the reference doc: while a station's
`comms_status` is "blackout", records are NOT published live (the generator
itself buffers them internally); as soon as the blackout ends, the whole
buffered backlog is published in one burst, each record tagged
`"backfill": true` so a subscriber/dashboard can tell "this just happened
live" from "this arrived late from the blackout queue".

Usage:
    python mqtt_publisher.py --interval 5 --speed 60
    python mqtt_publisher.py --interval 5 --speed 60 --demo-trigger 30:maitri:comms_blackout
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

from db.db import update_command_status
from generator import ANOMALY_TYPES, StationSimulator
from station_config import STATIONS

TOPIC_TEMPLATE = "station/{station_id}/telemetry"
COMMAND_TOPIC_FILTER = "station/+/command"


def on_command_message(client, userdata, msg):
    """
    Remote Management Action Layer: the publisher owns the live
    StationSimulator instances, so it's the process that actually applies
    operator commands. `userdata` is the {station_id: StationSimulator} dict
    set via client.user_data_set() in main().
    """
    sims = userdata
    try:
        station_id = msg.topic.split("/")[1]
        cmd = json.loads(msg.payload.decode("utf-8"))
    except (IndexError, json.JSONDecodeError) as exc:
        print(f"# BAD COMMAND on {msg.topic}: {exc}", file=sys.stderr)
        return

    sim = sims.get(station_id)
    if sim is None:
        print(f"# command for unknown station '{station_id}'", file=sys.stderr)
        return

    result = sim.apply_command(cmd)
    print(f"# COMMAND {station_id} <- {cmd.get('command')}: {result}", file=sys.stderr)

    command_id = cmd.get("command_id")
    if command_id is not None:
        try:
            update_command_status(command_id, "applied" if result.get("applied") else "failed")
        except Exception as exc:
            print(f"# failed to update audit row {command_id}: {exc}", file=sys.stderr)


def parse_trigger(spec: str) -> tuple[float, str, str]:
    secs, station, kind = spec.split(":")
    if station not in STATIONS:
        raise argparse.ArgumentTypeError(f"Unknown station '{station}'")
    if kind not in ANOMALY_TYPES:
        raise argparse.ArgumentTypeError(f"Unknown anomaly '{kind}'")
    return float(secs), station, kind


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish synthetic telemetry over MQTT.")
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--start", default=None, help="ISO sim start time; default = now")
    parser.add_argument("--interval", type=float, default=5.0, help="Sim minutes per tick")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed-up factor vs wall clock")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--demo-trigger", action="append", default=[], type=parse_trigger,
        help="WALL_SECONDS:STATION:ANOMALY, repeatable",
    )
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dt-publisher")
    client.connect(args.broker_host, args.broker_port, keepalive=30)
    client.loop_start()

    sim_time = datetime.fromisoformat(args.start) if args.start else datetime.now()
    sims = {key: StationSimulator(key, rng_seed=args.seed) for key in STATIONS}
    was_blacked_out = {key: False for key in STATIONS}

    # Remote Management Action Layer: listen for operator commands alongside
    # the publish loop. client.loop_start() (above) already runs a background
    # network thread, so subscribing here is enough -- no extra polling needed.
    client.user_data_set(sims)
    client.message_callback_add(COMMAND_TOPIC_FILTER, on_command_message)
    client.subscribe(COMMAND_TOPIC_FILTER, qos=1)

    pending_triggers = sorted(args.demo_trigger)
    t0 = time.monotonic()
    tick_wall_seconds = (args.interval * 60.0) / max(args.speed, 1e-6)

    print(
        f"# publishing {list(sims)} -> mqtt://{args.broker_host}:{args.broker_port} | "
        f"{args.interval} sim-min/tick | {args.speed}x speed",
        file=sys.stderr,
    )

    try:
        while True:
            elapsed_wall = time.monotonic() - t0

            while pending_triggers and pending_triggers[0][0] <= elapsed_wall:
                secs, station, kind = pending_triggers.pop(0)
                sims[station].trigger_anomaly(kind, sim_time)
                print(f"# TRIGGER {kind} on {station} at {sim_time.isoformat()}", file=sys.stderr)

            for key, sim in sims.items():
                record = sim.step(sim_time)
                topic = TOPIC_TEMPLATE.format(station_id=key)

                if record["_delivered_live"]:
                    client.publish(topic, json.dumps(record), qos=1)
                # else: blacked out -- generator already queued it internally, don't publish yet

                # Blackout just ended this tick -> flush the backlog in one burst.
                if was_blacked_out[key] and not sim.is_blacked_out():
                    backlog = sim.drain_queue()
                    print(f"# comms recovered on {key} -- flushing {len(backlog)} queued records", file=sys.stderr)
                    for queued in backlog:
                        queued["backfill"] = True
                        client.publish(topic, json.dumps(queued), qos=1)
                was_blacked_out[key] = sim.is_blacked_out()

            sim_time += timedelta(minutes=args.interval)
            time.sleep(tick_wall_seconds)
    except KeyboardInterrupt:
        print("# stopped", file=sys.stderr)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()