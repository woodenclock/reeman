# Autoxing Spellbook CLI

Command-line utilities for interacting with **Autoxing AXBot** robots via REST API (port 8090) and WebSocket telemetry (`/ws/v2/topics`).

## Quick Start

```bash
cd autoxing-spellbook-cli

# One-time: create .venv and install dependencies (requires [UV](https://docs.astral.sh/uv/))
uv sync

# One-time: symlink spellbook commands into bin/
./setup_bin.sh

# Each terminal session: .venv/bin + bin/ on PATH
source activate_autoxing.sh

autoxing_help
get_device_info
```

## Installation

**Prerequisites:** Python **3.11+** and [UV](https://docs.astral.sh/uv/).

**1. Create the virtual environment** (from `autoxing-spellbook-cli/`):

```bash
uv sync
```

This reads `pyproject.toml` / `uv.lock`, creates `.venv/` in this directory, and installs `requests`, `websockets`, `rich`, `pyyaml`, and other CLI dependencies.

**2. Run setup** (creates symlinks in `bin/`):

```bash
./setup_bin.sh
```

**3. Activate the spellbook** (each shell session):

```bash
source activate_autoxing.sh
```

This prepends `bin/` (spellbook commands) and `.venv/bin` (Python + dependencies) to `PATH`, and sets `VIRTUAL_ENV` when `.venv` exists. Run `deactivate_autoxing` to undo both.

**Without UV:** install deps with `pip3 install requests websockets rich pyyaml` into the Python you want on `PATH`, then continue from step 2.

## Getting Help

```bash
# Quick reference — lists all commands
autoxing_help

# Detailed help with examples and workflows
autoxing_help_detailed
```

## Configuration

### `autoxing/credentials/CONSTANTS.yml`

Multi-robot config: a list of robots plus `active_index` (0-based) for the one all commands use. Copy from `CONSTANTS.example.yml` on first setup. **Gitignored** so real IPs are not committed.

If you still have legacy `CONSTANTS.py`, the first run of any command or `change_active_robot` migrates it to `CONSTANTS.yml` automatically.

```yaml
active_index: 0
prefix: http://
timeout_ms: 30000
robots:
  - name: d300_artc
    robot_ip: "192.168.25.25:8090"
  - name: lab_l300
    robot_ip: "192.168.68.64:8090"
    timeout_ms: 15000
```

- `active_index` — which entry in `robots` is active (table **key** column)
- `timeout_ms` — default HTTP/WebSocket timeout in **milliseconds** (e.g. `30000` = 30 s)
- `robots[].name` — label (`ROBOT_NAME` in code)
- `robots[].robot_ip` — `host:port`, **no** `http://`
- `robots[].timeout_ms` — optional per-robot override (ms)

### Switch active robot

```bash
change_active_robot
```

Shows a table of robots; enter an index to update `active_index` in `CONSTANTS.yml`.

WebSocket URLs use the active robot: `ws://{robot_ip}/ws/v2/topics`.

## Available Commands

Run `autoxing_help` for the categorized list. Commands are thin hand-written wrappers around common REST and WebSocket flows; see `openapi.yaml` for the full API surface.

### Core / Status

- `get_device_info` — GET `/device/info`; model, firmware, capabilities
- `get_battery_state` — WS `/battery_state`; percentage, charging status; stream; `-n N`
- `get_robot_position` — WS `/tracked_pose`; `[x, y]` position + orientation (radians); stream; `-n N`
- `get_pose` — WS `/tracked_pose`; **same as** `get_robot_position` (shorter name)
- `get_wheel_state` — WS `/wheel_state` snapshot; stream; `-n 1` one-shot
- `jack_state` — WS `/jack_state` snapshot; state, progress, self-check; stream; `-n 1` one-shot
- `get_path` — WS `/path` snapshot; stream; `-n 1` one-shot
- `get_map_ws` — WS `/map` snapshot (large payload trimmed in tty); stream; `-n 1` one-shot
- `get_alerts` — WS `/alerts`; active alert codes and messages; stream; `-n N`
- `get_current_map` — GET `/chassis/current-map`; active map name/ID
- `get_maps` — GET `/maps/`; list all maps with IDs and URLs

### WebSocket extras

- `ws_topic` — stream any topic(s): `ws_topic /wheel_state [/path …]`; `-n 1` for one payload; `--list` for topic names; `--no-topic-list` for older robots

### Map & Overlays (5)

- `get_map_overlays` — GET `/maps/{id}`; raw overlay GeoJSON (virtual walls, chargers, landmarks)
- `get_waypoints` — parse overlays from current map; extract named goals (chargers, barcodes, landmarks)
- `switch_map` — POST `/chassis/current-map`; interactive pick or `switch_map <id>`
- `set_pose` — POST `/chassis/pose`; localize to overlay point or `set_pose X Y ORI_RADIANS`
- `download_map` — save map raster PNG to **current directory**; `.png` appended if omitted; `download_map floor1 3` or interactive

### Navigation (6)

- `navigate` — POST `/chassis/moves`; interactive list, `navigate X Y ORI`, or `navigate <name>`; then watches `/planning_state` (`moving....`); Ctrl+C/Ctrl+D cancels unless `move_state` is already `succeeded` (`--no-monitor` to skip)
- `navigate_to_charger` — POST `/chassis/moves` with `type=charge`; dock at charger
- `cancel_move` — PATCH `/chassis/moves/current`; cancel active move
- `get_move_status` — GET `/chassis/moves/{id}`; poll state, fail reason
- `list_moves` — GET `/chassis/moves`; move history
- `check_robot_movement` — sample WS `/planning_state` ~15 s; MOVING/IDLE heuristic

### Wheel & Services (7)

- `set_control_mode` — POST `.../set_control_mode`; `auto`, `manual`, or `remote`; interactive if no arg
- `set_emergency_stop` — POST `.../set_emergency_stop`; software e-stop; may be unsupported on some SKUs
- `clear_wheel_errors` — POST `.../clear_errors`; reset wheel fault state
- `jack_up` — POST `/services/jack_up`; raise jack (monitor with `jack_state`)
- `jack_down` — POST `/services/jack_down`; lower jack
- `restart_service` — POST `/services/restart_service`; **disruptive**; confirms interactively

### Infrastructure (4)

- `change_active_robot` — pick `active_index` in `CONSTANTS.yml`
- `autoxing_help` — quick command reference
- `autoxing_help_detailed` — detailed help with workflows and auth notes
- `deactivate_autoxing` — remove spellbook commands from PATH

## Usage Examples

### Simple Status

```bash
get_device_info
get_battery_state -n 1         # one WS sample; omit -n to stream
get_robot_position -n 1
get_pose -n 1                # same as get_robot_position (/tracked_pose)
get_current_map
```

### WebSocket

All ws commands parse JSON from `/ws/v2/topics` and print syntax-highlighted JSON (via `rich`). Default is continuous streaming until Ctrl+C or Ctrl+D; pass `-n N` to stop after N messages.

```bash
# Help on any ws wrapper
get_battery_state -h
ws_topic -h

# Stream continuously (default)
get_battery_state
get_robot_position
get_pose                     # alias for get_robot_position
get_wheel_state
jack_state

# One sample, then exit immediately
get_battery_state -n 1
get_robot_position -n 1

# Multiple samples, then exit immediately
get_battery_state -n 5
get_robot_position -n 3 --timeout 10

# Large /map payload — trimmed in tty; longer default timeout (8 s)
get_map_ws              # stream
get_map_ws -n 1         # one sample

# Multi-topic streaming
ws_topic /wheel_state
ws_topic /planning_state /path
ws_topic /wheel_state -n 1
ws_topic /wheel_state /path -n 3

# List documented subscribe topic names
ws_topic --list
```

### Switch Map

The robot must have an active map loaded before it can navigate. After every reboot or map change you must re-localize with `set_pose`.

**Full workflow:**

```bash
# 1. See what maps are on the robot (note the id column)
get_maps
# example output:
#   [{'id': 3, 'map_name': 'floor1', ...},
#    {'id': 7, 'map_name': 'floor2', ...}]

# 2. Check which map is currently active
get_current_map

# 3. Switch to a different map
switch_map              # interactive — shows list, prompt to pick by index
switch_map 7            # non-interactive — pass the numeric map id directly
```

**Example — switch to map id 15 and verify:**

```bash
get_current_map
```

```json
{
  "id": 14,
  "uid": "69f99db00c6e8167a4427062",
  "map_name": "Game",
  "create_time": 1777966511,
  "map_version": 0,
  "overlays_version": 2
}
```

```bash
switch_map 15
```

```json
{
  "id": 15,
  "uid": "69fb0226fe07afec2a1e2c67",
  "map_name": "LargeARTC",
  "create_time": 1778057765,
  "map_version": 0,
  "overlays_version": 2
}
```

`switch_map` returns the activated map. Confirm with:

```bash
get_current_map
```

```json
{
  "id": 15,
  "uid": "69fb0226fe07afec2a1e2c67",
  "map_name": "LargeARTC",
  "create_time": 1778057765,
  "map_version": 0,
  "overlays_version": 2
}
```

`switch_map` takes the **map `id`** (from `get_maps` output), not the list index shown in the interactive picker. If the number you pass is smaller than the number of maps it treats it as a list index; otherwise as a raw map ID.

```bash
# 4. Re-localize after the map switch (robot doesn't know where it is on the new map)
set_pose                # interactive — lists overlay landmarks/chargers to pick from
set_pose 1.2 3.4 0.0   # or explicit: X Y ORI_RADIANS (radians CCW from East)

# 5. Confirm waypoints loaded from new map's overlays
get_waypoints

# 6. Navigate
navigate
```

`set_pose` with `adjust_position=true` (the default) lets the robot fine-tune its position from the given hint using its sensors. If the robot is close to a known landmark, pick that landmark — it gives the localizer a better starting point than raw coordinates.

### Navigation by Coordinates or Name

```bash
get_waypoints           # browse named points parsed from map overlays

navigate                # interactive — select from list
navigate 1.2 3.4 0.0   # coordinates: x, y, orientation (radians CCW from East)
navigate charger_42     # named landmark (if unique match in overlays)
```

### Move Lifecycle

```bash
navigate 5.0 10.0 1.57  # start a move (returns move ID)
get_move_status 42       # poll status
cancel_move              # cancel active move
list_moves               # view move history
check_robot_movement     # monitor movement in real-time (~15 s sample)
```

### Charger Docking

```bash
navigate_to_charger
get_move_status         # monitor until succeeded
```

### Wheel & Safety

```bash
set_control_mode               # interactive
set_control_mode auto

set_emergency_stop             # interactive
set_emergency_stop y

clear_wheel_errors

jack_up
jack_state -n 1                # one-shot progress after jack_up/jack_down
jack_down
```

### Map Image

```bash
download_map floor1 3          # writes ./floor1.png in cwd
download_map                   # fully interactive (basename only → .png added)
open floor1.png
```

### Switch Robot Target

Edit `autoxing/credentials/CONSTANTS.yml` (`active_index` / `robots`), or run `change_active_robot`, then re-activate if needed:

```bash
deactivate_autoxing
source activate_autoxing.sh
get_device_info
```

## API Endpoints

AXBot exposes REST at `http://{ROBOT_IP}:8090` and WebSocket at `ws://{ROBOT_IP}:8090/ws/v2/topics`.

### REST (HTTP)

- `GET /device/info` — device info and capability flags
- `GET /maps/` — list all maps
- `GET /maps/{id}` — map detail + overlays GeoJSON
- `GET /chassis/current-map` — active map
- `POST /chassis/current-map` — switch map
- `POST /chassis/pose` — set pose (localize)
- `POST /chassis/moves` — send move goal
- `GET /chassis/moves/{id}` — poll move status
- `GET /chassis/moves` — move history
- `PATCH /chassis/moves/current` — cancel move
- `POST /services/wheel_control/set_control_mode` — set control mode
- `POST /services/wheel_control/set_emergency_stop` — software e-stop
- `POST /services/wheel_control/clear_errors` — clear wheel errors
- `POST /services/restart_service` — restart robot service
- `POST /services/jack_up` — raise jack device
- `POST /services/jack_down` — lower jack device

### WebSocket Topics

Subscribe by sending `{"enable_topic": "<name>"}` after connecting to `/ws/v2/topics`.

- `/tracked_pose` — `{pos: [x, y], ori: radians}`
- `/battery_state` — `{percentage: 0–1, power_supply_status}`
- `/planning_state` — `{move_state, action_id, fail_reason, remaining_distance}`
- `/alerts` — `{alerts: [{code, level, msg}]}`
- `/wheel_state` — `{control_mode, emergency_stop_pressed}`
- `/jack_state` — `{state, progress, self_checking, self_check_state}`; `state`: `unknown`, `hold`, `jacking_up`, `jacking_down`

Always use `/ws/v2/topics` — the legacy `/ws/topics` path is deprecated.

## Path Resolution

All scripts support symlink-safe path resolution:

- Resolves the script's real location (follows symlinks in `bin/`)
- Falls back to `AUTOXING_SPELLBOOK_DIR` environment variable if resolution fails
- Works from any directory after `source activate_autoxing.sh`

## Troubleshooting

### Navigation Fails

```bash
get_current_map        # verify map is loaded
set_pose               # re-localize before navigating
get_waypoints          # check available overlay waypoints
get_move_status <id>   # poll move failure reason
```

## Full API surface (`openapi.yaml`)

The spellbook exposes focused commands for day-to-day fleet work (maps, moves, wheel control, settings). For endpoints without a dedicated script, call the robot directly (e.g. `curl`) using `[openapi.yaml](openapi.yaml)` and the [AXBot REST book](https://autoxingtech.github.io/axbot_rest_book/). Prefer `patch_settings` over deprecated `/robot-params`.