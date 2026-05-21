"""Robot service quick actions — one page per section."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from api.client import ApiError, base_url_from_session, get_client, suggests_software_emergency_stop_unsupported
from api.websocket import get_ws_manager, ws_url_from_base
from ui_api_block import api_block, ws_topic_block

CONTROL_MODES = ["auto", "manual", "remote"]


def _wheel_snapshot() -> dict:
    if not st.session_state.get("ws_enabled"):
        return {}
    base = base_url_from_session()
    return get_ws_manager(ws_url_from_base(base)).get("/wheel_state") or {}


def _invoke_service(
    label: str,
    fn,
    *,
    on_success: Callable[[], None] | None = None,
    on_api_error: Callable[[ApiError], None] | None = None,
) -> None:
    """Run a callable; toast outcome + optional callbacks (cards live below each page)."""
    try:
        fn()
        st.toast(f"{label} — ok", icon="✅")
        if on_success:
            on_success()
    except ApiError as exc:
        st.warning(str(exc))
        st.toast("Request failed", icon="❌")
        if on_api_error:
            on_api_error(exc)


@st.dialog("Restart robot services?")
def confirm_restart() -> None:
    st.warning("All robot software services will restart.")
    if st.button("Restart", type="primary"):
        _invoke_service(
            "Restart services",
            lambda: get_client(base_url_from_session()).restart_service(),
        )
        st.rerun()


@st.dialog("Shut down or reboot?")
def confirm_shutdown() -> None:
    st.warning("This affects the main computing unit.")
    reboot = st.checkbox("Reboot (uncheck for shutdown)", value=True)
    if st.button("Confirm", type="primary"):
        _invoke_service(
            "Shutdown" if not reboot else "Reboot",
            lambda: get_client(base_url_from_session()).shutdown(reboot=reboot),
        )
        st.rerun()


def render_safety() -> None:
    st.title("Safety")
    st.markdown(
        "Emergency stop and wheel fault clearing mirror **`/services/wheel_control/*`** helpers. "
        "Live **`/wheel_state`** (when WebSocket is on) aligns with **`POST`** payloads below."
    )
    client = get_client(base_url_from_session())

    wheel = _wheel_snapshot()
    estop_pressed = wheel.get("emergency_stop_pressed", False)
    mode = wheel.get("control_mode", "—")

    sw_hint = st.session_state.get("wheel_sw_estop_supported")
    if sw_hint is False:
        st.info(
            "Software **`set_emergency_stop`** was reported **unsupported** for this chassis. "
            "Use hardware e-stop · see **Monitor → Wheel** to retry after firmware changes."
        )

    z1, z2 = st.columns(2)
    z1.metric("E-stop pressed (WS)", "Yes" if estop_pressed else "No")
    z2.metric("Control mode (WS)", str(mode))

    st.caption(
        "**Tip:** Toggle **WebSocket telemetry** for live **`/wheel_state`** that matches post-call "
        "states (minus wire delay)."
    )

    estop_blocked = sw_hint is False
    estop_enable = st.toggle(
        "Next POST body · enable emergency_stop",
        value=estop_pressed,
        disabled=estop_blocked,
    )
    estop_body = {"enable": bool(estop_enable)}

    def _remember_estop_ok() -> None:
        st.session_state.wheel_sw_estop_supported = True

    def _maybe_remember_estop_unsupported(exc: ApiError) -> None:
        if suggests_software_emergency_stop_unsupported(exc):
            st.session_state.wheel_sw_estop_supported = False

    sb1, sb2, sb3 = st.columns(3)
    with sb1:
        if st.button("Apply E-stop state", use_container_width=True, disabled=estop_blocked):
            _invoke_service(
                "Set emergency stop",
                lambda: client.set_emergency_stop(bool(estop_enable)),
                on_success=_remember_estop_ok,
                on_api_error=_maybe_remember_estop_unsupported,
            )
    with sb2:
        if st.button("Confirm E-stop", use_container_width=True):
            _invoke_service("Confirm E-stop", client.confirm_estop)
    with sb3:
        if st.button("Clear wheel errors", use_container_width=True):
            _invoke_service("Clear wheel errors", client.clear_wheel_errors)

    st.divider()

    ws_topic_block("/wheel_state", wheel)

    api_block(
        "POST",
        "/services/wheel_control/set_emergency_stop",
        request=estop_body,
        note='Press **Apply E-stop state** to send `{ "enable": boolean }`.',
        empty_label="Payload shown above mirrors the toggle.",
    )
    api_block("POST", "/services/confirm_estop", note='Body typically empty — **`POST`** on press.')
    api_block("POST", "/services/wheel_control/clear_errors", note='Clear hardware wheel faults.')


def render_control() -> None:
    st.title("Control mode")
    st.markdown(
        "Switch **`auto` / `manual` / `remote`** via **`POST /services/wheel_control/set_control_mode`**. "
        "Mirrors **`control_mode`** in **`/wheel_state`** when subscribed."
    )
    client = get_client(base_url_from_session())

    wheel = _wheel_snapshot()
    current_mode = wheel.get("control_mode", "—")

    st.metric("Observed control mode (`/wheel_state`)", current_mode)

    mode = st.segmented_control(
        "Next POST payload · control_mode",
        CONTROL_MODES,
        default=current_mode if current_mode in CONTROL_MODES else "auto",
        selection_mode="single",
    )
    body = {"control_mode": mode}

    if st.button("Apply control mode", use_container_width=True) and mode:
        _invoke_service(
            "Set control mode",
            lambda: client.set_control_mode(mode),
        )

    st.divider()

    ws_topic_block("/wheel_state", wheel)
    api_block(
        "POST",
        "/services/wheel_control/set_control_mode",
        request=body,
        note='Sends **`{ "control_mode": ... }`** from the segmented control.',
    )


def render_hardware() -> None:
    st.title("Hardware")
    st.markdown(
        "Jack, roller transport, wake — **`POST /services/{jack_up,...}`**. "
        "**Idempotent-ish** presses; failures surface as toasts plus JSON in the footer."
    )
    client = get_client(base_url_from_session())
    actions = [
        ("Jack up", "/services/jack_up", client.jack_up),
        ("Jack down", "/services/jack_down", client.jack_down),
        ("Roller load", "/services/roller_load", client.roller_load),
        ("Roller unload", "/services/roller_unload", client.roller_unload),
    ]
    h1, h2, h3, h4 = st.columns(4)
    for col, (label, path, fn) in zip((h1, h2, h3, h4), actions):
        with col:
            if st.button(label):
                _invoke_service(label, fn)

    wu1, _wu2 = st.columns([1, 3])
    with wu1:
        if st.button("Wake up device", use_container_width=True):
            _invoke_service("Wake up", client.wake_up_device)

    st.divider()

    for label, path, _fn in actions:
        api_block("POST", path, note=f'Press **`{label}`** above.')

    api_block(
        "POST",
        "/services/wake_up_device",
        note="Bring peripherals out of low-power standby.",
    )


def render_calibration() -> None:
    st.title("Calibration")
    st.markdown(
        "**`POST`** IMU depth or gyro pipelines; some runs take several seconds on-robot. "
        "Watch toasts for completion."
    )
    client = get_client(base_url_from_session())
    cal_actions = [
        ("IMU recalibrate", "/services/imu/recalibrate", client.recalibrate_imu),
        ("Calibrate depth cameras", "/services/calibrate_depth_cameras", client.calibrate_depth_cameras),
        ("Calibrate gyro scale", "/services/imu/calibrate_gyro_scale", client.calibrate_gyro_scale),
    ]
    c1, c2, c3 = st.columns(3)
    for col, (label, path, fn) in zip((c1, c2, c3), cal_actions):
        with col:
            if st.button(label, use_container_width=True):
                _invoke_service(label, fn)

    st.divider()

    for label, path, _fn in cal_actions:
        api_block("POST", path, note=f'Press **`{label}`** above.')


def render_power() -> None:
    st.title("Power")
    st.markdown(
        "Software restart vs baseboard **`shutdown`** differ: restart recycles ROS stacks; **`shutdown`** "
        "powers off MCUs (**confirm dialogs**)."
    )

    pw1, pw2 = st.columns(2)
    with pw1:
        if st.button("Restart services", use_container_width=True):
            confirm_restart()
    with pw2:
        if st.button("Shutdown / reboot…", use_container_width=True):
            confirm_shutdown()

    st.divider()

    api_block(
        "POST",
        "/services/restart_service",
        note="Opens **Restart robot services?** when you press the first button.",
    )
    api_block(
        "POST",
        "/services/baseboard/shutdown",
        request={"target": "main_computing_unit", "reboot": True},
        note="Modal checkbox switches **reboot** true/false before **POST**.",
    )
