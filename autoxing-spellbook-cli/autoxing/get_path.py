#!/usr/bin/env python3

from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def get_path(timeout: float | None = None) -> dict | None:
    got = ws_get_topics(ROBOT.ROBOT_IP, ["/path"], timeout=timeout)
    return got.get("/path")


if __name__ == "__main__":
    run_single_topic_cli("/path", description="WebSocket /path")
