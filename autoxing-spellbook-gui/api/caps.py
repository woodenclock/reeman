"""Capability flags from `GET /device/info` → caps (stored in Streamlit session)."""

from __future__ import annotations

from typing import Any

import streamlit as st


def device_caps_from_session() -> dict[str, Any]:
    info = st.session_state.get("device_info") or {}
    caps = info.get("caps") or {}
    return caps if isinstance(caps, dict) else {}


def has_cap(key: str, *, caps: dict[str, Any] | None = None) -> bool:
    c = caps if caps is not None else device_caps_from_session()
    return bool(c.get(key))
