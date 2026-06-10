#!/usr/bin/env python3

import json

from api_client import print_json, request_api


# def get_device_info() -> dict | None:
#     """GET /device/info — full firmware, model, capabilities."""
#     data = request_api("GET", "/device/info")
#     return data if isinstance(data, dict) else {"raw": data}

def get_device_info() -> dict | None:
    """GET /reeman/current_version — Reeman navigation firmware/version info."""
    data = request_api("GET", "/reeman/current_version")

    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        return json.loads(data)

    return None

if __name__ == "__main__":
    result = get_device_info()
    if result is not None:
        print_json(result)
