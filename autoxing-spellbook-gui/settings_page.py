"""System settings and device information — one page per section."""

from __future__ import annotations

import json

import streamlit as st

from api.client import ApiError, base_url_from_session, get_client
from ui_api_block import api_block


def render_effective() -> None:
    st.title("Effective settings")
    st.caption("Resolved stack from **`GET /system/settings/effective`** (defaults + overlays).")
    client = get_client(base_url_from_session())
    data = {}
    err: ApiError | None = None
    try:
        data = client.get_settings_effective() or {}
    except ApiError as exc:
        err = exc

    if isinstance(data, dict) and data:
        st.metric("Top-level sections", len(data))
        peek = ", ".join(list(data.keys())[:6])
        st.caption(f"Keys preview: **`{peek}**{'…' if len(data) > 6 else ''}")
    elif not err:
        st.info("Effective payload empty or not yet loaded.")

    st.divider()
    if err:
        api_block(
            "GET",
            "/system/settings/effective",
            response=err.body,
            error=str(err),
        )
    else:
        api_block("GET", "/system/settings/effective", response=data)


def render_schema() -> None:
    st.title("Settings schema")
    st.markdown("Discover PATCHable **`user`** knobs before editing — **`GET /system/settings/schema`**.")
    client = get_client(base_url_from_session())
    data = {}
    err: ApiError | None = None
    try:
        data = client.get_settings_schema() or {}
    except ApiError as exc:
        err = exc

    if isinstance(data, dict) and data:
        st.metric("Schema keys reported", len(data))
    elif not err:
        st.caption("No schema body returned.")

    st.divider()
    if err:
        api_block("GET", "/system/settings/schema", response=err.body, error=str(err))
    else:
        api_block("GET", "/system/settings/schema", response=data)


def render_edit() -> None:
    st.title("Edit settings")
    st.markdown(
        "**`PATCH /system/settings/user`** accepts a sparse JSON object. Validate names against "
        "**Schema**, then paste the diff below."
    )
    client = get_client(base_url_from_session())

    patch_raw = st.text_area(
        "JSON patch object",
        value='{\n  "example_key": "example_value"\n}',
        height=160,
    )
    patch: dict | None
    try:
        loaded = json.loads(patch_raw)
        patch = loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        patch = None

    if st.button("Apply patch", type="primary", use_container_width=True):
        if patch is None:
            st.toast("Invalid JSON — must be an object", icon="❌")
        else:
            try:
                client.patch_settings_user(patch)
                st.toast("Settings patched", icon="✅")
            except ApiError:
                st.toast("Patch failed", icon="❌")

    st.divider()

    if patch is None:
        api_block(
            "PATCH",
            "/system/settings/user",
            request={"…": "fix JSON above"},
            note="Body must be a JSON object matching schema fields.",
        )
    else:
        api_block(
            "PATCH",
            "/system/settings/user",
            request=patch,
            note="Press **Apply patch** to send this object.",
        )


def render_device() -> None:
    st.title("Device info")
    st.caption("Capabilities gating — many optional routes require flags from **`GET /device/info`**.")
    client = get_client(base_url_from_session())
    info: dict = {}
    err: ApiError | None = None
    try:
        info = client.get_device_info() or {}
        st.session_state.device_info = info
    except ApiError as exc:
        err = exc
        st.session_state.device_info = None

    if err:
        st.warning(str(err))
    elif info:
        c1, c2, c3 = st.columns(3)
        c1.metric("Model", info.get("model") or info.get("name") or "—")
        c2.metric("Version", info.get("version") or "—")
        caps = info.get("caps") or {}
        c3.metric("Capability flags", len(caps))

    st.divider()
    if err:
        api_block("GET", "/device/info", response=err.body, error=str(err))
    else:
        api_block("GET", "/device/info", response=info)


def render_wifi() -> None:
    st.title("Wi-Fi")
    st.markdown(
        "**`GET /device/wifi_info`** for association state; **`GET /device/available_wifis`** for scan "
        "results (timing depends on MCU)."
    )
    client = get_client(base_url_from_session())

    wf: dict = {}
    wf_err: ApiError | None = None
    try:
        wf = client.get_wifi_info() or {}
    except ApiError as exc:
        wf_err = exc

    nets: list = []
    nets_err: ApiError | None = None
    try:
        nets = client.list_available_wifis() or []
    except ApiError as exc:
        nets_err = exc

    if wf and not wf_err:
        st.json(wf)
    elif not wf_err:
        st.caption("No STA info returned.")

    if nets_err:
        st.warning(f"Scan unavailable: **{nets_err}**")
    elif nets:
        st.metric("Networks in last scan", len(nets))
        st.dataframe(nets, use_container_width=True, hide_index=True)
    else:
        st.caption("No scan rows — robot may still be scanning.")

    st.divider()

    if wf_err:
        api_block("GET", "/device/wifi_info", response=wf_err.body, error=str(wf_err))
    else:
        api_block("GET", "/device/wifi_info", response=wf if wf else None)

    if nets_err:
        api_block(
            "GET",
            "/device/available_wifis",
            response=nets_err.body,
            error=str(nets_err),
        )
    else:
        api_block("GET", "/device/available_wifis", response=nets if nets else None)
