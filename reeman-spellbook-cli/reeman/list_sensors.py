#!/usr/bin/env python3
"""GET /device/sensors — sensor list and primary topic names (v2.12.0+)."""

from api_client import print_json, request_api


def list_sensors() -> dict | None:
    data = request_api("GET", "/device/sensors")
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    result = list_sensors()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
