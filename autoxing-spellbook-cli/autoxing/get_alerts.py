#!/usr/bin/env python3

from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def get_alerts(timeout: float | None = None) -> dict | None:
    """Subscribe once to WebSocket ``/alerts``."""
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/alerts"], timeout=timeout)
        return got.get("/alerts")
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    run_single_topic_cli("/alerts", description="WebSocket /alerts")
