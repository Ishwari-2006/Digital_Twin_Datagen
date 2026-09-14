"""
Subscribes to station/+/telemetry over MQTT and writes each record into
Postgres. This is the "Data" side of the four-layer architecture -- the thing
that would run continuously on a small backend server.

Usage:
    python mqtt_subscriber.py
"""

from __future__ import annotations

import argparse
import json
import sys

import paho.mqtt.client as mqtt

from db.db import insert_record

TOPIC_FILTER = "station/+/telemetry"


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"# connected to broker (rc={reason_code}); subscribing to {TOPIC_FILTER}", file=sys.stderr)
    client.subscribe(TOPIC_FILTER, qos=1)


def on_message(client, userdata, msg):
    try:
        record = json.loads(msg.payload.decode("utf-8"))
        insert_record(record)
        tag = " [backfill]" if record.get("backfill") else ""
        print(f"# stored {record['station_id']} @ {record['timestamp']}{tag}", file=sys.stderr)
    except Exception as e:  # keep the subscriber alive even if one message is bad
        print(f"# ERROR processing message: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Subscribe to MQTT telemetry and write to Postgres.")
    parser.add_argument("--broker-host", default="localhost")
    parser.add_argument("--broker-port", type=int, default=1883)
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dt-subscriber")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker_host, args.broker_port, keepalive=30)

    print("# subscriber running -- Ctrl+C to stop", file=sys.stderr)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("# stopped", file=sys.stderr)


if __name__ == "__main__":
    main()