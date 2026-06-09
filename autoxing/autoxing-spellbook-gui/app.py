"""AXBot Streamlit controller — entry point."""

from __future__ import annotations

import streamlit as st

from api.client import ApiError, base_url_from_session, get_client, init_session_state
from api.websocket import ensure_ws_running, stop_ws
from ui_api_block import run_http_block
from ui_transport import sidebar_transport_guide
import live_map
import navigation
import advanced_hub
import services
import settings_page
import telemetry

st.set_page_config(
    page_title="AXBot Controller",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()


def render_sidebar() -> None:
    st.sidebar.title("AXBot Controller")
    st.sidebar.caption("OpenAPI v2.14 · Phase 1")

    st.session_state.robot_ip = st.sidebar.text_input(
        "Robot IP",
        value=st.session_state.robot_ip,
        key="sidebar_robot_ip",
    )
    st.session_state.robot_port = st.sidebar.number_input(
        "Port",
        min_value=1,
        max_value=65535,
        value=int(st.session_state.robot_port),
        step=1,
        key="sidebar_robot_port",
    )

    base = base_url_from_session()
    st.sidebar.code(base, language=None)
    st.sidebar.caption(
        "**Test connection** uses REST `GET /device/info/brief`. "
        "**WebSocket telemetry** opens `ws://…/ws/v2/topics`."
    )

    sidebar_transport_guide()

    if st.sidebar.button("Test connection", use_container_width=True):
        client = get_client(base)
        try:
            with st.sidebar:
                brief = run_http_block("GET", "/device/info/brief", client.ping)
            st.session_state.connection_ok = True
            st.session_state.device_brief = brief
            try:
                info = run_http_block("GET", "/device/info", client.get_device_info)
                st.session_state.device_info = info
            except ApiError:
                st.session_state.device_info = None
            st.sidebar.toast("Connected to robot", icon="✅")
        except ApiError:
            st.session_state.connection_ok = False
            st.session_state.device_brief = None
            st.sidebar.toast("Connection failed", icon="❌")

    if st.session_state.connection_ok is True:
        st.sidebar.success("Online")
    elif st.session_state.connection_ok is False:
        st.sidebar.error("Offline")
    else:
        st.sidebar.info("Not tested")

    brief = st.session_state.device_brief or {}
    if brief:
        name = brief.get("name") or brief.get("robot_name") or "Robot"
        version = brief.get("version") or brief.get("software_version") or "—"
        st.sidebar.markdown(f"**{name}**  \nFirmware: `{version}`")

    st.sidebar.divider()
    st.sidebar.caption("Turn **WebSocket** on for telemetry pages under Monitor.")
    ws_on = st.sidebar.toggle(
        "WebSocket telemetry",
        value=st.session_state.ws_enabled,
        key="sidebar_ws_toggle",
    )
    st.session_state.ws_enabled = ws_on
    st.session_state._ws_base_url = base

    if ws_on:
        mgr = ensure_ws_running(base)
        if mgr.connected:
            st.sidebar.caption("WS: connected")
        elif mgr.last_error:
            st.sidebar.caption(f"WS: reconnecting ({mgr.last_error[:40]}…)")
        else:
            st.sidebar.caption("WS: connecting…")
    else:
        stop_ws(base)
        st.sidebar.caption("WS: off")


pages = {
    "Monitor": [
        st.Page(
            telemetry.render_battery,
            title="Battery",
            icon=":material/battery_full:",
            url_path="battery",
            default=True,
        ),
        st.Page(
            telemetry.render_pose,
            title="Pose",
            icon=":material/location_on:",
            url_path="pose",
        ),
        st.Page(
            telemetry.render_wheel,
            title="Wheel",
            icon=":material/tire_repair:",
            url_path="wheel",
        ),
        st.Page(
            telemetry.render_alerts,
            title="Alerts",
            icon=":material/warning:",
            url_path="alerts",
        ),
    ],
    "Navigation": [
        st.Page(
            navigation.render_navigation_hub,
            title="Navigation",
            icon=":material/navigation:",
            url_path="navigation",
        ),
    ],
    "Maps": [
        st.Page(
            live_map.render_live_map,
            title="Maps & live canvas",
            icon=":material/explore:",
            url_path="maps-hub",
        ),
    ],
    "Services": [
        st.Page(
            services.render_safety,
            title="Safety",
            icon=":material/shield:",
            url_path="svc-safety",
        ),
        st.Page(
            services.render_control,
            title="Control mode",
            icon=":material/tune:",
            url_path="svc-control",
        ),
        st.Page(
            services.render_hardware,
            title="Hardware",
            icon=":material/precision_manufacturing:",
            url_path="svc-hardware",
        ),
        st.Page(
            services.render_calibration,
            title="Calibration",
            icon=":material/science:",
            url_path="svc-calibration",
        ),
        st.Page(
            services.render_power,
            title="Power",
            icon=":material/power_settings_new:",
            url_path="svc-power",
        ),
    ],
    "Advanced": [
        st.Page(
            advanced_hub.render_advanced_hub,
            title="Advanced",
            icon=":material/extension:",
            url_path="advanced",
        ),
    ],
    "Settings": [
        st.Page(
            settings_page.render_effective,
            title="Effective",
            icon=":material/settings:",
            url_path="settings-effective",
        ),
        st.Page(
            settings_page.render_schema,
            title="Schema",
            icon=":material/schema:",
            url_path="settings-schema",
        ),
        st.Page(
            settings_page.render_edit,
            title="Edit",
            icon=":material/edit:",
            url_path="settings-edit",
        ),
        st.Page(
            settings_page.render_device,
            title="Device",
            icon=":material/robot:",
            url_path="settings-device",
        ),
        st.Page(
            settings_page.render_wifi,
            title="Wi-Fi",
            icon=":material/wifi:",
            url_path="settings-wifi",
        ),
    ],
}

render_sidebar()
pg = st.navigation(pages)
pg.run()
