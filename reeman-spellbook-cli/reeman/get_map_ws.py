#!/usr/bin/env python3

"""
Get map data.

Reeman FlyBoat uses REST API.
Existing OpenAPI/WebSocket path is kept as fallback.
"""

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_map(timeout: float | None = None) -> dict | None:
    """Get Reeman current map via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/map",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None

def get_map_ws(timeout: float | None = None) -> dict | None:
    """
    Get map data.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """
    state = get_reeman_map(timeout=timeout)
    if state is not None:
        return state

    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/map"], timeout=timeout)
        return got.get("/map")
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    state = get_map_ws()
    if state is not None:
        print_json(state)
    else:
        run_single_topic_cli(
            "/map",
            description="WebSocket /map (large data field trimmed in tty)",
            trim_large_data=True,
        )
