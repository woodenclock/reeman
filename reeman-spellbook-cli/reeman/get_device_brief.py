#!/usr/bin/env python3
"""GET /device/info/brief — compact device info."""

from api_client import print_json, request_api


def get_device_brief() -> dict | None:
    data = request_api("GET", "/device/info/brief")
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    result = get_device_brief()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
