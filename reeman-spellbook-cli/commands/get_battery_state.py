#!/usr/bin/env python3

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_battery_state(timeout: float | None = None) -> dict | None:
    """Get Reeman battery state via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/base_encode",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "percentage": data.get("battery"),
            "battery": data.get("battery"),
            "charge_flag": data.get("chargeFlag"),
            "emergency_button": data.get("emergencyButton"),
            # "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_battery_state(timeout: float | None = None) -> dict | None:
    # """Subscribe once to WebSocket ``/battery_state``."""
    """
    Get battery state.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """
    state = get_reeman_battery_state(timeout=timeout)
    if state is not None:
        return state
    
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/battery_state"], timeout=timeout)
        return got.get("/battery_state")
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    state = get_battery_state()
    if state is not None:
        print_json(state)
    else:
        run_single_topic_cli("/battery_state", description="WebSocket /battery_state")
