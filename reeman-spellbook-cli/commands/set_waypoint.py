#!/usr/bin/env python3

import argparse
import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


VALID_TYPES = {
    "waypoint": "normal",
    "normal": "normal",
    "delivery": "delivery",
    "production": "production",
    "charge": "charge",
    "charging": "charge",
    "charging_pile": "charge",
}


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_pose(timeout: float | None = None) -> dict | None:
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/pose",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Reeman REST error while getting pose: {e}")
        return None


def set_reeman_waypoint(
    name: str,
    waypoint_type: str = "normal",
    timeout: float | None = None,
) -> dict | None:
    """
    Set a Reeman waypoint using current robot position and orientation.

    Reeman API:
      POST /cmd/position
      body:
      {
        "name": "Point_A",
        "type": "normal",
        "pose": {"x": ..., "y": ..., "theta": ...}
      }
    """
    waypoint_type = VALID_TYPES.get(waypoint_type, waypoint_type)

    pose = get_reeman_pose(timeout=timeout)
    if pose is None:
        return None

    payload = {
        "name": name,
        "type": waypoint_type,
        "pose": {
            "x": pose.get("x"),
            "y": pose.get("y"),
            "theta": pose.get("theta"),
        },
    }

    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/position",
            json=payload,
            timeout=timeout or 10,
        )
        resp.raise_for_status()

        try:
            result = resp.json()
        except Exception:
            result = {}

        return {
            "status": "success",
            "name": name,
            "type": waypoint_type,
            "pose": payload["pose"],
            "response": result,
        }

    except Exception as e:
        print(f"Reeman REST error while setting waypoint: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set Reeman waypoint using current robot pose."
    )
    parser.add_argument(
        "name",
        help="Waypoint name, e.g. Point_A",
    )
    parser.add_argument(
        "--type",
        default="normal",
        choices=sorted(VALID_TYPES.keys()),
        help="Waypoint type. Default: normal",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10,
        help="REST timeout in seconds. Default: 10",
    )

    args = parser.parse_args()

    result = set_reeman_waypoint(
        name=args.name,
        waypoint_type=args.type,
        timeout=args.timeout,
    )

    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()