#!/usr/bin/env python3
"""GET/PUT/DELETE /device/usb_devices — connected and saved USB device lists."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import parse_json_file, print_json, request_api


def list_usb_devices() -> list | None:
    data = request_api("GET", "/device/usb_devices")
    return data if isinstance(data, list) else data


def get_saved_usb_devices() -> list | None:
    data = request_api("GET", "/device/usb_devices/saved")
    return data if isinstance(data, list) else data


def save_usb_devices(devices: list) -> dict | None:
    data = request_api("PUT", "/device/usb_devices/saved", json_body=devices)
    return data if isinstance(data, dict) else data


def clear_saved_usb_devices() -> dict | None:
    data = request_api("DELETE", "/device/usb_devices/saved")
    return data if isinstance(data, dict) else data


def _load_json_array(path: str) -> list:
    if path == "-":
        raw = sys.stdin.read()
        parsed = json.loads(raw)
    else:
        parsed = parse_json_file(path)
    if not isinstance(parsed, list):
        print("JSON must be an array of USB device objects.", file=sys.stderr)
        raise SystemExit(1)
    return parsed


def main() -> None:
    p = argparse.ArgumentParser(description="USB device list on robot (v2.5.0+)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="GET /device/usb_devices — currently connected")
    sub.add_parser("saved", help="GET /device/usb_devices/saved")

    save_p = sub.add_parser("save", help="PUT /device/usb_devices/saved")
    save_p.add_argument(
        "json_path",
        nargs="?",
        default="-",
        help="JSON array file, or omit for stdin",
    )
    save_p.add_argument(
        "--from-connected",
        action="store_true",
        help="snapshot current GET /device/usb_devices list",
    )

    sub.add_parser("clear", help="DELETE /device/usb_devices/saved")

    args = p.parse_args()

    if args.cmd == "list":
        result = list_usb_devices()
    elif args.cmd == "saved":
        result = get_saved_usb_devices()
    elif args.cmd == "save":
        if args.from_connected:
            devices = list_usb_devices()
            if devices is None:
                raise SystemExit(1)
        else:
            devices = _load_json_array(args.json_path)
        result = save_usb_devices(devices)
    else:
        c = input("Clear saved USB device list? [y/N]: ").strip().lower()
        if c not in ("y", "yes"):
            print("Aborted.")
            raise SystemExit(0)
        result = clear_saved_usb_devices()

    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
