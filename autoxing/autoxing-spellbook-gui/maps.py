"""Map list, activation, pose, and overlay viewer — one page per section."""

from __future__ import annotations

import base64
import json
import math
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

import mappings_hub
from api.client import ApiError, base_url_from_session, get_client
from ui_api_block import api_block, response_preview, run_http_block


def _sync_livemap_session(map_id: int, detail: dict) -> None:
    """Keep Live map / Map list selection aligned after GET /maps/{id}."""
    st.session_state.livemap_selected_map_id = int(map_id)
    st.session_state.livemap_map_detail = detail


def _overlay_session_map() -> tuple[int | None, dict | None]:
    detail = st.session_state.get("livemap_map_detail")
    if isinstance(detail, dict) and detail.get("id") is not None:
        return int(detail["id"]), detail
    d2 = st.session_state.get("maps_selected_detail")
    mid = st.session_state.get("maps_selected_id")
    if isinstance(d2, dict) and mid is not None:
        return int(mid), d2
    return None, None


@st.dialog("Delete ALL maps on the robot?")
def confirm_delete_all_maps_bulk() -> None:
    st.error("This calls **`DELETE /maps/`** — destructive.")
    if st.button("DELETE every map", type="primary"):
        client = get_client(base_url_from_session())
        try:
            run_http_block(
                "DELETE",
                "/maps/",
                lambda: client.delete_all_maps() or {"status": "deleted"},
            )
            st.toast("All maps deleted", icon="✅")
            st.session_state.maps_selected_id = None
            st.session_state.maps_selected_detail = None
            st.session_state.livemap_selected_map_id = None
            st.session_state.livemap_map_detail = None
        except ApiError:
            st.toast("Failed", icon="❌")
        st.rerun()


def _validate_feature_collection(obj: object) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "Root must be a JSON object."
    if obj.get("type") != "FeatureCollection":
        return False, "GeoJSON root type must be FeatureCollection."
    feats = obj.get("features")
    if feats is None or not isinstance(feats, list):
        return False, "`features` must be a JSON array."
    return True, ""


def _parse_overlays(overlays_raw: str | None) -> tuple[list[dict], list[dict]]:
    if not overlays_raw:
        return [], []
    try:
        data = json.loads(overlays_raw)
    except json.JSONDecodeError:
        return [], []

    points: list[dict] = []
    lines: list[dict] = []
    for feature in data.get("features", []):
        geom = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Point" and coords and len(coords) >= 2:
            points.append(
                {
                    "name": props.get("name") or props.get("type") or "point",
                    "x": coords[0],
                    "y": coords[1],
                    "type": props.get("type"),
                }
            )
        elif gtype == "LineString" and coords:
            lines.append({"name": props.get("name", "line"), "coords": coords})
    return points, lines


def _overlay_figure(points: list[dict], lines: list[dict]) -> go.Figure:
    fig = go.Figure()
    if lines:
        for line in lines:
            xs = [c[0] for c in line["coords"]]
            ys = [c[1] for c in line["coords"]]
            fig.add_trace(
                go.Scatter(x=xs, y=ys, mode="lines", name=line["name"], line=dict(width=1))
            )
    if points:
        fig.add_trace(
            go.Scatter(
                x=[p["x"] for p in points],
                y=[p["y"] for p in points],
                mode="markers+text",
                text=[p["name"] for p in points],
                textposition="top center",
                name="Overlays",
                marker=dict(size=10, color="#4CAF50"),
            )
        )
    fig.update_layout(
        title="Map overlays",
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        yaxis_scaleanchor="x",
        height=400,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    return fig


def render_map_advanced_ingest(client, selected_id: int, detail: dict) -> None:
    """POST /maps/, ``data_url`` / inline activate, bulk delete — inside Map library."""
    with st.expander("Advanced — ingest, activate from files/data, DELETE /maps/", expanded=False):
        st.markdown(
            "AXBot **Current map and pose** (**`data_url`**, inline) and **Map API** (**POST /maps/**)."
        )
        mappings_hub.render_create_map_from_mapping_compact(key_prefix="maps_lib_adv", show_title=False)

        st.divider()
        st.markdown("#### Activate from robot `data_url` (+ map_name)")
        du = st.text_input(
            "data_url (`file://` … `.pbstream` — companion `.png`/`.yaml` on robot)",
            value="file:///tmp/map_bundle/map_73.pbstream",
            key=f"maps_act_du_{selected_id}",
        )
        dn = st.text_input(
            "map_name",
            value=str(detail.get("map_name") or "imported_from_files"),
            key=f"maps_act_dn_{selected_id}",
        )
        if st.button("POST /chassis/current-map (data_url)", key=f"maps_btn_du_{selected_id}"):
            body = {"data_url": du.strip(), "map_name": dn.strip()}
            try:
                with st.spinner("Loading from robot filesystem…"):
                    run_http_block(
                        "POST",
                        "/chassis/current-map",
                        lambda: client.set_current_map(body),
                        request=body,
                    )
                st.toast("Activated from data_url", icon="✅")
            except ApiError:
                st.toast("Failed", icon="❌")

        st.divider()
        st.markdown("#### Activate inline (base64 · can be slow)")
        iname = st.text_input("map_name (inline)", value="inline_map", key=f"maps_inline_nm_{selected_id}")
        gres = st.number_input(
            "grid_resolution",
            value=float(detail.get("grid_resolution") or 0.05),
            format="%.4f",
            key=f"maps_inline_gr_{selected_id}",
        )
        gox = st.number_input(
            "grid_origin_x", value=float(detail.get("grid_origin_x") or 0.0), format="%.4f",
            key=f"maps_inline_gox_{selected_id}",
        )
        goy = st.number_input(
            "grid_origin_y", value=float(detail.get("grid_origin_y") or 0.0), format="%.4f",
            key=f"maps_inline_goy_{selected_id}",
        )
        up_png = st.file_uploader("occupancy_grid PNG", type=["png"], key=f"maps_up_png_{selected_id}")
        up_pb = st.file_uploader("carto_map (.pbstream)", type=["pbstream"], key=f"maps_up_pb_{selected_id}")
        if st.button("POST /chassis/current-map (inline)", key=f"maps_btn_inline_{selected_id}"):
            if not up_png or not up_pb:
                st.warning("Need both PNG and pbstream uploads.")
            else:
                og_b64 = base64.standard_b64encode(up_png.read()).decode("ascii")
                cm_b64 = base64.standard_b64encode(up_pb.read()).decode("ascii")
                body = {
                    "map_name": iname.strip(),
                    "occupancy_grid": og_b64,
                    "carto_map": cm_b64,
                    "grid_resolution": float(gres),
                    "grid_origin_x": float(gox),
                    "grid_origin_y": float(goy),
                }
                preview = {
                    **body,
                    "occupancy_grid": f"<{len(og_b64)} chars>",
                    "carto_map": f"<{len(cm_b64)} chars>",
                }
                try:
                    with st.spinner("Uploading large map payload…"):
                        run_http_block(
                            "POST",
                            "/chassis/current-map",
                            lambda: client.set_current_map(body),
                            request=preview,
                        )
                    st.toast("Inline map activated", icon="✅")
                except ApiError:
                    st.toast("Failed", icon="❌")

        st.divider()
        st.markdown("#### POST /maps/ from base64 (local files)")
        cname = st.text_input("new map_name", value="uploaded_map", key=f"maps_create_nm_{selected_id}")
        c_png = st.file_uploader("carto PNG", type=["png"], key=f"maps_c_png_{selected_id}")
        c_pb = st.file_uploader("carto pbstream", type=["pbstream"], key=f"maps_c_pb_{selected_id}")
        c_gres = st.number_input(
            "grid_resolution", value=0.05, format="%.4f", key=f"maps_c_gr_{selected_id}",
        )
        c_gox = st.number_input("grid_origin_x", value=0.0, key=f"maps_c_gx_{selected_id}")
        c_goy = st.number_input("grid_origin_y", value=0.0, key=f"maps_c_gy_{selected_id}")
        if st.button("POST /maps/ (base64)", key=f"maps_btn_postmaps_{selected_id}"):
            if not c_png or not c_pb:
                st.warning("Need PNG + pbstream.")
            else:
                body = {
                    "map_name": cname.strip(),
                    "carto_map": base64.standard_b64encode(c_pb.read()).decode("ascii"),
                    "occupancy_grid": base64.standard_b64encode(c_png.read()).decode("ascii"),
                    "grid_resolution": float(c_gres),
                    "grid_origin_x": float(c_gox),
                    "grid_origin_y": float(c_goy),
                }
                req_view = {
                    **body,
                    "carto_map": f"<{len(body['carto_map'])} chars>",
                    "occupancy_grid": f"<{len(body['occupancy_grid'])} chars>",
                }
                try:
                    with st.spinner("POST /maps/ …"):
                        run_http_block(
                            "POST",
                            "/maps/",
                            lambda: client.create_map(body),
                            request=req_view,
                        )
                    st.toast("Map created on robot", icon="✅")
                except ApiError:
                    st.toast("Failed", icon="❌")

        st.divider()
        st.markdown("#### Danger zone")
        if st.button("DELETE /maps/ (remove every map)", key=f"maps_btn_delall_{selected_id}"):
            confirm_delete_all_maps_bulk()


@st.dialog("Delete map?")
def confirm_delete_map(map_id: int, map_name: str) -> None:
    st.warning(f"Permanently delete map **{map_name}** (id={map_id})?")
    if st.button("Delete", type="primary"):
        client = get_client(base_url_from_session())
        try:
            run_http_block(
                "DELETE",
                f"/maps/{map_id}",
                lambda: client.delete_map(map_id) or {"status": "deleted"},
            )
            st.toast(f"Deleted map {map_id}", icon="✅")
            if st.session_state.get("maps_selected_id") == map_id:
                st.session_state.maps_selected_id = None
                st.session_state.maps_selected_detail = None
            if st.session_state.get("livemap_selected_map_id") == map_id:
                st.session_state.livemap_selected_map_id = None
                st.session_state.livemap_map_detail = None
        except ApiError:
            st.toast("Delete failed", icon="❌")
        st.rerun()


def render_browser(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Map list")
        st.caption(
            "**Activate / delete** maps here (`POST /chassis/current-map`, `DELETE /maps/{id}`). "
            "**`GET /maps/`**, **`GET /maps/{id}`**, **`GET /chassis/current-map`**."
        )
    else:
        st.title("Map list")
        st.info(
            "Pick a map to activate or delete below. Canvas and click-to-pose live on "
            "**Maps → Live canvas** · Overlays use the cached **`GET /maps/{id}`** payload."
        )
    client = get_client(base_url_from_session())

    current: dict = {}
    try:
        current = client.get_current_map() or {}
    except ApiError:
        pass

    maps_list: list = []
    try:
        maps_list = client.list_maps() or []
    except ApiError:
        pass

    st.metric("Maps on robot", len(maps_list))
    cn = current.get("map_name") if isinstance(current.get("map_name"), str) else None
    st.caption(
        f"**Active:** {cn or '—'} `(id={current.get('id', '—')})`"
        if maps_list or current
        else "Offline or listing failed."
    )

    if not maps_list:
        st.warning("No maps (or **`GET /maps/`** failed). Test connection in the sidebar.")
        if current:
            st.divider()
            api_block("GET", "/chassis/current-map", response=current if current else None)
        st.divider()
        api_block("GET", "/maps/", response=[], note="Empty or unreachable.", empty_label="No list yet.")
        return

    id_options = [m["id"] for m in maps_list]
    preferred = st.session_state.get("livemap_selected_map_id")
    default_pick = preferred if preferred in id_options else id_options[0]

    selected_id = st.selectbox(
        "Select map",
        options=id_options,
        index=id_options.index(default_pick),
        format_func=lambda mid: next(
            (f"{m.get('map_name')} (id={m['id']})" for m in maps_list if m["id"] == mid),
            str(mid),
        ),
    )
    summary = next((m for m in maps_list if m["id"] == selected_id), None)
    if not summary:
        return

    detail_exc: ApiError | None = None
    detail: dict = summary
    try:
        detail = client.get_map(int(selected_id))
    except ApiError as exc:
        detail_exc = exc
        detail = summary
    else:
        _sync_livemap_session(int(selected_id), detail)

    col_img, col_meta = st.columns([1, 2])
    with col_img:
        raw = detail.get("thumbnail_url") or detail.get("image_url") or detail.get("url")
        thumb: str | None = None
        if raw and isinstance(raw, str) and not raw.startswith("file://"):
            if raw.startswith("http"):
                thumb = raw
            elif raw.startswith("/"):
                thumb = base_url_from_session().rstrip("/") + raw
        if thumb:
            st.image(thumb, caption=detail.get("map_name"), use_container_width=True)
        else:
            st.caption("No displayable map image")

    with col_meta:
        st.markdown(f"### {detail.get('map_name', '—')}")
        st.text(f"UID: {detail.get('uid', '—')}")
        ts = detail.get("create_time")
        if ts:
            st.text(f"Created: {datetime.fromtimestamp(ts).isoformat(sep=' ', timespec='seconds')}")
        st.text(f"Resolution: {detail.get('grid_resolution', '—')} m")
        st.text(f"Origin: ({detail.get('grid_origin_x')}, {detail.get('grid_origin_y')})")

    st.session_state.maps_selected_id = selected_id
    st.session_state.maps_selected_detail = detail

    st.divider()
    st.markdown("**Activate / delete**")

    uid_val = detail.get("uid")
    if isinstance(uid_val, str):
        uid_default = uid_val
    elif uid_val is not None:
        uid_default = str(uid_val)
    else:
        uid_default = ""

    map_uid_input = st.text_input(
        "`map_uid` for POST (pre-filled when the map exposes `uid`)",
        value=uid_default,
        key=f"maps_lib_uid_row_{selected_id}",
        help="Alternative to **`map_id`** on **`POST /chassis/current-map`**.",
    )
    uid_str = map_uid_input.strip()

    ba1, ba2, ba3 = st.columns(3)
    with ba1:
        if st.button("Activate (map_id)", use_container_width=True, key="maps_btn_act_id"):
            try:
                with st.spinner("Activating map…"):
                    run_http_block(
                        "POST",
                        "/chassis/current-map",
                        lambda: client.set_current_map({"map_id": int(selected_id)}),
                        request={"map_id": int(selected_id)},
                    )
                st.toast("Activated map by id", icon="✅")
            except ApiError:
                st.toast("Activate failed", icon="❌")
    with ba2:
        if st.button(
            "Activate (map_uid)",
            use_container_width=True,
            disabled=not uid_str,
            key="maps_btn_act_uid",
        ):
            try:
                with st.spinner("Activating map…"):
                    run_http_block(
                        "POST",
                        "/chassis/current-map",
                        lambda: client.set_current_map({"map_uid": uid_str}),
                        request={"map_uid": uid_str},
                    )
                st.toast("Activated map by uid", icon="✅")
            except ApiError:
                st.toast("Activate by uid failed", icon="❌")
    with ba3:
        if st.button("Delete map…", type="secondary", use_container_width=True, key="maps_btn_del"):
            confirm_delete_map(int(selected_id), str(detail.get("map_name") or f"id-{selected_id}"))

    api_block("GET", "/chassis/current-map", response=current if current else None)
    if detail_exc:
        api_block(
            "GET",
            f"/maps/{selected_id}",
            response=detail_exc.body,
            error=str(detail_exc),
        )
    else:
        api_block(
            "GET",
            f"/maps/{selected_id}",
            response=response_preview(detail),
            note="Preview trims huge `overlays` strings.",
        )

    render_map_advanced_ingest(client, int(selected_id), detail)

    api_block(
        "POST",
        "/chassis/current-map",
        note="Bodies sent via **Activate (map_id)** / **Activate (map_uid)** above.",
        empty_label="No POST yet — use the activation buttons.",
    )


def render_pose(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Set pose (form)")
        st.caption(
            "Same as **`POST /chassis/pose`** on **Live canvas** — use this tab for typed coordinates only."
        )
    else:
        st.title("Set robot pose")
        st.markdown(
            "Seed localization with **`POST /chassis/pose`**. Matches map frame; third element of "
            "`position` is fixed at **0.0**."
        )
    client = get_client(base_url_from_session())

    with st.form("set_pose_form"):
        use_deg = st.checkbox("Orientation in degrees")
        pc1, pc2, pc3 = st.columns(3)
        px = pc1.number_input("X (m)", value=0.0, format="%.3f")
        py = pc2.number_input("Y (m)", value=0.0, format="%.3f")
        pori = pc3.number_input("Orientation", value=0.0, format="%.3f")
        adjust = st.checkbox("Adjust position (refine after set)", value=True)
        submitted = st.form_submit_button("Set pose", use_container_width=True)

    ori_rad = math.radians(pori) if use_deg else pori
    body = {
        "position": [px, py, 0.0],
        "ori": ori_rad,
        "adjust_position": adjust,
    }

    st.divider()

    if submitted:
        try:
            client.set_pose([px, py, 0.0], ori_rad, adjust_position=adjust)
            api_block(
                "POST",
                "/chassis/pose",
                request=body,
                response={"status": "ok"},
                note="Submitted from this page.",
            )
            st.toast("Pose updated", icon="✅")
        except ApiError as exc:
            api_block(
                "POST",
                "/chassis/pose",
                request=body,
                response=exc.body,
                error=str(exc),
            )
            st.toast("Failed", icon="❌")
    else:
        api_block("POST", "/chassis/pose", request=body, note="Submit the form to call the API.")


def render_overlays(*, compact: bool = False) -> None:
    if compact:
        st.subheader("Overlays")
        st.caption("GeoJSON from the **selected map** (`overlays` field on **`GET /maps/{id}`**).")
    else:
        st.title("Map overlays")
    selected_id, detail = _overlay_session_map()
    if not detail:
        st.info(
            "Pick a map on **Live map** or **Map list** first — overlays come from **`GET /maps/{id}`**."
        )
        st.divider()
        api_block(
            "GET",
            "/maps/{id}",
            note="Loads GeoJSON overlays from stored map metadata.",
            empty_label="No cached map payload in session.",
        )
        return

    st.session_state.maps_selected_id = selected_id
    st.session_state.maps_selected_detail = detail

    overlays_raw = detail.get("overlays")
    points, lines = _parse_overlays(overlays_raw)
    st.metric(
        "Overlay primitives",
        f"{len(points)} points · {len(lines)} line strings",
    )
    st.caption(detail.get("map_name") or f"map id `{selected_id}`")

    if points or lines:
        st.plotly_chart(_overlay_figure(points, lines), use_container_width=True)
    else:
        st.caption("No drawable overlay features.")

    preview = {"overlays": overlays_raw} if overlays_raw else {}
    st.divider()
    api_block(
        "GET",
        f"/maps/{selected_id}",
        response=response_preview(preview),
        note="Uses cached map detail from **Live map** or **Map list**.",
    )

    st.divider()
    with st.expander("PATCH overlays (`PATCH /maps/{id}`)", expanded=False):
        default_ov = overlays_raw if isinstance(overlays_raw, str) and overlays_raw.strip() else (
            '{"type":"FeatureCollection","features":[]}'
        )
        ov_edit = st.text_area(
            "GeoJSON FeatureCollection (stored as JSON string on the robot)",
            value=default_ov,
            height=220,
            key=f"maps_ov_patch_{selected_id}",
        )
        if st.button("Validate JSON"):
            try:
                parsed = json.loads(ov_edit)
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            else:
                ok, err = _validate_feature_collection(parsed)
                if ok:
                    st.success("Valid FeatureCollection root.")
                else:
                    st.error(err)
        if st.button("Apply PATCH to this map"):
            try:
                parsed = json.loads(ov_edit)
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            else:
                ok, err = _validate_feature_collection(parsed)
                if not ok:
                    st.error(err)
                else:
                    client = get_client(base_url_from_session())
                    overlay_wire = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
                    patch_body = {"overlays": overlay_wire}
                    try:
                        with st.spinner("Patching map…"):
                            run_http_block(
                                "PATCH",
                                f"/maps/{selected_id}",
                                lambda: client.update_map(int(selected_id), patch_body),
                                request=patch_body,
                            )
                        st.toast("Overlays patched", icon="✅")
                    except ApiError:
                        st.toast("PATCH failed", icon="❌")
