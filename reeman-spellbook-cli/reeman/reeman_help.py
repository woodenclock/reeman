#!/usr/bin/env python3
"""Reeman FlyBoat Pro Spellbook — quick command list."""

from __future__ import annotations

import re
import sys

_METHOD_COLORS = {
    "GET": "\033[32m",
    "POST": "\033[33m",
    "PUT": "\033[34m",
    "DELETE": "\033[31m",
    "PATCH": "\033[35m",
}
_RESET = "\033[0m"
_METHOD_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b")


def _colorize_desc(desc: str, *, use_color: bool) -> str:
    if not use_color:
        return desc

    def _repl(match: re.Match[str]) -> str:
        method = match.group(1)
        return f"{_METHOD_COLORS[method]}{method}{_RESET}"

    return _METHOD_RE.sub(_repl, desc)


COMMANDS = [
    (
        "Core / status",
        [
            ("get_device_info", "GET /reeman/hostname + /reeman/current_version"),
            ("get_battery_state", "GET /reeman/base_encode"),
            ("get_robot_position", "GET /reeman/pose"),
            ("get_pose", "GET /reeman/pose"),
            ("get_current_map", "GET /reeman/current_map"),
            ("get_maps", "GET /reeman/history_map"),
            ("get_map_overlays", "GET /reeman/position"),
            ("get_waypoints", "GET /reeman/position"),
        ],
    ),
    (
        "Navigation",
        [
            ("navigate", "POST /cmd/nav_name or POST /cmd/nav"),
            ("cancel_move", "POST /cmd/cancel_goal"),
            ("get_move_status", "GET /reeman/nav_status"),
            ("check_robot_movement", "GET /reeman/nav_status polling"),
            ("switch_map", "POST /cmd/apply_map"),
            ("set_pose", "POST /cmd/reloc_pose"),
        ],
    ),
    (
        "Movement",
        [
            ("move", "POST /cmd/move"),
            ("speed", "POST /cmd/speed"),
            ("turn", "POST /cmd/turn"),
            ("set_max_speed", "POST /cmd/max_speed"),
        ],
    ),
    (
        "Jack / external control",
        [
            ("jack_up", "POST /cmd/hydraulic_up"),
            ("jack_down", "POST /cmd/hydraulic_down"),
            ("lock", "POST /cmd/lock"),
            ("unlock", "POST /cmd/unlock"),
        ],
    ),
    (
        "Infra",
        [
            ("change_active_robot", "Set active_index in CONSTANTS.yml"),
            ("reeman_help", "Quick command reference"),
            ("reeman_help_detailed", "Detailed help with workflows and API notes"),
            ("deactivate_reeman", "Remove spellbook commands from PATH"),
        ],
    ),
]


def print_help() -> None:
    use_color = sys.stdout.isatty()
    print("=" * 70)
    print("Reeman FlyBoat Pro Spellbook (REST API)")
    print("=" * 70)
    for category, cmds in COMMANDS:
        print(f"\n{category}:")
        print("-" * 70)
        for cmd, desc in cmds:
            print(f"  {cmd:<28} {_colorize_desc(desc, use_color=use_color)}")
    print()
    print("See `reeman_help_detailed` for workflows and API notes.")
    print("Spec: reeman-spellbook-cli/openapi.yaml")
    print("=" * 70)


if __name__ == "__main__":
    print_help()