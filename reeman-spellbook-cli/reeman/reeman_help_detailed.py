#!/usr/bin/env python3
"""Reeman FlyBoat Pro Spellbook — detailed help and workflows."""

TEXT = """
REEMAN FLYBOAT PRO SPELLBOOK — REST API CLI
===========================================

AUTH & BASE URL
  - No HTTP auth.
  - Base URL is read from credentials/CONSTANTS.yml.
  - Current robot host should be configured as: http://10.59.58.209

POSE & COORDINATES
  - Reeman pose API: GET /reeman/pose
  - Returns x, y, theta.
  - Navigation by coordinate uses theta in radians.

CORE COMMANDS
  get_device_info      GET /reeman/hostname + GET /reeman/current_version.
  get_battery_state    GET /reeman/base_encode.
  get_robot_position   GET /reeman/pose.
  get_pose             Same as get_robot_position.
  get_current_map      GET /reeman/current_map.
  get_maps             GET /reeman/history_map.
  get_map_overlays     GET /reeman/position.
  get_waypoints        GET /reeman/position.

MAP / WAYPOINTS
  Reeman exposes calibrated map points through:
    GET /reeman/position

  Expected response shape:
    {
      "waypoints": [
        {
          "name": "Point_A",
          "type": "delivery",
          "pose": {"x": -1.0, "y": -1.43, "theta": -1.57}
        }
      ]
    }

  get_map_overlays     Shows current map and extracted navigation points.
  get_waypoints        Lists calibrated navigation points.
  get_current_map      Shows active map alias/name.
  get_maps             Lists available maps.
  switch_map           POST /cmd/apply_map.

NAVIGATION COMMANDS
  navigate             POST /cmd/nav_name or POST /cmd/nav.
                       Use point name or x y theta.
  cancel_move          POST /cmd/cancel_goal.
  get_move_status      GET /reeman/nav_status.
  check_robot_movement Poll GET /reeman/nav_status until moving/idle result.

NAVIGATION STATUS
  Reeman navigation status:
    GET /reeman/nav_status

  Important result values:
    res=6  normal / idle status
    res=1  navigation started / moving
    res=3  navigation result
    res=4  manually cancelled

  Important reason values when res=3:
    reason=0 navigation successful
    reason=1 navigation failed

MOVEMENT COMMANDS
  speed                POST /cmd/speed.
                       Body: {"vx": 0.3, "vth": 0.0}
  move                 POST /cmd/move.
                       Body: {"distance": 100, "direction": 1, "speed": 0.5}
  turn                 POST /cmd/turn.
                       Body: {"direction": 1, "angle": 90, "speed": 0.6}
  set_max_speed        POST /cmd/max_speed.
                       Body: {"speed": 0.5}

JACK / EXTERNAL CONTROL
  jack_up              POST /cmd/hydraulic_up.
  jack_down            POST /cmd/hydraulic_down.
  lock                 POST /cmd/lock.
  unlock               POST /cmd/unlock.

MAP SWITCH WORKFLOW
  1. get_maps
  2. get_current_map
  3. switch_map
  4. get_current_map
  5. get_waypoints

SIMPLE NAVIGATION WORKFLOW
  1. get_waypoints
  2. navigate Point_A
  3. get_move_status
  4. navigate Point_B
  5. get_move_status

A -> B -> C TEST WORKFLOW
  1. get_waypoints
  2. navigate Point_A
  3. wait until get_move_status reports idle/success
  4. navigate Point_B
  5. wait until get_move_status reports idle/success
  6. navigate Point_C
  7. wait until get_move_status reports idle/success

CHARGING WORKFLOW
  1. get_waypoints
  2. confirm charger point exists
  3. navigate Charger
  4. get_move_status

JACK WORKFLOW
  1. jack_up
  2. verify cargo rack lifted physically
  3. jack_down
  4. verify cargo rack lowered physically

INFRASTRUCTURE
  change_active_robot  Set active_index in credentials/CONSTANTS.yml.
  reeman_help          Quick command reference.
  reeman_help_detailed Detailed help with workflows and API notes.
  deactivate_reeman    Remove Reeman Spellbook commands from PATH.

SETUP
  cd reeman-spellbook-cli

  uv sync
  ./setup_bin.sh
  source activate_reeman.sh
  
  reeman_help
  get_device_info

CONFIGURATION
  reeman-spellbook-sli/reeman/credentials/CONSTANTS.yml stores robot host configuration.
  Keep robot IP there and let scripts read from it.

TROUBLESHOOTING
  Connection failed:
    - Check robot and laptop are on same LAN.
    - Check robot IP in credentials/CONSTANTS.yml.
    - Open http://10.59.58.209 in browser.

  Empty waypoints:
    - Check points are calibrated in robot web UI.
    - Run get_current_map and confirm the correct map is active.

  Robot does not navigate:
    - Check emergency stop is released.
    - Check robot localization is correct.
    - Check target point is not too close to obstacles or virtual walls.

  Navigation failed:
    - Run get_move_status.
    - Re-localize robot from web UI if pose is wrong.
    - Try navigating to a nearby known point first.

SAFETY
  - Do not stand directly in front of the robot during navigation.
  - Keep emergency stop accessible.
  - Verify jack_up and jack_down physically before payload testing.
"""


def print_detailed_help() -> None:
    print(TEXT)


if __name__ == "__main__":
    print_detailed_help()