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


def get_reeman_wheel_state(timeout: float | None = None) -> dict | None:
    """Get Reeman wheel/motion state via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/speed",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        EPS = 1e-3
        vx = data.get("vx", 0)
        vth = data.get("vth", 0)
        moving = abs(vx) > EPS or abs(vth) > EPS

        return {
            "vx": vx,
            "vth": vth,
            "linear_velocity": vx,
            "angular_velocity": vth,
            "moving": moving,
            "state": "moving" if moving else "idle",
            # "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_wheel_state(timeout: float | None = None) -> dict | None:
    """
    Get wheel state.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """
    state = get_reeman_wheel_state(timeout=timeout)
    if state is not None:
        return state
    
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/wheel_state"], timeout=timeout)
        return got.get("/wheel_state")
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    state = get_wheel_state()
    if state is not None:
        print_json(state)
    else:
        run_single_topic_cli("/wheel_state", description="WebSocket /wheel_state")
