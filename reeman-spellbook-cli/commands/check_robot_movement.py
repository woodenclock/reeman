#!/usr/bin/env python3

# """Sample WebSocket `/planning_state` for ~15s — MOVING vs IDLE heuristic."""
"""
Check robot movement state.

Reeman FlyBoat uses REST API.
Existing OpenAPI/WebSocket `/planning_state` path is kept as fallback.
"""

from __future__ import annotations
from collections import Counter
from credentials import CONSTANTS as ROBOT
from ws_helper import ws_poll_topic

import requests


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_robot_movement(timeout: float | None = None) -> str | None:
    """Get Reeman robot movement state via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/nav_status",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        res = data.get("res")
        reason = data.get("reason")

        # Reeman nav_status:
        # res=1 -> navigation started / moving
        # res=3, reason=0 -> navigation success
        # res=3, reason=1 -> navigation failed
        # res=4 -> manual cancellation
        # res=6 -> normal / idle status
        if res == 1:
            return "MOVING"

        if res == 3:
            if reason == 0:
                return "IDLE_TERMINAL_RECENT"
            if reason == 1:
                return "IDLE_FAILED_RECENT"
            return "IDLE_TERMINAL_RECENT"

        if res == 4:
            return "IDLE_CANCELLED_RECENT"

        if res == 6:
            if reason == 2:
                return "IDLE_EMERGENCY_STOP"
            if reason == 6:
                return "IDLE_LOCALIZATION_ABNORMAL"
            return "IDLE"

        return f"UNKNOWN_REEMAN_RES_{res}"

    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None
    

def check_robot_movement(*, duration_sec: float = 15.0) -> str:
    """
    Check robot movement state.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket path is kept as fallback.
    """
    
    # msgs = ws_poll_topic(ROBOT.ROBOT_IP, "/planning_state", duration_sec=duration_sec)
    # if not msgs:
    #     return "NO_DATA"

    reeman_state = get_reeman_robot_movement(timeout=duration_sec)
    if reeman_state is not None:
        return reeman_state

    try:
        msgs = ws_poll_topic(
            ROBOT.ROBOT_IP,
            "/planning_state",
            duration_sec=duration_sec,
        )
    except Exception as e:
        print(f"WebSocket error: {e}")
        return "NO_DATA"

    if not msgs:
        return "NO_DATA"

    states = [m.get("move_state") for m in msgs if isinstance(m, dict)]
    ctr = Counter(s for s in states if isinstance(s, str))

    stuck = False
    for m in msgs:
        if isinstance(m, dict) and m.get("stuck_state"):
            stuck = stuck or True

    if ctr.get("moving", 0) > 2:
        return "MOVING" + ("_STUCK_HINT" if stuck else "")
    if ctr.get("moving", 0) > 0:
        return "MOVING_MINOR"
    terminal = ctr.get("succeeded", 0) + ctr.get("failed", 0) + ctr.get("cancelled", 0)
    if ctr.get("idle", 0) > 3 and terminal:
        return "IDLE_TERMINAL_RECENT"

    dominant = ctr.most_common(1)[0][0] if ctr else "UNKNOWN"

    stuck_note = "_STUCK" if stuck else ""
    return dominant + stuck_note


if __name__ == "__main__":
    print("Watching /planning_state for ~15s …")
    label = check_robot_movement()
    print(label)
