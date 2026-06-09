# AXBot Streamlit Controller

Phase 1 control panel for the Autoxing AXBot REST API ([`openapi.yaml`](../autoxing-spellbook-cli/openapi.yaml)).

> **Notice:** This GUI is **not** the main focus of the repo. Development and testing prioritize [`autoxing-spellbook-cli`](../autoxing-spellbook-cli/). The Streamlit app is experimental — you may hit bugs, missing features, or unstable behavior. For dependable robot operations, use the CLI spellbook first.

## Prerequisites

- [UV](https://docs.astral.sh/uv/)
- Robot reachable at `http://<ip>:8090` on the LAN

## Setup

```bash
cd autoxing-spellbook-gui
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
uv sync
```

## Run

```bash
uv run streamlit run app.py
```

Open the URL shown in the terminal (default `http://localhost:3000`).

## Configuration

Edit `.streamlit/secrets.toml`:

```toml
robot_ip = "192.168.25.25"
robot_port = 8090
```

You can override the IP in the app sidebar without editing the file.
