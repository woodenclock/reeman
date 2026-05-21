"""Manual jog — goal-based short moves that approximate joystick control.

The public AXBot REST/WS API does NOT expose continuous velocity teleop
(no /cmd_vel topic, no linear/angular publish). For a true held-joystick
feel, use the official rb-admin web UI. This page issues a fresh
`POST /chassis/moves` (type=standard) on every direction press, with the
target offset from the live `/tracked_pose`. Each press cancels the
in-flight move first so the robot follows the latest command.
"""

from __future__ import annotations

import math

import streamlit as st

from api.client import DEFAULT_CREATOR, ApiError, base_url_from_session, get_client
from api.websocket import get_ws_manager, ws_url_from_base


def _ws_snapshot() -> dict:
    if not st.session_state.get("ws_enabled"):
        return {}
    base = base_url_from_session()
    return get_ws_manager(ws_url_from_base(base)).snapshot()


def _pose_from_snap(snap: dict) -> tuple[float, float, float] | None:
    pose = snap.get("/tracked_pose") or {}
    pos = pose.get("pos")
    ori = pose.get("ori")
    if not pos or len(pos) < 2 or pos[0] is None or pos[1] is None or ori is None:
        return None
    return float(pos[0]), float(pos[1]), float(ori)


def _jog(client, snap: dict, dx_m: float, dy_m: float, dori_rad: float,
         inplace_rotate: bool, current_map_id: int | None) -> None:
    """Compose target from current pose and send a fresh `standard` move.

    dx_m/dy_m are in the robot's body frame (dx forward, dy left).
    For pure rotation in place pass dx=dy=0 and inplace_rotate=True.
    """
    pose = _pose_from_snap(snap)
    if pose is None:
        st.toast("No live /tracked_pose yet — enable WebSocket in the sidebar.", icon="⚠️")
        return
    x, y, h = pose
    target_x = x + dx_m * math.cos(h) - dy_m * math.sin(h)
    target_y = y + dx_m * math.sin(h) + dy_m * math.cos(h)
    target_ori = h + dori_rad

    payload: dict = {
        "creator": DEFAULT_CREATOR,
        "type": "standard",
        "target_x": target_x,
        "target_y": target_y,
        "target_ori": target_ori,
    }
    if inplace_rotate:
        payload["inplace_rotate"] = True

    try:
        client.cancel_current_move()
    except ApiError:
        pass  # no move in flight is fine

    try:
        created = client.create_move(payload)
        mv = created.get("id") if isinstance(created, dict) else None
        if mv is not None:
            st.session_state.active_move_id = mv
        st.toast(f"Jog → move {mv} dispatched", icon="🕹️")
    except ApiError as exc:
        st.toast(f"Jog failed: {exc}", icon="❌")


def _stop(client) -> None:
    try:
        client.cancel_current_move()
        st.toast("Stopped (move cancelled)", icon="🛑")
    except ApiError as exc:
        st.toast(f"Cancel failed: {exc}", icon="❌")


def _readiness(snap: dict, current_map: dict | None) -> list[str]:
    blockers: list[str] = []
    if not snap:
        blockers.append("WebSocket telemetry is off — turn it on in the sidebar to read pose/state.")
    if current_map is None or not current_map.get("id"):
        blockers.append(
            "No active map — activate one under **Maps → Live map** before jogging."
        )
    wheel = snap.get("/wheel_state") or {}
    if wheel.get("emergency_stop_pressed"):
        blockers.append("Emergency stop is engaged — release it first.")
    mode = wheel.get("control_mode")
    if mode and mode != "auto":
        blockers.append(
            f"Wheel control mode is **{mode}** — must be **auto** "
            "(autonomous goal moves are how this page drives the robot)."
        )
    return blockers


def render_manual_control(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Manual jog")
        st.caption(
            "Short `POST /chassis/moves` taps vs live **`/tracked_pose`** · "
            "no continuous /cmd_vel in the public API."
        )
    else:
        st.title("Manual jog")
        st.caption(
            "Tap-to-jog dpad. Each button issues a short `POST /chassis/moves` "
            "relative to the live pose. **The public AXBot API has no continuous "
            "velocity / joystick endpoint** — for held-stick teleop use the official "
            "rb-admin web UI. Wheel control mode must be **auto** (not `manual`/`remote`) "
            "because we drive via autonomous goal moves."
        )

    client = get_client(base_url_from_session())
    snap = _ws_snapshot()

    current_map: dict = {}
    try:
        current_map = client.get_current_map() or {}
    except ApiError:
        pass

    pose = _pose_from_snap(snap) or (None, None, None)
    wheel = snap.get("/wheel_state") or {}
    planning = snap.get("/planning_state") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Control mode", wheel.get("control_mode") or "—")
    c2.metric("E-stop", "PRESSED" if wheel.get("emergency_stop_pressed") else "clear")
    c3.metric("Move state", planning.get("move_state") or "—")
    if pose[2] is not None:
        c4.metric("Heading", f"{math.degrees(pose[2]):.1f}°")
    else:
        c4.metric("Heading", "—")

    blockers = _readiness(snap, current_map)
    if blockers:
        st.error("Jog blocked:\n\n- " + "\n- ".join(blockers))

    st.divider()

    c_lin, c_ang = st.columns(2)
    with c_lin:
        step_m = st.slider(
            "Linear step (m)", 0.05, 1.0,
            value=st.session_state.get("manual_step_m", 0.30),
            step=0.05, key="manual_step_m",
            help="Forward / Back distance per press",
        )
    with c_ang:
        step_deg = st.slider(
            "Angular step (°)", 5, 90,
            value=st.session_state.get("manual_step_deg", 30),
            step=5, key="manual_step_deg",
            help="In-place rotation per press",
        )
    step_rad = math.radians(step_deg)

    disabled = bool(blockers)

    _, up_col, _ = st.columns(3)
    if up_col.button(
        f"▲  Forward  +{step_m:.2f} m",
        key="jog_fwd", use_container_width=True, disabled=disabled, type="primary",
        help="POST /chassis/moves with target = current_pose + step·(cos h, sin h)",
    ):
        _jog(client, snap, +step_m, 0.0, 0.0, inplace_rotate=False,
             current_map_id=current_map.get("id"))
        st.rerun()

    l_col, stop_col, r_col = st.columns(3)
    if l_col.button(
        f"↺  CCW  +{step_deg}°",
        key="jog_ccw", use_container_width=True, disabled=disabled,
        help="In-place rotation (inplace_rotate=true, top-level per official docs)",
    ):
        _jog(client, snap, 0.0, 0.0, +step_rad, inplace_rotate=True,
             current_map_id=current_map.get("id"))
        st.rerun()
    if stop_col.button(
        "■  STOP",
        key="jog_stop", use_container_width=True, type="primary",
        help="PATCH /chassis/moves/current {state: cancelled} — always available",
    ):
        _stop(client)
        st.rerun()
    if r_col.button(
        f"↻  CW  −{step_deg}°",
        key="jog_cw", use_container_width=True, disabled=disabled,
        help="In-place rotation (inplace_rotate=true, top-level per official docs)",
    ):
        _jog(client, snap, 0.0, 0.0, -step_rad, inplace_rotate=True,
             current_map_id=current_map.get("id"))
        st.rerun()

    _, dn_col, _ = st.columns(3)
    if dn_col.button(
        f"▼  Back  −{step_m:.2f} m",
        key="jog_back", use_container_width=True, disabled=disabled,
        help="POST /chassis/moves with target = current_pose − step·(cos h, sin h)",
    ):
        _jog(client, snap, -step_m, 0.0, 0.0, inplace_rotate=False,
             current_map_id=current_map.get("id"))
        st.rerun()

    st.divider()
    with st.expander("How this works", expanded=False):
        st.markdown(
            "- **Forward / Back** → `POST /chassis/moves` `type: standard` "
            "with `target_x, target_y, target_ori`. The target is the live "
            "`/tracked_pose` offset by `step` along the robot's heading.\n"
            "- **CCW / CW** → same endpoint, same position, `target_ori` "
            "rotated by `step°`, plus top-level `inplace_rotate: true` so "
            "the robot spins without translating.\n"
            "- **STOP** → `PATCH /chassis/moves/current` with "
            "`{state: cancelled}`. Always enabled even when blocked.\n"
            "- Every direction press first cancels the current move so the "
            "robot follows the freshest command, giving a stutter-tap "
            "joystick feel."
        )
