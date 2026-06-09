"""Send and monitor chassis moves — standalone pages or grouped hub (tabs)."""

from __future__ import annotations

import math

import streamlit as st

import manual_control
from api.client import (
    DEFAULT_CREATOR,
    MOVE_TYPES,
    TERMINAL_MOVE_STATES,
    ApiError,
    base_url_from_session,
    get_client,
)
from api.websocket import ensure_ws_running
from ui_api_block import api_block, run_http_block

MOVE_STATE_COLORS = {
    "idle": "gray",
    "moving": "blue",
    "succeeded": "green",
    "failed": "red",
    "cancelled": "orange",
}


@st.fragment(run_every=0.33)
def _follow_target_ws_fragment() -> None:
    """Publish ``/follow_target_state`` at ~3 Hz from live ``/tracked_pose``."""
    if not st.session_state.get("nav_follow_publish_tracked"):
        return
    if not st.session_state.get("ws_enabled"):
        return
    base = base_url_from_session()
    mgr = ensure_ws_running(base)
    pose = mgr.get("/tracked_pose") or {}
    pos = pose.get("pos")
    ori = pose.get("ori")
    if not pos or len(pos) < 2 or ori is None:
        return
    mgr.send_ws_message(
        {
            "topic": "/follow_target_state",
            "follow_state": "follow_pose",
            "target_pose": {"pos": [float(pos[0]), float(pos[1])], "ori": float(ori)},
        }
    )


@st.dialog("Cancel current move?")
def confirm_cancel_move() -> None:
    st.warning("This will stop the robot's current navigation task.")
    if st.button("Yes, cancel move", type="primary"):
        client = get_client(base_url_from_session())
        try:
            with st.spinner("Cancelling…"):
                run_http_block(
                    "PATCH",
                    "/chassis/moves/current",
                    lambda: client.cancel_current_move(),
                    request={"state": "cancelled"},
                )
            st.session_state.active_move_id = None
            st.toast("Move cancelled", icon="✅")
        except ApiError:
            st.toast("Cancel failed", icon="❌")
        st.rerun()


@st.fragment(run_every="2s")
def _active_move_poll(*, compact: bool = False) -> None:
    move_id = st.session_state.get("active_move_id")
    if not move_id:
        hint = (
            "Send one from the **Send move** tab or **Maps → Live map**."
            if compact
            else "Send one from **Send move** or **Maps → Live map**."
        )
        st.info(f"No active move tracked. {hint}")
        if st.session_state.get("connection_ok"):
            st.caption("After dispatch, progress and JSON below refresh every **2 s**.")
        st.divider()
        api_block(
            "GET",
            "/chassis/moves/{id}",
            note="Shown when tracking a move id from the session.",
            empty_label="No active move — send one from the Send move page.",
        )
        return

    path = f"/chassis/moves/{move_id}"
    client = get_client(base_url_from_session())
    try:
        detail = client.get_move(int(move_id))
    except ApiError as exc:
        st.warning("Lost move payload — check robot connection.")
        st.divider()
        api_block("GET", path, response=exc.body, error=str(exc))
        return

    state = detail.get("state", "—")
    st.markdown(f"**Move `{move_id}`** · planner state")
    prog = (
        0.5
        if state == "moving"
        else (1.0 if state in TERMINAL_MOVE_STATES else 0.0)
    )
    st.progress(prog)
    st.badge(state, color=MOVE_STATE_COLORS.get(state, "gray"))
    if detail.get("fail_reason_str"):
        st.caption(detail["fail_reason_str"])
    cx, cy, co = detail.get("target_x"), detail.get("target_y"), detail.get("target_ori")
    if any(v is not None for v in (cx, cy, co)):
        st.caption(
            f"Goal · X **{cx}** · Y **{cy}** · ori **{co}** (units as returned by the API)"
        )

    if state in TERMINAL_MOVE_STATES:
        st.session_state.active_move_id = None
        if state == "succeeded":
            st.toast(f"Move {move_id} succeeded", icon="✅")
        elif state == "failed":
            st.toast(f"Move {move_id} failed", icon="❌")

    st.divider()
    api_block("GET", path, response=detail, note="Auto-refresh every 2 s.")


def _build_move_payload(move_type: str, creator: str) -> dict:
    """Render type-specific inputs and return the payload per official docs.

    https://autoxingtech.github.io/axbot_rest_book/reference/moves.html
    """
    payload: dict = {"creator": creator, "type": move_type}

    if move_type == "standard":
        use_degrees = st.toggle("Orientation in degrees", value=False, key="send_std_deg")
        c1, c2, c3 = st.columns(3)
        payload["target_x"] = c1.number_input("Target X (m)", value=0.0, format="%.3f",
                                              key="send_std_x")
        payload["target_y"] = c2.number_input("Target Y (m)", value=0.0, format="%.3f",
                                              key="send_std_y")
        ori_val = c3.number_input(
            "Target orientation", value=0.0, format="%.3f", key="send_std_ori",
            help="Radians CCW from East, unless degrees toggle is on",
        )
        payload["target_ori"] = math.radians(ori_val) if use_degrees else ori_val

        with st.expander("Advanced (standard)", expanded=False):
            c4, c5 = st.columns(2)
            acc = c4.number_input(
                "target_accuracy (m)", value=0.0, format="%.3f", min_value=0.0,
                key="send_std_acc",
                help="0 = leave unset (server default).",
            )
            if acc > 0:
                payload["target_accuracy"] = acc
            use_zone = c5.checkbox(
                "use_target_zone", value=False, key="send_std_zone",
                help="Auto-succeed once within target_accuracy radius.",
            )
            if use_zone:
                payload["use_target_zone"] = True
            inplace = st.checkbox(
                "inplace_rotate", value=False, key="send_std_inplace",
                help="Strictly rotate without any linear velocity (v2.11.0+).",
            )
            if inplace:
                payload["inplace_rotate"] = True

    elif move_type == "charge":
        st.caption("Robot routes to its charging dock. No target coordinates needed.")
        retry = st.number_input(
            "charge_retry_count", value=0, min_value=0, step=1, key="send_chg_retry",
            help="0 = leave unset (server default).",
        )
        if retry > 0:
            payload["charge_retry_count"] = int(retry)

    elif move_type == "along_given_route":
        route = st.text_area(
            "route_coordinates",
            value="",
            key="send_route_coords",
            help='Comma-separated "x1, y1, x2, y2, …" path in world meters.',
            placeholder="0.0, 0.0, 1.5, 0.0, 1.5, 2.0",
        )
        detour = st.number_input(
            "detour_tolerance (m)", value=0.0, format="%.3f", min_value=0.0,
            key="send_route_detour",
            help="0 = no obstacle evasion. Leave blank to use server default.",
        )
        if route.strip():
            payload["route_coordinates"] = route.strip()
        if detour > 0:
            payload["detour_tolerance"] = detour

    elif move_type in ("align_with_rack", "to_unload_point"):
        st.caption(
            "Rack interaction move. Provide a target rack via `rack_area_id`, "
            "and the rack layer index via `properties.rack_layer`."
        )
        c1, c2 = st.columns(2)
        rack_id = c1.text_input("rack_area_id", value="", key=f"send_{move_type}_rack")
        rack_layer = c2.number_input(
            "properties.rack_layer", value=0, min_value=0, step=1,
            key=f"send_{move_type}_layer",
        )
        if rack_id.strip():
            payload["rack_area_id"] = rack_id.strip()
        if rack_layer > 0:
            payload["properties"] = {"rack_layer": int(rack_layer)}

    elif move_type == "follow_target":
        st.info(
            "`follow_target` does not take target coordinates here. After the move "
            "is created, publish target poses to the WebSocket topic "
            "**`/follow_target_state`** at 2–4 Hz to update the goal."
        )

    elif move_type == "leave_elevator":
        st.warning(
            "**`leave_elevator` is deprecated** per the official docs. "
            "Do not use it for new code."
        )

    elif move_type in ("return_to_elevator_waiting_point", "enter_elevator"):
        st.caption("Elevator-flow move. No additional parameters required.")

    else:
        st.caption("No type-specific parameters for this move type.")

    return payload


def render_send(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Send move")
        st.caption(
            "Queue a goal with **`POST /chassis/moves`** · "
            "[Move API](https://autoxingtech.github.io/axbot_rest_book/reference/moves.html)"
        )
    else:
        st.title("Send move")
        st.markdown(
            "Queue a goal with **`POST /chassis/moves`**. Field requirements vary by "
            "`type` — see [official docs]"
            "(https://autoxingtech.github.io/axbot_rest_book/reference/moves.html). "
            "Targets use map **world meters** with **orientation radians counter-clockwise from East** "
            "unless you toggle degrees."
        )

    client = get_client(base_url_from_session())

    move_type = st.pills(
        "Move type",
        MOVE_TYPES,
        default="standard",
        selection_mode="single",
    ) or "standard"

    creator = st.text_input("Creator", value=DEFAULT_CREATOR)

    payload = _build_move_payload(move_type, creator)

    clicked = st.button("Send move", type="primary", use_container_width=True)

    st.divider()

    if clicked:
        with st.spinner("Dispatching move…"):
            try:
                created = client.create_move(payload)
                api_block(
                    "POST",
                    "/chassis/moves",
                    request=payload,
                    response=created,
                    note="Last response from Send move.",
                )
                mv = created.get("id")
                st.session_state.active_move_id = mv
                st.toast(f"Move {mv} started", icon="✅")
            except ApiError as exc:
                api_block(
                    "POST",
                    "/chassis/moves",
                    request=payload,
                    response=exc.body,
                    error=str(exc),
                )
                st.toast("Move failed", icon="❌")
    else:
        api_block(
            "POST",
            "/chassis/moves",
            request=payload,
            note="Press **Send move** to dispatch this payload.",
        )

    if move_type == "follow_target":
        st.divider()
        st.markdown("**`follow_target`** — publish **`/follow_target_state`** (see OpenAPI websocket schema).")
        st.caption(
            "After **`POST /chassis/moves`** succeeds, enable publishing so the planner receives a moving goal. "
            "**Requires WebSocket** in the sidebar."
        )
        if not st.session_state.get("ws_enabled"):
            st.warning("Turn on **WebSocket telemetry** in the sidebar.")
        st.checkbox(
            "Publish live ``/tracked_pose`` as follow goal (~3 Hz)",
            key="nav_follow_publish_tracked",
            help="Sends follow_pose with the robot's current tracked pose — useful to unstick a follow_target move.",
        )
        _follow_target_ws_fragment()


def render_active(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Active move")
        st.caption("Poll **`GET /chassis/moves/{id}`** while a navigation task runs.")
    else:
        st.title("Active move")
        st.caption("Poll **`GET /chassis/moves/{id}`** while a navigation task runs.")
    move_id = st.session_state.get("active_move_id")
    if move_id:
        st.metric("Tracked move ID", move_id)

    if st.button("Cancel current move", use_container_width=True):
        confirm_cancel_move()

    _active_move_poll(compact=compact)


def render_history(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Move history")
    else:
        st.title("Move history")
    client = get_client(base_url_from_session())
    moves: list = []
    fetch_error: ApiError | None = None
    try:
        moves = client.list_moves() or []
    except ApiError as exc:
        fetch_error = exc

    total = len(moves)
    st.metric("Recorded moves", f"{total}")
    last = moves[-1] if moves else {}
    if last:
        lc1, lc2 = st.columns(2)
        with lc1:
            st.caption(
                f"Latest · id **`{last.get('id', '—')}`** · **`{last.get('state', '—')}`** · "
                f"type **`{last.get('type', '—')}`**"
            )
        lf = last.get("fail_reason_str")
        with lc2:
            if lf:
                st.caption(f"Failure · {lf}")

    if fetch_error:
        st.warning(str(fetch_error))

    if moves:
        rows = [
            {
                "id": m.get("id"),
                "type": m.get("type"),
                "state": m.get("state"),
                "creator": m.get("creator"),
                "fail_reason_str": m.get("fail_reason_str"),
            }
            for m in reversed(moves[-50:])
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    elif not fetch_error:
        st.caption("No moves recorded.")

    st.divider()
    if fetch_error:
        api_block(
            "GET",
            "/chassis/moves",
            response=fetch_error.body,
            error=str(fetch_error),
            note="List endpoint failed on last fetch.",
        )
    else:
        api_block(
            "GET",
            "/chassis/moves",
            response=moves,
            note="Fresh list · same payloads as above.",
        )


def render_navigation_hub() -> None:
    """Single sidebar entry: all move workflows behind tabs (less duplication vs split pages)."""
    st.title("Navigation")
    st.markdown(
        "Plan goals and monitor execution — **`POST /chassis/moves`**, "
        "**`PATCH /chassis/moves/current`**, **`GET /chassis/moves*`**. "
        "Docs: [Move API]"
        "(https://autoxingtech.github.io/axbot_rest_book/reference/moves.html)."
    )
    st.caption(
        "**Standard goals** from the canvas: **Maps → Live map** (click pose + **Send standard move**). "
        "Use the tabs below for specialist move types, tap-to-jog, live polling, and history."
    )
    t1, t2, t3, t4 = st.tabs(["Send move", "Manual jog", "Active move", "History"])
    with t1:
        render_send(compact=True)
    with t2:
        manual_control.render_manual_control(compact=True)
    with t3:
        render_active(compact=True)
    with t4:
        render_history(compact=True)
