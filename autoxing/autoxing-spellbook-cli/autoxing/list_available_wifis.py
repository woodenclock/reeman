#!/usr/bin/env python3
"""GET /device/available_wifis — scan nearby Wi-Fi networks."""

from api_client import print_json, request_api


def list_available_wifis() -> list | None:
    data = request_api("GET", "/device/available_wifis")
    return data if isinstance(data, list) else data


if __name__ == "__main__":
    result = list_available_wifis()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
