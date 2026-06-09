#!/usr/bin/env python3

from api_client import print_json, request_api


def get_device_info() -> dict | None:
    """GET /device/info — full firmware, model, capabilities."""
    data = request_api("GET", "/device/info")
    return data if isinstance(data, dict) else {"raw": data}


if __name__ == "__main__":
    result = get_device_info()
    if result is not None:
        print_json(result)
