#!/usr/bin/env python3
"""Subscribe to AXBot WebSocket topics — stream by default, or stop after -n messages."""

from __future__ import annotations

import argparse
import sys

from credentials import CONSTANTS as ROBOT
from credentials import timeout_seconds

from ws_cli import pprint_ws_message
from ws_helper import ws_stream_topics

# Subset of ``openapi.yaml`` x-websocket.topics (subscribe direction).
DOCUMENTED_SUBSCRIBE_TOPICS: tuple[str, ...] = (
    "/tracked_pose",
    "/battery_state",
    "/detailed_battery_state",
    "/planning_state",
    "/wheel_state",
    "/slam/state",
    "/alerts",
    "/map",
    "/maps/5cm/1hz",
    "/maps/1cm/1hz",
    "/path",
    "/trajectory",
    "/scan_matched_points2",
    "/robot_model",
    "/nearby_robots",
    "/jack_state",
    "/roller_state",
    "/bumper_state",
    "/detected_pallets",
    "/landmarks",
    "/sensor_manager_state",
    "/global_positioning_state",
    "/nearby_auto_doors",
    "/push_handle_state",
    "/detected_trailer",
    "/robot_signal",
    "/v2x_health_state",
    "/devpvt",
    "/map/info",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Stream AXBot /ws/v2/topics (see openapi.yaml x-websocket). "
            "Runs until Ctrl+C or Ctrl+D unless -n limits message count."
        ),
    )
    parser.add_argument(
        "topics",
        nargs="*",
        metavar="TOPIC",
        help="e.g. /wheel_state /path (leading slash optional)",
    )
    parser.add_argument("--list", action="store_true", help="Print documented subscribe topic names")
    parser.add_argument(
        "-n",
        type=int,
        metavar="N",
        dest="max_messages",
        help="exit after N payloads (e.g. -n 1 for a single sample)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="WebSocket connect timeout seconds (default: timeout_ms from CONSTANTS.yml)",
    )
    parser.add_argument(
        "--no-topic-list",
        action="store_true",
        help="Send separate enable_topic per topic (older robots without supportsEnableTopicList)",
    )
    args = parser.parse_args()

    if args.list:
        for t in DOCUMENTED_SUBSCRIBE_TOPICS:
            print(t)
        return

    if not args.topics:
        parser.error("pass at least one topic or use --list")

    if args.max_messages is not None and args.max_messages < 1:
        parser.error("-n must be >= 1")

    topics = [t if t.startswith("/") else f"/{t}" for t in args.topics]
    use_topic_list = False if args.no_topic_list else None
    ws_timeout = args.timeout if args.timeout is not None else timeout_seconds()

    def on_message(data: object) -> None:
        pprint_ws_message(data, trim_large_data=True)

    try:
        if args.max_messages is None:
            print("Streaming… (Ctrl+C or Ctrl+D to stop)", file=sys.stderr)

        received = ws_stream_topics(
            ROBOT.ROBOT_IP,
            topics,
            max_messages=args.max_messages,
            use_topic_list=use_topic_list,
            on_message=on_message,
            open_timeout=ws_timeout,
        )

        if args.max_messages is not None and received < args.max_messages:
            print(f"Only received {received}/{args.max_messages} payload(s).", file=sys.stderr)
            raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    except Exception as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
