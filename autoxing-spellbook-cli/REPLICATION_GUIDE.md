# Spellbook Replication Guide

How to build an identical CLI spellbook for a **different robot brand** from scratch.
Read this top-to-bottom before touching any files.

---

## What This Repo Does

`gausium_spellbook` is a collection of Python scripts that wrap a robot's REST API into
interactive CLI commands. The design goals are:

- **No global install** — works like a Python venv: `source activate_<name>.sh` adds a `bin/`
  directory to `$PATH`, `deactivate_<name>` removes it.
- **No argument memorisation** — every script is interactive when run bare; it prompts the user
  to pick a map, waypoint, or area from a live list fetched from the robot.
- **Importable functions** — every script also exports its core function so other scripts can
  call it (`from get_current_map import get_current_map`).
- **Single credentials file** — `gaussian/credentials/CONSTANTS.py` is the only place robot
  IP/name lives. `change_active_robot` rewrites it from `data.json`.

---

## Repository Layout

```
<robot>_spellbook/
├── <robot>/                        # All Python scripts live here
│   ├── credentials/
│   │   ├── CONSTANTS.py            # Active robot config (auto-generated, do not hand-edit)
│   │   └── .gitignore              # gitignore CONSTANTS.py so credentials don't leak
│   ├── data.json                   # Robot inventory (all known robots + their IPs)
│   └── *.py                        # One script per command (27+ files)
├── bin/                            # Symlinks created by setup_bin.sh (no .py suffix)
├── activate_<robot>.sh             # Source this to put bin/ on $PATH
├── deactivate_<robot>.sh           # Source this to remove bin/ from $PATH
├── setup_bin.sh                    # One-time setup: creates the bin/ symlinks
├── pyproject.toml                  # uv / pip project (only `requests` required)
└── README.md                       # User-facing quick-start
```

Naming convention: replace `<robot>` with a short lowercase slug for the robot brand,
e.g. `gaussian`, `keenon`, `pudu`, `coco`.

---

## Step-by-Step: Replicating for a New Robot

### 1 — Create the repo skeleton

```
mkdir <robot>_spellbook
cd <robot>_spellbook
git init
mkdir -p <robot>/credentials bin
touch <robot>/credentials/.gitignore
echo "CONSTANTS.py" >> <robot>/credentials/.gitignore
```

### 2 — Write `pyproject.toml`

```toml
[project]
name = "<robot>-spellbook"
version = "0.1.0"
description = "CLI utilities for <Robot Brand> robots"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "requests>=2.34.2",
]
```

Install with `uv sync` (preferred) or `pip install requests`.

### 3 — Write `<robot>/data.json` — Robot Inventory

```json
{
  "<robot_name_1>": {
    "ROBOT_IP": "<ip>:<port>",
    "CLEAN_IP": "<ip>:<krapi_port>/v1"
  },
  "<robot_name_2>": {
    "ROBOT_IP": "<ip>:<port>"
  }
}
```

**Rules:**
- `ROBOT_IP` — required. Full `host:port` string, **no** `http://`. The scripts prepend
  `PREFIX` from CONSTANTS.py at call time.
- `CLEAN_IP` — optional. Some robots expose the cleaning/scheduler API on a different port
  (e.g. `7201/v1`). If absent, the scripts fall back to `ROBOT_IP`.
- Key names become the `ROBOT_NAME` in CONSTANTS.py.

### 4 — Write `<robot>/credentials/CONSTANTS.py` (initial stub)

```python
PREFIX = 'http://'
ROBOT_NAME = '<robot_name_1>'
ROBOT_IP = '<ip>:<port>'
```

This file is **auto-generated** by `change_active_robot`. Create it once with mock values so
scripts can import it before any real robot is configured.

### 5 — Write `<robot>/change_active_robot.py`

This is the only script with non-trivial infra logic. Copy it verbatim from the Gausium
version and change only the module-name references. Key behaviours:

- Resolves its own real path (follows symlinks from `bin/`).
- Reads `data.json` from the same directory.
- Writes `credentials/CONSTANTS.py` with `PREFIX`, `ROBOT_NAME`, `ROBOT_IP`,
  `ROBOT_KRAPI_PREFIX`.
- Falls back to `GAUSSIAN_SPELLBOOK_DIR` env var (set by `activate_<robot>.sh`).

```python
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

def get_script_dir():
    script_path = os.path.realpath(__file__)
    script_dir  = os.path.dirname(script_path)
    if os.path.exists(os.path.join(script_dir, 'data.json')):
        return script_dir
    env_dir = os.environ.get('<ROBOT_UPPER>_SPELLBOOK_DIR')
    if env_dir and os.path.exists(os.path.join(env_dir, 'data.json')):
        return env_dir
    if os.path.exists('data.json'):
        return os.getcwd()
    print("ERROR: Cannot locate Spellbook directory!")
    sys.exit(1)

SCRIPT_DIR = get_script_dir()
credentials_dir = os.path.join(SCRIPT_DIR, 'credentials')
if credentials_dir not in sys.path:
    sys.path.insert(0, credentials_dir)

import CONSTANTS as ROBOT

def select_robots() -> dict:
    data_json_path = os.path.join(SCRIPT_DIR, 'data.json')
    with open(data_json_path) as f:
        data = json.load(f)
    robot_list = list(data.items())
    for i, (name, _) in enumerate(robot_list):
        print(f"{i} - {name}")
    if len(robot_list) == 1:
        return robot_list[0]
    while True:
        user_input = input("Select robot: ")
        if user_input.isdigit() and 0 <= int(user_input) < len(robot_list):
            return robot_list[int(user_input)]
        print("Invalid input.")

def write_to_file(file_path, selected):
    robot_name, config = selected
    robot_ip  = config['ROBOT_IP']
    clean_ip  = config.get('CLEAN_IP', robot_ip)
    with open(file_path, 'w') as f:
        f.write("PREFIX = 'http://'\n")
        f.write(f"ROBOT_NAME = '{robot_name}'\n")
        f.write(f"ROBOT_IP = '{robot_ip}'\n")
        f.write(f"ROBOT_KRAPI_PREFIX = '{clean_ip}'\n")

def main():
    print(f"Current robot: {ROBOT.ROBOT_NAME}")
    selected = select_robots()
    creds = os.path.join(SCRIPT_DIR, 'credentials', 'CONSTANTS.py')
    write_to_file(creds, selected)
    print(f"Done — active robot is now {selected[0]}")

if __name__ == '__main__':
    main()
```

Replace `<ROBOT_UPPER>` with the uppercased env var name, e.g. `KEENON`.

### 6 — Write every API script

**Pattern — every file must follow this template exactly:**

```python
#!/usr/bin/env python3

import requests
from urllib.error import HTTPError
from credentials import CONSTANTS as ROBOT       # <- always this alias

from get_current_map import get_current_map      # <- import helpers you depend on


def <command_name>(<args>) -> <return_type>:
    """One-line description."""
    URL = f"{ROBOT.PREFIX}{ROBOT.ROBOT_IP}/path/to/endpoint"
    params = { ... }

    try:
        r = requests.get(URL, params=params)     # or requests.post(...)
        r.raise_for_status()
        data = r.json()
        return data
    except requests.exceptions.ConnectionError as e:
        print(f'Connection error: {e}')
    except HTTPError as e:
        print(f'HTTP error: {e}')


if __name__ == "__main__":
    # Interactive CLI section — prompts user, calls the function above
    current_map = get_current_map()
    ...
    result = <command_name>(...)
    from pprint import pprint
    pprint(result)
```

**Critical rules:**
1. `#!/usr/bin/env python3` shebang on line 1 (makes the symlink in `bin/` executable without
   specifying python).
2. Import credentials as `from credentials import CONSTANTS as ROBOT`. The `credentials/`
   directory is on `sys.path` because `activate_<robot>.sh` exports
   `<ROBOT>_SPELLBOOK_DIR` and scripts resolve their own location via `os.path.realpath`.
3. The importable function (`def <command_name>(...)`) never calls `input()` or prints
   interactive prompts — that lives exclusively in `if __name__ == "__main__":`.
4. All inter-script dependencies are bare imports (`from get_waypoints import get_waypoints`).
   Python finds them because all scripts live in the same `<robot>/` directory and the
   symlinks resolve back to that directory.

#### How imports work across symlinks

`bin/navigate` is a symlink → `../gaussian/navigate.py`.  
When Python executes a symlink, `__file__` resolves to the **real** path
(`gaussian/navigate.py`), so `from credentials import CONSTANTS` works because
`gaussian/credentials/` exists relative to the real file.  
`change_active_robot.py` uses `os.path.realpath(__file__)` explicitly for the same reason.

### 7 — Write the help scripts

#### `<robot>_help.py` — quick reference

```python
#!/usr/bin/env python3
"""<Robot> Spellbook - Quick Help"""

COMMANDS = [
    ("Core Commands", [
        ("get_device_status",  "Get full robot status (battery, position, state)"),
        ("get_robot_position", "Get current position with nearest waypoint"),
        ...
    ]),
    ("Navigation Commands", [
        ("navigate",    "Navigate to waypoint (interactive or direct)"),
        ("switch_map",  "Switch to different map/floor"),
        ...
    ]),
    ...
]

def print_help():
    print("=" * 70)
    print("<Robot> Spellbook - Available Commands")
    print("=" * 70)
    for category, commands in COMMANDS:
        print(f"\n{category}:")
        print("-" * 70)
        for cmd, desc in commands:
            print(f"  {cmd:<30} {desc}")
    print()
    print("Run '<robot>_help_detailed' for detailed help with examples")
    print("=" * 70)

if __name__ == "__main__":
    print_help()
```

#### `<robot>_help_detailed.py` — per-command docs + workflow examples

Structure the string with these sections in order:

```
CORE COMMANDS
NAVIGATION COMMANDS
TASK QUEUE COMMANDS   (if the robot supports queued tasks)
AREA & CLEANING COMMANDS  (if the robot supports cleaning)
MAP MANAGEMENT COMMANDS
UTILITY COMMANDS
INFRASTRUCTURE COMMANDS
WORKFLOW EXAMPLES     <-- see below for floor-change example
API ENDPOINT REFERENCE
CONFIGURATION
TROUBLESHOOTING
```

**Floor/map-change workflow example** (include this verbatim pattern, adapted to your robot):

```
Map / Floor Operations:
  1. get_maps                     # List available maps (each map = one floor)
  2. get_current_map              # See which floor robot is on now
  3. switch_map L01               # Switch to floor L01
                                  #   - Interactive: run bare and pick from numbered list
                                  #   - Direct: pass map name as argument
  4. localize                     # After switching, re-localize the robot
                                  #   - Prompts for initialization waypoint
                                  #   - Option to rotate for better accuracy
  5. get_waypoints                # Confirm waypoints for the new floor
  6. navigate                     # Navigate to a waypoint on the new floor

Example — moving robot from L01 to L02:
  switch_map L02                  # Robot loads L02 map
  localize                        # Pick "L02_init_point", choose rotate=n
  navigate                        # Pick destination waypoint on L02
  check_robot_movement            # Verify robot is moving
```

### 8 — Write `setup_bin.sh`

```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="${SCRIPT_DIR}/<robot>"           # e.g. gaussian, keenon
BIN_DIR="${SCRIPT_DIR}/bin"

echo "==========================================="
echo "<Robot> Spellbook - Setup Bin Directory"
echo "==========================================="

mkdir -p "$BIN_DIR"
rm -f "$BIN_DIR"/*

cd "$ROBOT_DIR"
count=0
for script in *.py; do
  [ "$script" = "CONSTANTS.py" ] && continue
  bin_name="${script%.py}"
  ln -s "$ROBOT_DIR/$script" "$BIN_DIR/$bin_name"
  echo "   ✓ $bin_name -> <robot>/$script"
  count=$((count + 1))
done

echo ""
echo "✅ Setup complete! Created $count symlinks"
echo ""
echo "To activate:"
echo "  source activate_<robot>.sh"
echo ""
echo "You'll be able to run: <robot>_help, switch_map, navigate, ..."
echo ""
echo "To deactivate:"
echo "  deactivate_<robot>"
```

**Key decisions:**
- `CONSTANTS.py` is explicitly skipped — it is not a command.
- Symlinks use the **absolute** real path (`$ROBOT_DIR/$script`) so they work from any CWD.
- The script uses `rm -f "$BIN_DIR"/*` to wipe stale symlinks before recreating.

### 9 — Write `activate_<robot>.sh`

```bash
#!/usr/bin/env bash
# Usage: source activate_<robot>.sh   (NOT ./<name>.sh — won't affect current shell)

deactivate_<robot> () {
    if [ -n "${_OLD_<ROBOT>_PATH:-}" ]; then
        PATH="${_OLD_<ROBOT>_PATH:-}"
        export PATH
        unset _OLD_<ROBOT>_PATH
    fi
    if [ -n "${<ROBOT>_SPELLBOOK_DIR:-}" ]; then
        unset <ROBOT>_SPELLBOOK_DIR
    fi
    unset -f deactivate_<robot>
    echo "✅ <Robot> Spellbook deactivated!"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="${SCRIPT_DIR}/<robot>"
ROBOT_BIN="${SCRIPT_DIR}/bin"

if [[ ":$PATH:" == *":$ROBOT_BIN:"* ]]; then
    echo "⚠️  <Robot> Spellbook already activated in this session"
else
    _OLD_<ROBOT>_PATH="$PATH"
    export PATH="$ROBOT_BIN:$PATH"
    export <ROBOT>_SPELLBOOK_DIR="$ROBOT_DIR"
    echo "✅ <Robot> Spellbook activated!"
    echo "Run '<robot>_help' for quick reference"
    echo "Run 'deactivate_<robot>' to deactivate"
fi
```

**How it works:**
1. Defines `deactivate_<robot>` as a **function** in the current shell (the only way a
   sub-process can modify the parent shell's `$PATH`).
2. Saves original `$PATH` in `_OLD_<ROBOT>_PATH` before prepending `bin/`.
3. Exports `<ROBOT>_SPELLBOOK_DIR` pointing to the `<robot>/` scripts directory — this is
   what `change_active_robot` and other scripts fall back to when symlink resolution fails.
4. Guard against double-activation with the `[[ ":$PATH:" == *":$ROBOT_BIN:"* ]]` check.

### 10 — Write `deactivate_<robot>.sh`

```bash
#!/usr/bin/env bash
# Usage: source deactivate_<robot>.sh

if [ -n "$BASH_SOURCE" ] && [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "❌ Error: Must be sourced, not executed directly"
    echo "  source deactivate_<robot>.sh"
    exit 1
fi

if [ -n "${<ROBOT>_SPELLBOOK_DIR}" ]; then
    SCRIPT_DIR="$(dirname "$<ROBOT>_SPELLBOOK_DIR")"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

ROBOT_BIN="${SCRIPT_DIR}/bin"

if [[ ":$PATH:" == *":$ROBOT_BIN:"* ]]; then
    PATH=$(echo "$PATH" | sed -e "s|:${ROBOT_BIN}||g" -e "s|${ROBOT_BIN}:||g" -e "s|${ROBOT_BIN}||g")
    export PATH
    unset <ROBOT>_SPELLBOOK_DIR
    echo "✅ <Robot> Spellbook deactivated!"
else
    echo "⚠️  <Robot> Spellbook is not currently activated"
fi
```

Note: `deactivate_<robot>` the **function** (defined by the activate script) is the preferred
way to deactivate. This `.sh` file exists as a fallback and for documentation purposes.
They do the same thing via different mechanisms.

---

## Complete Script Inventory Reference

Every script in `gaussian/` and what it does. Use this as the checklist when building for a
new robot — implement only the scripts that the target robot's API supports.

| Script | Function exported | Description |
|---|---|---|
| `get_device_status.py` | `get_device_status()` | Battery, position, state, full status JSON |
| `get_robot_position.py` | `get_robot_position()` | x/y/theta + nearest waypoint |
| `get_current_map.py` | `get_current_map()`, `get_map_id()` | Active map name + resolve name→id |
| `get_maps.py` | `get_maps()` | All maps on robot |
| `get_waypoints.py` | `get_waypoints(map_name)` | All waypoints on a given map |
| `get_waypoints_detailed.py` | `get_waypoints_detailed(map_name)` | Waypoints with coords/angles |
| `get_nearest_waypoint.py` | `get_nearest_waypoint(x, y, map_name)` | Nearest waypoint to a position |
| `navigate.py` | `navigate(map_name, waypoint_name)` | Direct navigation (single command) |
| `navigate_by_coords.py` | `navigate_by_coords(x, y, theta)` | Navigate to coordinates |
| `navigate_by_task_queue.py` | _(main-only)_ | Add+start+wait+delete temp task queue |
| `navigate_with_check.py` | _(main-only)_ | Navigate then poll until arrived |
| `localize.py` | `localize(map_name, init_position, rotate)` | Localize at waypoint |
| `switch_map.py` | `switch_map(map_name)` | Load different map/floor |
| `add_to_task_queue.py` | `add_to_task_queue(map_name, map_id, waypoint_name, queue_name)` | Save task to queue |
| `get_task_queue.py` | `get_task_queue(map_name)` | Current queue contents |
| `get_status_of_task_queue.py` | `get_status_of_task_queue()` | Is queue running/finished |
| `start_task_queue.py` | `start_task_queue(map_name, queue_name)` | Begin queue execution |
| `stop_task_queue.py` | `stop_task_queue()` | Halt queue execution |
| `delete_task_from_queue.py` | `delete_task_from_queue(map_name, queue_name)` | Remove task from queue |
| `get_areas.py` | `get_areas(map_name)` | Cleaning areas/subareas |
| `get_area_id.py` | `get_area_id(map_name, area_name)` | Resolve area name→id |
| `clean.py` | `clean_area(map_name, area_name)` | Start cleaning task |
| `download_map.py` | `download_map(filename)` | Save map image |
| `delete_waypoints.py` | `delete_waypoints(pattern)` | Delete waypoints by name |
| `plot_waypoints.py` | _(main-only)_ | matplotlib visualisation |
| `check_robot_movement.py` | `check_robot_movement()` | Poll speed for 15s, report MOVING/IDLE/STUCK |
| `change_active_robot.py` | `main()` | Interactive robot switcher, rewrites CONSTANTS.py |
| `<robot>_help.py` | `print_help()` | Quick command reference |
| `<robot>_help_detailed.py` | `print_detailed_help()` | Full docs + workflow examples |

---

## How `clean.py` Handles Two API Flavours

The clean command detects which endpoint type to use at runtime:

```python
is_krapi = '7201' in GAUSIUM.ROBOT_KRAPI_PREFIX
```

- **KRAPI endpoint** (`CLEAN_IP` contains `7201`): simplified payload, `POST
  /gs-robot/scheduler/task/start`.
- **Standard endpoint** (port `8080`): comprehensive payload with `taskId`, `workMode`, etc.

When replicating for a new robot: determine whether the cleaning API differs from the general
API (different port, different payload schema). If so, replicate this detection pattern using
a distinguishing string from `ROBOT_KRAPI_PREFIX`.

---

## README Template — Use-Example Section

The README's "Usage Examples" section must include **at least** these workflow blocks.
Floor/map-switching is the most important multi-step example to document clearly.

````markdown
## Usage Examples

### Simple Status Check
```bash
get_device_status
get_robot_position
get_current_map
```

### Switching Floors / Maps
```bash
# 1. See what floors are available
get_maps

# 2. See which floor robot is on now
get_current_map

# 3. Switch floor (interactive — picks from numbered list)
switch_map

# OR switch directly by name (case-sensitive, use exact name from get_maps)
switch_map L02

# 4. Re-localize on the new floor (robot needs to know where it is)
localize
# → prompts for init waypoint, then asks: rotate? (y/n)
# → choose a waypoint near where the robot physically is on L02

# 5. Confirm waypoints are correct for the new floor
get_waypoints

# 6. Navigate
navigate
```

### Simple Navigation
```bash
# See available waypoints on current floor
get_waypoints

# Navigate interactively (numbered list)
navigate

# Navigate directly by name
navigate lobby_entrance
```

### Task Queue Workflow
```bash
# Build a sequence
add_to_task_queue waypoint_a
add_to_task_queue waypoint_b
add_to_task_queue waypoint_c

# Verify queue
get_task_queue

# Execute
start_task_queue

# Monitor progress
get_status_of_task_queue

# Stop if needed
stop_task_queue
```

### Cleaning Operations
```bash
# See cleaning areas on current map
get_areas

# Start cleaning (interactive)
clean

# OR direct by area name
clean lobby
```

### Map / Visualization
```bash
get_maps
switch_map L01
get_waypoints_detailed
plot_waypoints
download_map L01_floor.png
```

### Switching Robots
```bash
change_active_robot
# → shows numbered list from data.json
# → select robot, rewrites credentials/CONSTANTS.py

# Deactivate/reactivate to pick up new credentials
deactivate_<robot>
source activate_<robot>.sh
get_device_status
```
````

---

## Setup Process — Exact Order

This is the sequence a user runs the very first time, and after any `git pull`:

```bash
# 1. Install Python deps (one time)
pip3 install requests matplotlib
# OR with uv:
uv sync

# 2. Configure robots
#    Edit <robot>/data.json — add robot name, IP, port(s)

# 3. Set active robot (creates/overwrites credentials/CONSTANTS.py)
cd <robot>_spellbook
python3 <robot>/change_active_robot.py

# 4. Create bin/ symlinks (one time, or after adding new scripts)
./setup_bin.sh

# 5. Activate for this terminal session
source activate_<robot>.sh

# 6. Verify
<robot>_help
get_device_status
```

After step 5, every command in the inventory is available by name with no path prefix.

**After opening a new terminal:** repeat step 5 only (`source activate_<robot>.sh`).

**After adding a new script:** repeat step 4 (`./setup_bin.sh`) then step 5.

**After changing target robot:** run `change_active_robot` interactively, or reopen terminal
and repeat from step 5 (CONSTANTS.py is already updated).

---

## Credentials: What Must Not Be Committed

`<robot>/credentials/CONSTANTS.py` must be in `.gitignore`. It contains IP addresses.
The `.gitignore` lives at `<robot>/credentials/.gitignore` and contains a single line:

```
CONSTANTS.py
```

`data.json` is committed — it is the inventory of robots. IPs in `data.json` are acceptable
to commit if they are internal/VPN-only addresses (Tailscale, etc.).

---

## Anti-Patterns to Avoid

| Wrong | Right |
|---|---|
| `import sys; sys.path.insert(0, '../credentials')` | Use `from credentials import CONSTANTS` — the real-path resolution handles symlinks |
| `input()` inside the importable function | `input()` only in `if __name__ == "__main__":` |
| Hardcoding IP in any `.py` file | Always use `ROBOT.ROBOT_IP` from CONSTANTS |
| Running `./activate_<robot>.sh` | Always `source activate_<robot>.sh` |
| Running `./deactivate_<robot>.sh` | `deactivate_<robot>` (function) or `source deactivate_<robot>.sh` |
| Global `pip install` | Install into `.venv` with `uv sync` or `pip install -r ...` |

---

## Checklist for a New Robot Spellbook

- [ ] `pyproject.toml` created
- [ ] `<robot>/data.json` populated with at least one real robot entry
- [ ] `<robot>/credentials/CONSTANTS.py` stub created (mock values OK)
- [ ] `<robot>/credentials/.gitignore` blocks `CONSTANTS.py`
- [ ] `change_active_robot.py` adapted (env var name, data.json field names)
- [ ] All API scripts follow the `#!/usr/bin/env python3` + importable-function + `__main__` pattern
- [ ] `<robot>_help.py` lists every command
- [ ] `<robot>_help_detailed.py` has per-command docs + floor-switching workflow example
- [ ] `setup_bin.sh` adapted (ROBOT_DIR path, display name)
- [ ] `activate_<robot>.sh` adapted (function name, env var name, ROBOT_DIR)
- [ ] `deactivate_<robot>.sh` adapted (env var name)
- [ ] `README.md` includes Quick Start, Setup, Configuration, Usage Examples with floor-switch block
- [ ] `./setup_bin.sh` runs without error
- [ ] `source activate_<robot>.sh` works
- [ ] `<robot>_help` prints the command list
- [ ] `change_active_robot` successfully rewrites CONSTANTS.py
- [ ] `get_device_status` returns robot data (on real robot or mock)
