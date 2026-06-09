# Autoxing Spellbook

Tools for operating **Autoxing AXBot** mobile robots on the LAN. The spellbook wraps the robot’s REST API (default port **8090**) and WebSocket telemetry (`/ws/v2/topics`) so you can drive, monitor, and debug robots from the terminal or a browser—without writing one-off API scripts each time.

## What this repo is for

- **Day-to-day robot ops** — battery, pose, maps, navigation, jack, alerts, mapping sessions, and related chassis/services calls.
- **Scriptable workflows** — each capability is a small Python command you can run from the shell, chain in scripts, or use in automation.
- **Interactive control** — a Streamlit UI for the same API when you want maps, telemetry, and manual control in one place.

Both packages target the same OpenAPI surface (see `autoxing-spellbook-cli/openapi.yaml`). The robot must be reachable at `http://<robot-ip>:8090` on your network.

## Repository layout

| Directory | Purpose |
|-----------|---------|
| [`autoxing-spellbook-cli/`](autoxing-spellbook-cli/) | CLI spellbook: activate once per shell, then run commands like `get_device_info`, `navigate`, `get_maps`. |
| [`autoxing-spellbook-gui/`](autoxing-spellbook-gui/) | Streamlit control panel (live map, navigation, telemetry, settings). Secondary to the CLI. |

> **Focus:** Primary development and testing target the **CLI**. The GUI is experimental and may have bugs, incomplete flows, or rough edges. For reliable day-to-day work, use the CLI; use the GUI when a visual panel is helpful and you can tolerate issues.

## Quick start

### CLI (terminal)

```bash
cd autoxing-spellbook-cli
uv sync
./setup_bin.sh
cp autoxing/credentials/CONSTANTS.example.yml autoxing/credentials/CONSTANTS.yml
source activate_autoxing.sh
autoxing_help
get_device_info
```

Edit `autoxing/credentials/CONSTANTS.yml` to set your robot IP(s). Full setup, command list, and workflows: [`autoxing-spellbook-cli/README.md`](autoxing-spellbook-cli/README.md).

### GUI (browser)

Experimental — expect bugs; prefer the CLI for production use.

```bash
cd autoxing-spellbook-gui
uv sync
uv run streamlit run app.py
```

Configure robot IP/port in the sidebar or `.streamlit/secrets.toml`. Details: [`autoxing-spellbook-gui/README.md`](autoxing-spellbook-gui/README.md).

## Prerequisites

- Python **3.11+**
- [UV](https://docs.astral.sh/uv/) recommended for dependency install (`uv sync` in each package)
- Autoxing AXBot on the LAN with API port **8090** open

## Extending to other robots

The CLI follows a reusable “spellbook” pattern (thin wrappers + `activate_*` / `setup_bin.sh`). To replicate for another brand, see [`autoxing-spellbook-cli/REPLICATION_GUIDE.md`](autoxing-spellbook-cli/REPLICATION_GUIDE.md).
