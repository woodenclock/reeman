"""Advanced REST coverage — app store, hostnames, Bluetooth, fleet services, raw GET."""

from __future__ import annotations

import json

import streamlit as st

from api.client import ApiError, base_url_from_session, get_client
from ui_api_block import api_block, run_http_block


def render_advanced_hub() -> None:
    st.title("Advanced APIs")
    st.caption(
        "OpenAPI-tagged routes beyond core navigation (app store, hostnames, Bluetooth, services)."
    )
    client = get_client(base_url_from_session())

    t1, t2, t3, t4, t5 = st.tabs(
        ["App store", "Hostnames", "Bluetooth", "Fleet / sensors", "Custom GET"],
    )
    with t1:
        _tab_app_store(client)
    with t2:
        _tab_hostnames(client)
    with t3:
        _tab_bluetooth(client)
    with t4:
        _tab_fleet(client)
    with t5:
        _tab_custom_get(client)


def _tab_app_store(client) -> None:
    if st.button("GET /app_store/packages", key="adv_as_pkgs"):
        try:
            rows = client.list_app_store_packages()
            api_block("GET", "/app_store/packages", response=rows)
        except ApiError as exc:
            api_block("GET", "/app_store/packages", response=exc.body, error=str(exc))
    if st.button("POST refresh_store", key="adv_as_ref"):
        try:
            run_http_block("POST", "/app_store/services/refresh_store", client.refresh_app_store)
        except ApiError:
            st.toast("Failed", icon="❌")
    pkgs_txt = st.text_input("packages (comma-separated names)", "", key="adv_as_pkglist")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("download_packages", key="adv_as_dl"):
            parts = [p.strip() for p in pkgs_txt.split(",") if p.strip()]
            if not parts:
                st.warning("Enter package names.")
            else:
                try:
                    run_http_block(
                        "POST",
                        "/app_store/services/download_packages",
                        lambda: client.app_store_download_packages(parts),
                        request={"packages": parts},
                    )
                except ApiError:
                    st.toast("Failed", icon="❌")
    with c2:
        if st.button("install_packages", key="adv_as_inst"):
            parts = [p.strip() for p in pkgs_txt.split(",") if p.strip()]
            if parts:
                try:
                    run_http_block(
                        "POST",
                        "/app_store/services/install_packages",
                        lambda: client.app_store_install_packages(parts),
                        request={"packages": parts},
                    )
                except ApiError:
                    st.toast("Failed", icon="❌")
    with c3:
        if st.button("uninstall_packages", key="adv_as_un"):
            parts = [p.strip() for p in pkgs_txt.split(",") if p.strip()]
            if parts:
                try:
                    run_http_block(
                        "POST",
                        "/app_store/services/uninstall_packages",
                        lambda: client.app_store_uninstall_packages(parts),
                        request={"packages": parts},
                    )
                except ApiError:
                    st.toast("Failed", icon="❌")
    fn_local = st.text_input("filename for install_local_file", "", key="adv_as_locfn")
    if st.button("install_local_file", key="adv_as_loc") and fn_local.strip():
        try:
            run_http_block(
                "POST",
                "/app_store/services/install_local_file",
                lambda: client.app_store_install_local_file(fn_local.strip()),
                request={"filename": fn_local.strip()},
            )
        except ApiError:
            st.toast("Failed", icon="❌")
    if st.button("GET firmware packages", key="adv_as_fw"):
        try:
            rows = client.list_firmware_packages()
            api_block("GET", "/app_store/firmware/packages", response=rows)
        except ApiError as exc:
            api_block("GET", "/app_store/firmware/packages", response=exc.body, error=str(exc))


def _tab_hostnames(client) -> None:
    if st.button("GET /hostnames/", key="adv_hn_list"):
        try:
            rows = client.list_hostnames()
            api_block("GET", "/hostnames/", response=rows)
        except ApiError as exc:
            api_block("GET", "/hostnames/", response=exc.body, error=str(exc))
    hn = st.text_input("hostname (for GET/PATCH/DELETE)", "robot.local", key="adv_hn_one")
    ip = st.text_input("ip for PATCH", "192.168.1.10", key="adv_hn_ip")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("GET one", key="adv_hn_g"):
            try:
                d = client.get_hostname(hn)
                api_block("GET", f"/hostnames/{hn}", response=d)
            except ApiError as exc:
                api_block("GET", f"/hostnames/{hn}", response=exc.body, error=str(exc))
    with c2:
        if st.button("PATCH upsert", key="adv_hn_p"):
            try:
                run_http_block(
                    "PATCH",
                    f"/hostnames/{hn}",
                    lambda: client.upsert_hostname(hn, ip.strip()),
                    request={"ip": ip.strip()},
                )
            except ApiError:
                st.toast("Failed", icon="❌")
    with c3:
        if st.button("DELETE", key="adv_hn_d"):
            try:
                run_http_block(
                    "DELETE",
                    f"/hostnames/{hn}",
                    lambda: client.delete_hostname_entry(hn) or {"status": "ok"},
                )
            except ApiError:
                st.toast("Failed", icon="❌")


def _tab_bluetooth(client) -> None:
    st.markdown("**POST /bluetooth/connect** · **/bluetooth/disconnect**")
    mac = st.text_input("BLE MAC address", "00:11:22:33:FF:EE", key="adv_bt_mac")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("connect", key="adv_bt_c"):
            try:
                run_http_block(
                    "POST",
                    "/bluetooth/connect",
                    lambda: client.bluetooth_connect(mac),
                    request={"address": mac.strip()},
                )
            except ApiError:
                st.toast("Failed", icon="❌")
    with b2:
        if st.button("disconnect", key="adv_bt_dc"):
            try:
                run_http_block(
                    "POST",
                    "/bluetooth/disconnect",
                    lambda: client.bluetooth_disconnect(mac),
                    request={"address": mac.strip()},
                )
            except ApiError:
                st.toast("Failed", icon="❌")


def _tab_fleet(client) -> None:
    st.markdown("Cargo, towing, rack laser, RGB, time sync, pose queries (v2.12+)")
    fx = [
        ("load_cargo", "/services/load_cargo", client.load_cargo),
        ("unload_cargo", "/services/unload_cargo", client.unload_cargo),
        ("towing_hook_lock", "/services/towing_hook_lock", client.towing_hook_lock),
        ("towing_hook_release", "/services/towing_hook_release", client.towing_hook_release),
        ("clear_towing_hook_error", "/services/clear_towing_hook_error", client.clear_towing_hook_error),
        ("start_rack_size_detection", "/services/start_rack_size_detection", client.start_rack_size_detection),
        ("stop_rack_size_detection", "/services/stop_rack_size_detection", client.stop_rack_size_detection),
    ]
    cols = st.columns(4)
    for i, (label, path, fn) in enumerate(fx):
        with cols[i % 4]:
            if st.button(label, key=f"adv_fleet_{i}"):
                try:
                    run_http_block("POST", path, fn)
                except ApiError:
                    st.toast("Failed", icon="❌")

    if st.button("GET /services/step_time", key="adv_st_g"):
        try:
            run_http_block("GET", "/services/step_time", client.get_step_time_status)
        except ApiError:
            st.toast("Failed", icon="❌")
    if st.button("POST /services/step_time (apply drift fix)", key="adv_st_p"):
        try:
            run_http_block("POST", "/services/step_time", client.apply_step_time)
        except ApiError:
            st.toast("Failed", icon="❌")

    rgb_topic = st.text_input(
        "RGB topic for POST /services/get_rgb_image",
        "/rgb_cameras/front/compressed",
        key="adv_rgb_top",
    )
    if st.button("get_rgb_image", key="adv_rgb"):
        try:
            run_http_block(
                "POST",
                "/services/get_rgb_image",
                lambda: client.get_rgb_image(rgb_topic.strip()),
                request={"topic": rgb_topic.strip()},
            )
        except ApiError:
            st.toast("Failed", icon="❌")

    st.divider()
    st.markdown("**Query poses** (`/services/query_pose/*`)")
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("charger_pose", key="adv_q_ch"):
            try:
                run_http_block("GET", "/services/query_pose/charger_pose", client.query_charger_pose)
            except ApiError:
                st.toast("Failed", icon="❌")
    with q2:
        if st.button("pallet_pose", key="adv_q_pl"):
            try:
                run_http_block("GET", "/services/query_pose/pallet_pose", client.query_pallet_pose)
            except ApiError:
                st.toast("Failed", icon="❌")
    with q3:
        if st.button("trailer_pose", key="adv_q_tr"):
            try:
                run_http_block("GET", "/services/query_pose/trailer_pose", client.query_trailer_pose)
            except ApiError:
                st.toast("Failed", icon="❌")

    st.caption(
        "**Submaps / bags / recordings** — not shipped in bundled `openapi.yaml`; use vendor tools "
        "or **`Custom GET`** for documented paths."
    )


def _tab_custom_get(client) -> None:
    st.markdown(
        "Issue a raw **GET** (with optional `?query` appended to the path) — for paths not wired above."
    )
    path_in = st.text_input("path", "/device/boot_progress", key="adv_raw_path")
    if st.button("GET", key="adv_raw_go") and path_in.strip():
        p = path_in.strip()
        if not p.startswith("/"):
            p = "/" + p
        try:
            data = client.http_get(p)
            api_block("GET", p, response=data)
        except ApiError as exc:
            api_block("GET", p, response=exc.body, error=str(exc))

    st.markdown("Paste JSON preview")
    paste = st.text_area("JSON", "", height=120, key="adv_paste_json")
    if st.button("Validate JSON"):
        try:
            st.json(json.loads(paste))
        except json.JSONDecodeError as exc:
            st.error(str(exc))
