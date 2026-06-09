#!/usr/bin/env python3
"""GET /device/wifi_info — current network configuration."""

from api_client import print_json, request_api


def get_wifi_info() -> dict | None:
    data = request_api("GET", "/device/wifi_info")
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    result = get_wifi_info()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
