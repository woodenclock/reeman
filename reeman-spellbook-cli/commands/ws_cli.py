"""Shared argparse CLI for single-topic WebSocket helper scripts."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import print_json
from credentials import CONSTANTS as ROBOT
from credentials import timeout_seconds

from ws_helper import ws_stream_topics


def parse_ws_payload(data: object) -> object:
    """Return parsed JSON from a WebSocket frame (object or JSON string)."""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    return data


def preview_payload(data: object, *, trim_large_data: bool = False) -> object:
    data = parse_ws_payload(data)
    if not isinstance(data, dict):
        return data
    preview = dict(data)
    if trim_large_data:
        val = preview.get("data")
        if isinstance(val, str) and len(val) > 120:
            preview["data"] = f"<{len(val)} chars>"
        inner = preview.get("map")
        if isinstance(inner, dict) and isinstance(inner.get("data"), str) and len(inner["data"]) > 120:
            preview["map"] = {**inner, "data": f"<{len(inner['data'])} chars>"}
    return preview


def pprint_ws_message(data: object, *, trim_large_data: bool = False) -> None:
    print_json(preview_payload(data, trim_large_data=trim_large_data))


def run_single_topic_cli(
    topic: str,
    *,
    description: str,
    default_timeout: float | None = None,
    trim_large_data: bool = False,
) -> None:
    if default_timeout is None:
        default_timeout = timeout_seconds()
    parser = argparse.ArgumentParser(
        description=(
            f"{description} — streams until Ctrl+C or Ctrl+D unless -n limits count."
        ),
    )
    parser.add_argument(
        "-n",
        type=int,
        metavar="N",
        dest="max_messages",
        help="exit after N payloads (default: stream continuously)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="WebSocket timeout seconds (default: timeout_ms from CONSTANTS.yml)",
    )
    args = parser.parse_args()
    ws_timeout = args.timeout if args.timeout is not None else default_timeout

    if args.max_messages is not None and args.max_messages < 1:
        parser.error("-n must be >= 1")

    t = topic if topic.startswith("/") else f"/{topic}"

    def on_message(data: object) -> None:
        pprint_ws_message(data, trim_large_data=trim_large_data)

    try:
        if args.max_messages is None:
            print("Streaming… (Ctrl+C or Ctrl+D to stop)", file=sys.stderr)

        received = ws_stream_topics(
            ROBOT.ROBOT_IP,
            [t],
            max_messages=args.max_messages,
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
