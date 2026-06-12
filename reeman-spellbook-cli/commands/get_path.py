#!/usr/bin/env python3

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


NO_PATH_MESSAGE = "If robot is not navigating to destination, no paths will be printed out\n\n"


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_path(timeout: float | None = None) -> dict | None:
    """Get Reeman navigation path via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/global_plan",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "coordinates": data.get("coordinates", []),
            # "raw": data,
        }
    except Exception:
        return {
            "coordinates": [],
        }


def get_path(timeout: float | None = None) -> dict | None:
    """
    Get navigation path.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """
    path = get_reeman_path(timeout=timeout)
    if path is not None:
        return path

    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/path"], timeout=timeout)
        return got.get("/path")
    except Exception:
        return None


if __name__ == "__main__":
    print(NO_PATH_MESSAGE, end="")

    path = get_path()
    if path is not None:
        coordinates = path.get("coordinates", [])
        if coordinates:
            print_json(path)
    else:
        run_single_topic_cli("/path", description="WebSocket /path")