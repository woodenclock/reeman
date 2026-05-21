"""API endpoint blocks: method badge, path, request/response cards."""

from __future__ import annotations

import json
from typing import Any, Callable

import streamlit as st

from api.client import ApiError

METHOD_COLORS: dict[str, str] = {
    "GET": "blue",
    "POST": "green",
    "PATCH": "orange",
    "PUT": "orange",
    "DELETE": "red",
    "WS": "violet",
}


def method_badge(method: str) -> None:
    m = method.upper()
    st.badge(m, color=METHOD_COLORS.get(m, "gray"))


def api_block(
    method: str,
    path: str,
    *,
    response: Any = None,
    request: Any = None,
    error: str | None = None,
    note: str | None = None,
    empty_label: str = "No data yet — run an action or enable telemetry.",
) -> None:
    """Bordered block: method badge + path + optional request + response card."""
    with st.container(border=True):
        head_l, head_r = st.columns([0.14, 0.86], vertical_alignment="center")
        with head_l:
            method_badge(method)
        with head_r:
            st.markdown(f"**`{path}`**")
        if note:
            st.caption(note)
        if request is not None:
            st.markdown("**Request**")
            st.json(request)
        st.markdown("**Response**")
        if error:
            st.error(error)
            if response is not None:
                st.json(response)
        elif response is not None:
            st.json(response)
        else:
            st.caption(empty_label)


def ws_topic_block(topic: str, payload: Any, *, note: str | None = None) -> None:
    api_block(
        "WS",
        topic,
        response=payload if payload else None,
        note=note or "WebSocket `/ws/v2/topics` · `enable_topic` subscription",
        empty_label="Waiting for topic message — enable WebSocket in the sidebar.",
    )


def run_http_block(
    method: str,
    path: str,
    fn: Callable[[], Any],
    *,
    request: Any = None,
    note: str | None = None,
) -> Any:
    """Execute `fn`, render api_block with result or error. Re-raises ApiError."""
    try:
        result = fn()
        api_block(method, path, request=request, response=result, note=note)
        return result
    except ApiError as exc:
        api_block(
            method,
            path,
            request=request,
            response=exc.body,
            error=str(exc),
            note=note,
        )
        raise


def response_preview(data: Any, *, max_chars: int = 8000) -> Any:
    """Trim huge payloads for display (e.g. map overlays string)."""
    if data is None:
        return None
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            if k == "overlays" and isinstance(v, str) and len(v) > max_chars:
                out[k] = f"<GeoJSON string, {len(v)} chars — see Overlays page>"
            else:
                out[k] = v
        return out
    text = json.dumps(data) if not isinstance(data, str) else data
    if len(text) > max_chars:
        return f"<payload truncated, {len(text)} chars>"
    return data
