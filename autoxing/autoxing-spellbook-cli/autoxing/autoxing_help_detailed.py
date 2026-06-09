#!/usr/bin/env python3
"""Autoxing Spellbook — detailed help and workflows."""

TEXT = """
AUTOXING SPELLBOOK — AXBot CLI
===============================

AUTH & BASE URL
  • No HTTP auth. Base: http://ROBOT_IP where ROBOT_IP is host:8090 from credentials.
  • Live telemetry: ws://ROBOT_IP/ws/v2/topics (use /ws/v2/topics — not legacy /ws/topics).

POSE & COORDINATES
  • Maps and moves use world-frame meters; orientation is radians counter-clockwise from East.

CORE COMMANDS
  get_device_info      GET /device/info — versions, caps{}, footprint.
  get_battery_state    WebSocket /battery_state (stream; -n 1 for one sample).
  get_robot_position   WebSocket /tracked_pose (pos [x,y], ori).
  get_pose             Same as get_robot_position (/tracked_pose).
  get_wheel_state      WebSocket /wheel_state snapshot (stream; -n 1 one-shot).
  jack_state           WebSocket /jack_state — state, progress, self-check (stream; -n 1 one-shot).
  get_path             WebSocket /path snapshot (stream; -n 1 one-shot).
  get_map_ws           WebSocket /map snapshot — large payload trimmed in tty (stream; -n 1 one-shot).
  get_alerts           WebSocket /alerts.
  get_current_map      GET /chassis/current-map.
  get_maps             GET /maps/ — list id, map_name, urls.

WEBSOCKET
  ws_topic /wheel_state [/path …]   Stream until Ctrl+C/Ctrl+D; -n 1 exits after one payload.
  ws_topic --list                   Print documented subscribe topic names (openapi.yaml subset).
  get_battery_state / get_robot_position / get_alerts
                       Same thin wrappers as above; stream until Ctrl+C/Ctrl+D; -n N to limit count.
  Multi-topic subscribe uses caps.supportsEnableTopicList when available; else
  sequential enable_topic in one session (--no-topic-list on ws_topic for older robots).

MAP / OVERLAYS / “WAYPOINTS”
  AXBot has no dedicated “list waypoints” REST API. Named goals are usually encoded in
  map ``overlays`` (GeoJSON FeatureCollection string on GET /maps/{id}):
    • Landmark  type 39
    • Charger   type  9
    • Barcode   type 37

  get_map_overlays     Interactive pick map → show overlay point count.
  get_waypoints        Parse overlays for the current (or given) map id.
  switch_map           POST /chassis/current-map: map id, --uid, --data-url + --map-name,
                       or --body-file / --body for full JSON.
  set_pose             POST /chassis/pose — required after switching map; pick overlay
                       point interactively or pass: set_pose X Y ORI radians.
  download_map         Save occupancy/thumbnail PNG via map detail URLs.
  create_map           POST /maps/ — --body-file (Base64, robot paths, or mapping_id).
  patch_map            PATCH /maps/{id} — map_name / overlays (--body-file or shortcuts).
  delete_all_maps      DELETE /maps/ — all maps (confirms).

MAPPING SESSIONS
  list_mappings        GET /mappings/
  start_mapping        POST /mappings/ — optional --continue-mapping, --start-pose-type.
  finish_mapping       PATCH /mappings/current — --state finished|cancelled.
  get_mapping ID       GET /mappings/{id}
  get_mapping_trajectories ID   GET …/trajectories.json
  get_mapping_landmarks ID      GET …/landmarks.json (v2.11.0+)
  delete_mapping ID    DELETE /mappings/{id} (confirms).
  delete_all_mappings  DELETE /mappings/ (confirms).

NAVIGATION COMMANDS
  navigate             POST /chassis/moves — all MoveType values via --type;
                       flags: --route, --detour-tolerance, --target-z, --charge-retry-count,
                       --rack-area-id, --use-target-zone / --no-target-zone, --json-extra,
                       --body-file. Legacy: X Y ORI, waypoint name, or interactive.
  navigate_along_route Convenience for type=along_given_route + --route CSV.
  navigate_to_charger  POST /chassis/moves {type: charge}.
  cancel_move          PATCH /chassis/moves/current {state: cancelled}.
  get_move_status ID   GET /chassis/moves/{id}.
  list_moves           GET /chassis/moves history.
  check_robot_movement Sample /planning_state for ~15s (MOVING / IDLE heuristic).

WHEEL / SERVICES
  set_control_mode     POST /services/wheel_control/set_control_mode — auto | manual | remote.
  set_emergency_stop   POST …/set_emergency_stop — some SKUs return “unsupported” for software e-stop.
  clear_wheel_errors   POST …/clear_errors.
  jack_up              POST /services/jack_up — raise jack; monitor via jack_state or ws_topic.
  jack_down            POST /services/jack_down — lower jack.
  restart_service      POST /services/restart_service — disruptive; confirms interactively.
  get_nav_thumbnail    GET /services/get_nav_thumbnail (optional --png-out).
  get_rgb_image        POST /services/get_rgb_image — --topic, --jpeg-out (caps.supportsGetRgbImage).

DEVICE / ADMIN
  get_device_brief     GET /device/info/brief.
  list_available_wifis GET /device/available_wifis.
  get_wifi_info        GET /device/wifi_info.
  get_boot_progress    GET /device/boot_progress.
  list_sensors         GET /device/sensors — topic names for cameras etc. (v2.12.0+).
  usb_devices          Subcommands: list | saved | save [--from-connected] | clear.
  chrony               Subcommands: conf | sources get|set|reset | allows get|set|disable.

SETTINGS (v2.9.0+)
  patch_settings        PATCH /system/settings/user from a JSON file or stdin (-).

INFRASTRUCTURE
  change_active_robot  Set active_index in credentials/CONSTANTS.yml (robot table).
  Setup: ./setup_bin.sh then source activate_autoxing.sh

WORKFLOW — MAP SWITCH + LOCALIZE
  1. get_maps
  2. get_current_map
  3. switch_map          # interactive or: switch_map MAP_ID
  4. set_pose            # pick landmark near physical robot, or enter x y ori
  5. get_waypoints
  6. navigate            # pick goal from overlay list

WORKFLOW — SIMPLE NAVIGATION
  get_waypoints
  navigate               # interactive
  # or: navigate 1.5 2.0 0.785
  get_move_status N      # use id returned from navigate

WORKFLOW — CHARGE DOCK
  navigate_to_charger
  get_move_status N

WORKFLOW — MONITORING
  check_robot_movement
  list_moves

WORKFLOW — SWITCH ROBOT
  change_active_robot    # table of robots; pick index → updates active_index
  # or edit autoxing/credentials/CONSTANTS.yml by hand
  deactivate_autoxing
  source activate_autoxing.sh
  get_device_info

DEPRECATIONS (do not use in new code)
  • WebSocket: /ws/topics (old) — use /ws/v2/topics.
  • PATCH /chassis/status — removed; use wheel_control services.
  • GET/POST /robot-params — deprecated; use patch_settings and /system/settings/*.

SAFETY
  • delete_map and restart_service confirm interactively before destructive calls.
  • Firmware / baseboard shutdown via REST can brick navigation or power-cycle the robot.

CONFIGURATION
  • autoxing/credentials/CONSTANTS.yml — robots list + active_index + timeout_ms (gitignored).
  • Copy CONSTANTS.example.yml → CONSTANTS.yml; legacy CONSTANTS.py auto-migrates on first use.
  • robot_ip must be host:port with no http://; timeout_ms is milliseconds for REST/WebSocket.

TROUBLESHOOTING
  • Connection refused — ping robot, check firewall, confirm port 8090.
  • Empty get_waypoints — map overlays may lack type 9/37/39 features; use navigate X Y ORI.
  • WebSocket timeout — robot booting or wrong IP; try get_device_info first.
"""


def print_detailed_help() -> None:
    print(TEXT)


if __name__ == "__main__":
    print_detailed_help()
