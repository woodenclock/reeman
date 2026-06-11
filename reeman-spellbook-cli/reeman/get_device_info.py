#!/usr/bin/env python3

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_device_info(timeout: float | None = None) -> dict | None:
    """Get Reeman device info via REST API."""
    try:
        result: dict = {}

        endpoints = {
            "hostname": "/reeman/hostname",
            "current_version": "/reeman/current_version",
            "mode": "/reeman/get_mode",
            "pose": "/reeman/pose",
            "battery": "/reeman/base_encode",
        }

        for key, path in endpoints.items():
            resp = requests.get(
                f"{_robot_base_url()}{path}",
                timeout=timeout or 10,
            )
            resp.raise_for_status()
            result[key] = resp.json()

        result["robot_type"] = "Reeman_FlyBoat_Pro"
        result["api_type"] = "RestAPI"

        return result

    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_device_info_with_reeman_support() -> dict | None:
    """Try Reeman REST first, keep original OpenAPI path as fallback."""
    data = get_reeman_device_info()
    if data is not None:
        return data

    return get_device_info()


def get_device_info() -> dict | None:
    """GET /device/info — full firmware, model, capabilities."""
    data = request_api("GET", "/device/info")
    return data if isinstance(data, dict) else {"raw": data}


if __name__ == "__main__":
    result = get_device_info_with_reeman_support()
    if result is not None:
        print_json(result)
