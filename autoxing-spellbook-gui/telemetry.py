"""WebSocket telemetry — one page per topic group."""

from __future__ import annotations

import streamlit as st

from api.client import (
    ApiError,
    base_url_from_session,
    get_client,
    suggests_software_emergency_stop_unsupported,
)
from api.websocket import get_ws_manager, ws_url_from_base
from ui_api_block import api_block, ws_topic_block

MOVE_STATE_COLORS = {
    "idle": "gray",
    "moving": "blue",
    "succeeded": "green",
    "failed": "red",
    "cancelled": "orange",
}


def _ws_snapshot() -> dict:
    if not st.session_state.get("ws_enabled"):
        return {}
    base = base_url_from_session()
    return get_ws_manager(ws_url_from_base(base)).snapshot()


def _ws_guard(title: str, blurb: str) -> bool:
    st.title(title)
    st.caption(blurb)
    if not st.session_state.get("ws_enabled"):
        st.warning(
            "Turn on **WebSocket telemetry** in the sidebar to receive live topic data."
        )
        st.divider()
        return False
    return True


CONTROL_MODES = ["auto", "manual", "remote"]


def _wheel_http_invoke(label: str, fn) -> None:
    try:
        fn()
        st.toast(f"{label} — ok", icon="✅")
    except ApiError as exc:
        st.warning(str(exc))
        st.toast("Request failed", icon="❌")


@st.fragment(run_every="1s")
def _fragment_battery() -> None:
    snap = _ws_snapshot()
    battery = snap.get("/battery_state") or {}
    planning = snap.get("/planning_state") or {}

    pct = battery.get("percentage")
    voltage = battery.get("voltage")
    supply = battery.get("power_supply_status", "—")
    move_state = planning.get("move_state", "—")
    remaining = planning.get("remaining_distance")
    action_id = planning.get("action_id")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Battery",
        f"{pct * 100:.0f}%" if pct is not None else "—",
        delta=str(supply) if supply not in ("", "—") else None,
        help="From `/battery_state` · `percentage` is 0–1",
    )
    c2.metric("Voltage", f"{voltage:.2f} V" if voltage is not None else "—")
    c3.metric("Remaining distance", f"{remaining:.2f} m" if remaining is not None else "—")
    c4.metric("Move state", str(move_state))
    r1, r2 = st.columns([1, 4])
    with r1:
        st.badge(
            str(move_state),
            icon=":material/smart_toy:",
            color=MOVE_STATE_COLORS.get(str(move_state), "gray"),
        )
    if action_id is not None:
        with r2:
            st.caption(f"Active action · `action_id`: **{action_id}**")

    st.divider()
    ws_topic_block("/battery_state", battery)
    ws_topic_block("/planning_state", planning)


def render_battery() -> None:
    if not _ws_guard(
        "Battery & planning",
        "Live charge and planner status from **`/battery_state`** and **`/planning_state`**.",
    ):
        ws_topic_block("/battery_state", None)
        ws_topic_block("/planning_state", None)
        return
    _fragment_battery()


@st.fragment(run_every="1s")
def _fragment_pose() -> None:
    pose = _ws_snapshot().get("/tracked_pose") or {}
    pos = pose.get("pos") or [None, None]
    ori = pose.get("ori")

    p1, p2, p3 = st.columns(3)
    p1.metric("X (m)", f"{pos[0]:.3f}" if pos[0] is not None else "—")
    p2.metric("Y (m)", f"{pos[1]:.3f}" if pos[1] is not None else "—")
    p3.metric("Heading (rad)", f"{ori:.4f}" if ori is not None else "—")
    st.caption("World-frame meters; **`ori`** radians counter-clockwise from East.")

    st.divider()
    ws_topic_block("/tracked_pose", pose)


def render_pose() -> None:
    if not _ws_guard("Pose", "Robot pose stream from **`/tracked_pose`**."):
        ws_topic_block("/tracked_pose", None)
        return
    _fragment_pose()


@st.fragment(run_every="1s")
def _fragment_wheel_live() -> None:
    """Live fields from WS `/wheel_state` — matches OpenAPI `components.schemas./wheel_state`."""
    wheel = _ws_snapshot().get("/wheel_state") or {}
    mode = wheel.get("control_mode", "—")
    estop = wheel.get("emergency_stop_pressed", False)
    released = wheel.get("wheels_released")

    r1, r2, r3 = st.columns(3)
    r1.metric("Control mode (`/wheel_state`)", str(mode))
    with r2:
        st.markdown("Hardware e-stop pressed")
        st.badge("Yes · latched" if estop else "Clear", color="red" if estop else "green")
    r3.metric(
        "Wheels released (≥ v2.9)",
        (
            "Yes"
            if released is True
            else ("No" if released is False else "— (field absent)")
        ),
    )

    err = wheel.get("error_msg") or wheel.get("error")
    if isinstance(err, str) and err.strip():
        st.warning(err)

    st.caption(
        "**OpenAPI · Services:** `POST /services/wheel_control/set_control_mode` "
        "`(auto | manual | remote)`, `POST …/set_emergency_stop`, `POST …/clear_errors`, "
        "`POST /services/confirm_estop`. Results follow on **`/wheel_state`**."
    )


@st.fragment(run_every="1s")
def _fragment_wheel_ws_json() -> None:
    ws_topic_block(
        "/wheel_state",
        _ws_snapshot().get("/wheel_state") or {},
        note="Includes `control_mode`, `emergency_stop_pressed`, optional **`wheels_released`**.",
    )


def render_wheel() -> None:
    st.title("Wheel")
    st.markdown(
        "Monitor **`/wheel_state`** and send the **`/services/wheel_control/*`** + **`confirm_estop`** "
        "calls described in **`openapi.yaml`** (Services tag)."
    )

    sw_estop_ok = st.session_state.get("wheel_sw_estop_supported")
    if sw_estop_ok is False:
        st.info(
            "This robot reported **software emergency stop** (`POST …/set_emergency_stop`) as **unsupported**. "
            "Rely on the **physical e-stop**; **`/wheel_state`** can still reflect `emergency_stop_pressed`."
        )
        with st.expander("Retry software e-stop (e.g. after firmware upgrade)"):
            if st.button("Clear local unsupported hint", key="wheel_clear_estop_hint"):
                st.session_state.wheel_sw_estop_supported = None
                st.rerun()

    ws_on = bool(st.session_state.get("ws_enabled"))
    if ws_on:
        _fragment_wheel_live()
    else:
        st.warning("Turn on **WebSocket telemetry** in the sidebar to stream **`/wheel_state`**.")

    client = get_client(base_url_from_session())
    ws_snap = (_ws_snapshot().get("/wheel_state") or {}) if ws_on else {}
    observed = ws_snap.get("control_mode") if ws_on else None
    default_mode = observed if observed in CONTROL_MODES else "auto"

    st.subheader("Change control mode")
    mode_pick = st.segmented_control(
        "`POST …/wheel_control/set_control_mode` · `control_mode`",
        CONTROL_MODES,
        default=default_mode,
        selection_mode="single",
        key="wheel_page_control_mode",
    )
    if st.button("Apply control mode", type="primary", use_container_width=True):
        if mode_pick:
            _wheel_http_invoke(
                "Set control mode",
                lambda m=mode_pick: client.set_control_mode(str(m)),
            )

    estop_pick = st.toggle(
        "Next **`set_emergency_stop`** body · `enable`",
        value=bool(ws_snap.get("emergency_stop_pressed")) if ws_on else False,
        key="wheel_page_estop_enable",
        disabled=sw_estop_ok is False,
    )
    estop_body = {"enable": estop_pick}
    if st.button(
        "Apply emergency stop enable",
        use_container_width=True,
        disabled=sw_estop_ok is False,
    ):
        try:
            client.set_emergency_stop(bool(estop_pick))
            st.session_state.wheel_sw_estop_supported = True
            st.toast("Set emergency stop — ok", icon="✅")
        except ApiError as exc:
            st.warning(str(exc))
            if suggests_software_emergency_stop_unsupported(exc):
                st.session_state.wheel_sw_estop_supported = False
            st.toast("Request failed", icon="❌")

    bw1, bw2 = st.columns(2)
    if bw1.button("Clear wheel errors", use_container_width=True):
        _wheel_http_invoke("Clear wheel errors", client.clear_wheel_errors)
    if bw2.button("Confirm e-stop (`confirm_estop`)", use_container_width=True):
        _wheel_http_invoke("Confirm e-stop", client.confirm_estop)

    st.divider()
    if ws_on:
        _fragment_wheel_ws_json()
    else:
        ws_topic_block("/wheel_state", None)

    st.caption("**REST request bodies** (mirrors OpenAPI schemas)")
    mode_body = {"control_mode": mode_pick or "auto"}
    api_block(
        "POST",
        "/services/wheel_control/set_control_mode",
        request=mode_body,
        note="Enum: **`auto`** · **`manual`** · **`remote`**.",
        empty_label="Payload matches segmented control.",
    )
    api_block(
        "POST",
        "/services/wheel_control/set_emergency_stop",
        request=estop_body,
        empty_label="{ enable: boolean }",
    )
    api_block(
        "POST",
        "/services/wheel_control/clear_errors",
        note="Clears latched wheel control faults when safe.",
        empty_label="Typically empty POST body.",
    )
    api_block(
        "POST",
        "/services/confirm_estop",
        note="Confirm wheel release on slopes during e-stop (**v2.11.0+**).",
        empty_label="Typically empty POST body.",
    )


@st.fragment(run_every="1s")
def _fragment_alerts() -> None:
    alerts_msg = _ws_snapshot().get("/alerts") or {}
    alert_list = alerts_msg.get("alerts") if isinstance(alerts_msg, dict) else []

    if alert_list:
        st.markdown(f"**{len(alert_list)}** active alert(s) in the last message.")
        rows = [
            {
                "level": a.get("level"),
                "code": a.get("code"),
                "message": a.get("msg") or a.get("message"),
            }
            for a in alert_list
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("No alerts in the latest `/alerts` payload.")

    st.divider()
    ws_topic_block("/alerts", alerts_msg)


def render_alerts() -> None:
    if not _ws_guard("Alerts", "Fault and notice stream from **`/alerts`**."):
        ws_topic_block("/alerts", None)
        return
    _fragment_alerts()
