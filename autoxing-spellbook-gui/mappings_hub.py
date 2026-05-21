"""Mapping sessions — list / start / finish / export (GET/POST/PATCH/DELETE /mappings/*)."""

from __future__ import annotations

import streamlit as st

from api.client import ApiError, base_url_from_session, get_client
from ui_api_block import api_block, run_http_block


@st.dialog("Delete all mapping sessions?")
def confirm_delete_all_mappings() -> None:
    st.warning("Deletes **every** mapping task on the robot.")
    if st.button("Delete all", type="primary"):
        client = get_client(base_url_from_session())
        try:
            run_http_block(
                "DELETE",
                "/mappings/",
                lambda: client.delete_all_mappings() or {"status": "deleted"},
            )
            st.toast("All mappings deleted", icon="✅")
        except ApiError:
            st.toast("Failed", icon="❌")
        st.rerun()


def render_mappings_tab() -> None:
    st.subheader("Mapping workflows")
    st.caption(
        "**`GET /mappings/`**, **`POST /mappings/`**, **`PATCH /mappings/current`**, "
        "**`GET / DELETE /mappings/{id}`**. Landmark helpers: "
        "**`POST /services/start_collecting_landmarks`** / **`stop_collecting_landmarks`**."
    )
    client = get_client(base_url_from_session())

    rows: list = []
    try:
        rows = client.list_mappings() or []
    except ApiError as exc:
        st.warning(str(exc))
        api_block("GET", "/mappings/", response=exc.body, error=str(exc))
        return

    if rows:
        slim = [
            {
                "id": r.get("id"),
                "state": r.get("state"),
                "start_time": r.get("start_time"),
                "bag_id": r.get("bag_id"),
            }
            for r in rows
        ]
        st.dataframe(slim, use_container_width=True, hide_index=True)
    else:
        st.caption("No mapping tasks returned.")

    api_block("GET", "/mappings/", response=rows, note="Fresh list from robot.")

    st.divider()
    st.markdown("#### Start session")
    cm = st.checkbox("continue_mapping", value=False)
    spt = st.selectbox("start_pose_type", ["current_pose", "zero"], index=0)
    if st.button("POST /mappings/", type="primary", key="map_hub_post_start"):
        body: dict = {"start_pose_type": spt}
        if cm:
            body["continue_mapping"] = True
        try:
            with st.spinner("Starting…"):
                out = run_http_block(
                    "POST",
                    "/mappings/",
                    lambda: client.start_mapping(body),
                    request=body,
                )
            st.toast(f"Mapping id **{out.get('id', '?')}**", icon="✅")
        except ApiError:
            st.toast("Start failed", icon="❌")

    st.divider()
    st.markdown("#### Finish / cancel current")
    fin = st.selectbox("state for PATCH /mappings/current", ["finished", "cancelled"])
    nmo = st.checkbox("new_map_only (optional)", value=False)
    if st.button("PATCH /mappings/current", key="map_hub_patch_cur"):
        body: dict = {"state": fin}
        if nmo:
            body["new_map_only"] = True
        try:
            with st.spinner("Updating…"):
                run_http_block(
                    "PATCH",
                    "/mappings/current",
                    lambda: client.patch_mappings_current(body),
                    request=body,
                )
            st.toast("Updated current mapping", icon="✅")
        except ApiError:
            st.toast("Patch failed", icon="❌")

    st.divider()
    st.markdown("#### Landmark collection (v2.11+)")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("start_collecting_landmarks", key="map_hub_lm_start"):
            try:
                run_http_block(
                    "POST",
                    "/services/start_collecting_landmarks",
                    lambda: client.start_collecting_landmarks(),
                )
                st.toast("Started", icon="✅")
            except ApiError:
                st.toast("Failed", icon="❌")
    with b2:
        if st.button("stop_collecting_landmarks", key="map_hub_lm_stop"):
            try:
                run_http_block(
                    "POST",
                    "/services/stop_collecting_landmarks",
                    lambda: client.stop_collecting_landmarks(),
                )
                st.toast("Stopped", icon="✅")
            except ApiError:
                st.toast("Failed", icon="❌")

    st.divider()
    st.markdown("#### Inspect / delete one mapping")
    mids = [int(r["id"]) for r in rows if r.get("id") is not None]
    if mids:
        mid = st.selectbox("mapping id", mids, key="map_hub_inspect_mid_pick")
        if st.button("GET detail", key="map_hub_get_detail"):
            try:
                d = client.get_mapping(int(mid))
                api_block("GET", f"/mappings/{mid}", response=d)
            except ApiError as exc:
                api_block("GET", f"/mappings/{mid}", response=exc.body, error=str(exc))

        tj, lj = st.columns(2)
        with tj:
            if st.button("GET trajectories.json", key="map_hub_get_traj"):
                try:
                    tr = client.get_mapping_trajectories(int(mid))
                    api_block("GET", f"/mappings/{mid}/trajectories.json", response=tr)
                except ApiError as exc:
                    api_block(
                        "GET",
                        f"/mappings/{mid}/trajectories.json",
                        response=exc.body,
                        error=str(exc),
                    )
        with lj:
            if st.button("GET landmarks.json", key="map_hub_get_lm"):
                try:
                    lm = client.get_mapping_landmarks(int(mid))
                    api_block("GET", f"/mappings/{mid}/landmarks.json", response=lm)
                except ApiError as exc:
                    api_block(
                        "GET",
                        f"/mappings/{mid}/landmarks.json",
                        response=exc.body,
                        error=str(exc),
                    )

        if st.button("DELETE this mapping", type="secondary", key="map_hub_del_one"):
            try:
                run_http_block(
                    "DELETE",
                    f"/mappings/{mid}",
                    lambda: client.delete_mapping(int(mid)) or {"status": "deleted"},
                )
                st.toast(f"Deleted mapping {mid}", icon="✅")
                st.rerun()
            except ApiError:
                st.toast("Delete failed", icon="❌")

    st.divider()
    st.markdown("#### Create persisted map")
    render_create_map_from_mapping_compact(key_prefix="mhub", show_title=False)

    st.divider()
    st.markdown("#### Danger zone")
    if st.button("DELETE /mappings/ (all sessions)", key="map_hub_del_all_btn"):
        confirm_delete_all_mappings()


def render_create_map_from_mapping_compact(*, key_prefix: str = "mhub", show_title: bool = True) -> None:
    """POST /maps/ — convert a mapping id."""
    if show_title:
        st.markdown("#### Create map from mapping → POST /maps/")
    client = get_client(base_url_from_session())
    maps_rows: list = []
    try:
        maps_rows = client.list_mappings() or []
    except ApiError:
        pass
    mids = [int(r["id"]) for r in maps_rows if r.get("id") is not None]
    if not mids:
        st.caption("No mapping ids — start a session first.")
        return
    mpick = st.selectbox("mapping_id", mids, key=f"{key_prefix}_create_from_mapping_id")
    name = st.text_input("map_name", value="from_mapping", key=f"{key_prefix}_create_from_mapping_name")
    body = {"map_name": name.strip(), "mapping_id": int(mpick)}
    if st.button("POST /maps/", key=f"{key_prefix}_btn_create_mapping"):
        try:
            with st.spinner("Creating map…"):
                run_http_block("POST", "/maps/", lambda: client.create_map(body), request=body)
            st.toast("Map created — check **Map list**.", icon="✅")
        except ApiError:
            st.toast("POST /maps/ failed", icon="❌")
