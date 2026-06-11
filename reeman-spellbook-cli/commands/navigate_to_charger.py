#!/usr/bin/env python3

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT

DEFAULT_CREATOR = "autoxing_spellbook_cli"


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_charger_point_name(default: str = "Charger") -> str:
    """
    Reeman /cmd/charge requires a calibrated charger point name.
    Override with REEMAN_CHARGER_POINT in CONSTANTS.yml if available.
    """
    return getattr(ROBOT, "REEMAN_CHARGER_POINT", default)


def navigate_to_reeman_charger(timeout: float | None = None) -> dict | None:
    """Send Reeman robot to charger via REST API."""
    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/charge",
            json={
                "type": 2,
                "point": get_reeman_charger_point_name(),
            },
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}

        return {
            "status": data.get("status", "success"),
            "type": "Charge",
            "point": get_reeman_charger_point_name(),
            # "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def navigate_to_charger(*, creator: str | None = None, timeout: float | None = None,) -> dict | None:
    # """POST /chassis/moves with ``type: charge``."""
    """
    Navigate to charger.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """

    # data = request_api(
    #     "POST",
    #     "/chassis/moves",
    #     json_body={"creator": creator or DEFAULT_CREATOR, "type": "charge"},
    # )
    # return data if isinstance(data, dict) else None

    out = navigate_to_reeman_charger(timeout=timeout)
    if out is not None:
        return out

    try:
        data = request_api(
            "POST",
            "/chassis/moves",
            json_body={"creator": creator or DEFAULT_CREATOR, "type": "charge"},
        )
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"OpenAPI fallback error: {e}")
        return None


if __name__ == "__main__":
    ans = input("Send robot to charging dock? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("Aborted.")
    else:
        out = navigate_to_charger()
        if out is not None:
            print_json(out)
