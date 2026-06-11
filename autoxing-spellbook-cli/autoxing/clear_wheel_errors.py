#!/usr/bin/env python3

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def clear_reeman_wheel_errors(timeout: float | None = None) -> dict | None:
    """
    Clear Reeman wheel errors.

    Reeman SDK does not expose /services/wheel_control/clear_errors.
    Best equivalent is to send zero speed to stop wheel motion.
    """
    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/speed",
            json={"vx": 0, "vth": 0},
            timeout=timeout or 10,
        )
        resp.raise_for_status()

        data = resp.json() if resp.content else {}

        return {
            "status": "success",
            "message": "Reeman wheel stop command sent",
            "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def clear_wheel_errors(timeout: float | None = None) -> dict | None:
    # """POST /services/wheel_control/clear_errors."""
    """
    Clear wheel errors.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI path is kept as fallback.
    """

    # data = request_api("POST", "/services/wheel_control/clear_errors", json_body={})
    # return data if isinstance(data, dict) else data

    state = clear_reeman_wheel_errors(timeout=timeout)
    if state is not None:
        return state

    try:
        data = request_api(
            "POST",
            "/services/wheel_control/clear_errors",
            json_body={},
        )
        return data if isinstance(data, dict) else data
    except Exception as e:
        print(f"OpenAPI error: {e}")
        return None


if __name__ == "__main__":
    out = clear_wheel_errors()
    if out is not None:
        print_json(out)
