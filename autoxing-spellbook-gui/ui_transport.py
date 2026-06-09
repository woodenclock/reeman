"""Page-level helpers: sidebar transport cheat sheet."""

from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st


def ws_endpoint_from_http_base(http_base: str) -> str:
    """Robot HTTP base ``http://host:8090`` → WebSocket endpoint."""
    p = urlparse(http_base.rstrip("/"))
    scheme = "wss" if p.scheme == "https" else "ws"
    return f"{scheme}://{p.netloc}/ws/v2/topics"


def sidebar_transport_guide() -> None:
    """Per-page cheat sheet shown in sidebar (below connection status)."""
    with st.sidebar.expander("Pages & transports", expanded=False):
        st.markdown(
            """
| Group | HTTP | WebSocket |
|-------|------|-----------|
| **Monitor** | Wheel: `POST …/wheel_control/{set_control_mode,set_emergency_stop,clear_errors}`, `POST /services/confirm_estop` | `/battery_state`, `/planning_state`, `/tracked_pose`, `/wheel_state`, `/alerts` |
| **Navigation** | `/chassis/moves*` | *(optional)* `/planning_state` |
| **Maps** | `/maps/*`, `/chassis/current-map`, `/chassis/pose` | `/tracked_pose`, costmaps, … when layers enabled |
| **Services** | `POST /services/*` | read `/wheel_state` on Safety & Control |
| **Advanced** | OpenAPI extras: app store, hostnames, BLE, fleet POSTs | Same as column 1 |

**Maps** and **Navigation** are one sidebar page each (tabs inside). See **Maps → Map library** for activate/delete; **Live canvas** for the interactive floorplan.

Each page shows an **API block** (method badge + path + response JSON).
"""
        )
