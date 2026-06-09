#!/usr/bin/env python3
"""Autoxing Spellbook — quick command list."""

from __future__ import annotations

import re
import sys

# Descriptions starting with "(ws)" use WebSocket /ws/v2/topics, not REST.

_METHOD_COLORS = {
    "GET": "\033[32m",  # green
    "POST": "\033[33m",  # yellow
    "PUT": "\033[34m",  # blue
    "DELETE": "\033[31m",  # red
    "PATCH": "\033[35m",  # purple
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
            ("get_device_info", "GET /device/info (model, firmware, caps)"),
            ("get_battery_state", "(ws) /battery_state; stream; -n N to limit"),
            ("get_robot_position", "(ws) /tracked_pose; stream; -n N to limit"),
            ("get_pose", "(ws) /tracked_pose; same as get_robot_position"),
            ("get_map_ws", "(ws) /map snapshot (large payload trimmed in tty); stream; -n 1 one-shot"),
            ("get_path", "(ws) /path snapshot; stream; -n 1 one-shot"),
            ("get_wheel_state", "(ws) /wheel_state snapshot; stream; -n 1 one-shot"),
            ("jack_state", "(ws) /jack_state snapshot; stream; -n 1 one-shot"),
            ("get_alerts", "(ws) /alerts; stream; -n N to limit"),
            ("get_current_map", "GET /chassis/current-map"),
            ("get_maps", "GET /maps/"),
        ],
    ),
    (
        "WebSocket extras",
        [
            ("ws_topic", "(ws) stream: `ws_topic /wheel_state` — `-n 1` one payload; `--list` topic names"),
        ],
    ),
    (
        "Map / overlays",
        [
            ("get_map_overlays", "GET /maps/{id} + list overlay navigation points"),
            ("get_waypoints", "Landmarks/chargers/barcodes from current map overlays"),
            ("switch_map", "POST /chassis/current-map — id, --uid, --data-url, --body-file"),
            ("set_pose", "POST /chassis/pose — localize"),
            ("download_map", "Save map raster from image_url"),
            ("create_map", "POST /maps/ — --body-file (Base64, files, or mapping_id)"),
            ("patch_map", "PATCH /maps/{id} — name/overlays"),
            ("delete_map", "DELETE /maps/{id} (confirms)"),
            ("delete_all_maps", "DELETE /maps/ — all maps (confirms)"),
            ("patch_settings", "PATCH /system/settings/user from JSON file/stdin"),
        ],
    ),
    (
        "Mapping sessions",
        [
            ("list_mappings", "GET /mappings/"),
            ("start_mapping", "POST /mappings/ — --continue-mapping, --start-pose-type"),
            ("finish_mapping", "PATCH /mappings/current — finished | cancelled"),
            ("get_mapping", "GET /mappings/{id}"),
            ("get_mapping_trajectories", "GET /mappings/{id}/trajectories.json"),
            ("get_mapping_landmarks", "GET /mappings/{id}/landmarks.json"),
            ("delete_mapping", "DELETE /mappings/{id} (confirms)"),
            ("delete_all_mappings", "DELETE /mappings/ (confirms)"),
        ],
    ),
    (
        "Navigation",
        [
            ("navigate", "POST /chassis/moves — full MoveType + flags + --body-file"),
            ("navigate_along_route", "along_given_route helper (--route CSV + pose)"),
            ("navigate_to_charger", "POST /chassis/moves type=charge"),
            ("cancel_move", "PATCH /chassis/moves/current"),
            ("get_move_status", "GET /chassis/moves/{id}"),
            ("list_moves", "GET /chassis/moves"),
            ("check_robot_movement", "(ws) sample /planning_state ~15 s"),
        ],
    ),
    (
        "Wheel / services (shortcuts)",
        [
            ("set_control_mode", "POST …/wheel_control/set_control_mode — auto | manual | remote"),
            ("set_emergency_stop", "POST …/set_emergency_stop — software e-stop when supported"),
            ("clear_wheel_errors", "POST …/clear_errors — clear wheel faults"),
            ("jack_up", "POST /services/jack_up — raise jack (monitor with jack_state)"),
            ("jack_down", "POST /services/jack_down — lower jack"),
            ("restart_service", "POST /services/restart_service (destructive)"),
            ("get_nav_thumbnail", "GET /services/get_nav_thumbnail (optional --png-out)"),
            ("get_rgb_image", "POST /services/get_rgb_image — --topic, --jpeg-out"),
        ],
    ),
    (
        "Device / admin",
        [
            ("get_device_brief", "GET /device/info/brief"),
            ("list_available_wifis", "GET /device/available_wifis"),
            ("get_wifi_info", "GET /device/wifi_info"),
            ("get_boot_progress", "GET /device/boot_progress"),
            ("list_sensors", "GET /device/sensors (v2.12.0+)"),
            ("usb_devices", "GET/PUT/DELETE /device/usb_devices — list | saved | save | clear"),
            ("chrony", "GET/PUT/DELETE /device/chrony/* — conf | sources | allows"),
        ],
    ),
    (
        "Infra",
        [
            ("change_active_robot", "Set active_index in CONSTANTS.yml (multi-robot table)"),
            ("autoxing_help", "Quick command reference"),
            ("autoxing_help_detailed", "Detailed help with workflows and auth notes"),
            ("deactivate_autoxing", "Remove spellbook commands from PATH"),
        ],
    ),
]


def print_help() -> None:
    use_color = sys.stdout.isatty()
    print("=" * 70)
    print("Autoxing Spellbook (AXBot REST + WebSocket)")
    print("=" * 70)
    for category, cmds in COMMANDS:
        print(f"\n{category}:")
        print("-" * 70)
        for cmd, desc in cmds:
            print(f"  {cmd:<28} {_colorize_desc(desc, use_color=use_color)}")
    print()
    print("See `autoxing_help_detailed` for workflows and API notes.")
    print("Spec: autoxing-spellbook-cli/openapi.yaml")
    print("=" * 70)


if __name__ == "__main__":
    print_help()
