#!/usr/bin/env python3
"""GET /device/boot_progress — boot status and logs."""

from api_client import print_json, request_api


def get_boot_progress() -> dict | None:
    data = request_api("GET", "/device/boot_progress")
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    result = get_boot_progress()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
