#!/usr/bin/env python3

#"""Read robot pose from WebSocket ``/tracked_pose`` (same data as ``get_robot_position``)."""
"""
Read robot pose.

Reeman FlyBoat uses REST API.
Existing OpenAPI/WebSocket path is kept as fallback.
"""

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics

TOPIC = "/tracked_pose"


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_pose(timeout: float | None = None) -> dict | None:
    """Get Reeman pose via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/pose",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "x": data.get("x"),
            "y": data.get("y"),
            "theta": data.get("theta"),
            # Compatibility with existing /tracked_pose shape.
            "pos": [data.get("x"), data.get("y")],
            "ori": data.get("theta"),
            # "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_pose(timeout: float | None = None) -> dict | None:
    #"""Subscribe to WebSocket ``/tracked_pose`` (world-frame meters, radians CCW from East)."""
    """
    Get robot pose.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """

    pose = get_reeman_pose(timeout=timeout)
    if pose is not None:
        return pose
        
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, [TOPIC], timeout=timeout)
        return got.get(TOPIC)
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    pose = get_pose()
    if pose is not None:
        print_json(pose)
    else:
        run_single_topic_cli(
            TOPIC,
            description="WebSocket /tracked_pose (alias of get_robot_position; pos [x,y], ori)",
        )
