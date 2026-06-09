"""Thin HTTP client for the AXBot REST API (OpenAPI v2.14)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import requests
import streamlit as st

MOVE_TYPES = [
    "standard",
    "charge",
    "return_to_elevator_waiting_point",
    "enter_elevator",
    "leave_elevator",
    "along_given_route",
    "align_with_rack",
    "to_unload_point",
    "follow_target",
]

TERMINAL_MOVE_STATES = frozenset({"succeeded", "failed", "cancelled", "idle"})
DEFAULT_CREATOR = "streamlit_controller"
DEFAULT_HOST = "192.168.25.25"
DEFAULT_PORT = 8090
REQUEST_TIMEOUT = 10


def robot_controller_auto_connect_ws() -> bool:
    """True if `.streamlit/config.toml` requests WebSocket telemetry on startup."""
    path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    if not path.is_file():
        return False
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return False
    section = data.get("robot_controller")
    if not isinstance(section, dict):
        return False
    val = section.get("auto_connect_ws", False)
    return val is True


class ApiError(Exception):
    """Robot API returned an error response."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _http_error_user_message(body: Any, response_text: str, *, status_code: int) -> str:
    """Prefer FastAPI-style ``detail`` then ``message`` (AXBot stacks vary slightly)."""
    if isinstance(body, dict):
        m = body.get("message")
        if isinstance(m, str) and m.strip():
            return m.strip()
        if m is not None and not isinstance(m, str):
            return str(m)
        detail = body.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, dict):
                    loc = item.get("loc")
                    msg = item.get("msg", item.get("detail", ""))
                    parts.append(f"{loc}: {msg}" if loc else str(msg))
                else:
                    parts.append(str(item))
            joined = "; ".join(p for p in parts if p)
            if joined:
                return joined
    elif isinstance(body, str) and body.strip():
        return body.strip()
    return (response_text or "").strip() or f"HTTP {status_code}"


def suggests_software_emergency_stop_unsupported(exc: ApiError) -> bool:
    """True when chassis reports software ``set_emergency_stop`` is unavailable for this SKU."""
    if isinstance(exc.body, dict):
        detail = exc.body.get("detail")
        if isinstance(detail, str):
            low = detail.lower()
            return "unsupported" in low and "emergency stop" in low
    msg = exc.args[0] if exc.args else ""
    if isinstance(msg, str):
        low = msg.lower()
        return "unsupported" in low and "emergency stop" in low
    return False


def default_robot_host() -> str:
    try:
        return str(st.secrets["robot_ip"])
    except (KeyError, FileNotFoundError):
        return DEFAULT_HOST


def default_robot_port() -> int:
    try:
        return int(st.secrets["robot_port"])
    except (KeyError, FileNotFoundError, TypeError, ValueError):
        return DEFAULT_PORT


def base_url_from_session() -> str:
    host = st.session_state.get("robot_ip", default_robot_host())
    port = int(st.session_state.get("robot_port", default_robot_port()))
    return f"http://{host}:{port}"


def init_session_state() -> None:
    if "robot_ip" not in st.session_state:
        st.session_state.robot_ip = default_robot_host()
    if "robot_port" not in st.session_state:
        st.session_state.robot_port = default_robot_port()
    if "connection_ok" not in st.session_state:
        st.session_state.connection_ok = None
    if "device_brief" not in st.session_state:
        st.session_state.device_brief = None
    if "device_info" not in st.session_state:
        st.session_state.device_info = None
    if "ws_enabled" not in st.session_state:
        st.session_state.ws_enabled = robot_controller_auto_connect_ws()
    if "active_move_id" not in st.session_state:
        st.session_state.active_move_id = None
    if "maps_selected_id" not in st.session_state:
        st.session_state.maps_selected_id = None
    if "maps_selected_detail" not in st.session_state:
        st.session_state.maps_selected_detail = None
    if "livemap_selected_map_id" not in st.session_state:
        st.session_state.livemap_selected_map_id = None
    if "livemap_map_detail" not in st.session_state:
        st.session_state.livemap_map_detail = None
    if "livemap_pose_history" not in st.session_state:
        st.session_state.livemap_pose_history = []
    if "livemap_pending_x_input" not in st.session_state:
        st.session_state.livemap_pending_x_input = 0.0
    if "livemap_pending_y_input" not in st.session_state:
        st.session_state.livemap_pending_y_input = 0.0
    if "livemap_pending_ori_input" not in st.session_state:
        st.session_state.livemap_pending_ori_input = 0.0
    if "livemap_pending_first_x" not in st.session_state:
        st.session_state.livemap_pending_first_x = None
    if "livemap_pending_first_y" not in st.session_state:
        st.session_state.livemap_pending_first_y = None
    if "livemap_pending_stage" not in st.session_state:
        st.session_state.livemap_pending_stage = "idle"
    if "livemap_use_deg" not in st.session_state:
        st.session_state.livemap_use_deg = True
    if "livemap_nudge_step_cm" not in st.session_state:
        st.session_state.livemap_nudge_step_cm = 10
    if "livemap_nudge_ori_deg" not in st.session_state:
        st.session_state.livemap_nudge_ori_deg = 5
    if "livemap_last_click" not in st.session_state:
        st.session_state.livemap_last_click = None
    if "wheel_sw_estop_supported" not in st.session_state:
        st.session_state.wheel_sw_estop_supported = None


@st.cache_resource
def get_client(base_url: str) -> AxbotClient:
    return AxbotClient(base_url)


class AxbotClient:
    def __init__(self, base_url: str, timeout: float = REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | list | None = None,
        params: dict | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(
                method,
                url,
                json=json,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Network error: {exc}") from exc

        if response.status_code >= 400:
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text
            message = _http_error_user_message(body, response.text, status_code=response.status_code)
            raise ApiError(message, response.status_code, body)

        if response.status_code == 204 or not response.content:
            return None
        if not expect_json:
            return response.text
        if not response.content:
            return None
        return response.json()

    def ping(self) -> dict:
        return self._request("GET", "/device/info/brief")

    def http_get(self, path: str, *, params: dict | None = None) -> Any:
        """Ad-hoc GET for paths not wrapped (e.g. boot progress, Chrony)."""
        if not path.startswith("/"):
            path = "/" + path
        return self._request("GET", path, params=params)

    # ── Moves ─────────────────────────────────────────────────────────────

    def create_move(self, payload: dict) -> dict:
        return self._request("POST", "/chassis/moves", json=payload)

    def list_moves(self) -> list:
        return self._request("GET", "/chassis/moves") or []

    def get_move(self, move_id: int) -> dict:
        return self._request("GET", f"/chassis/moves/{move_id}")

    def cancel_current_move(self) -> dict:
        return self._request(
            "PATCH",
            "/chassis/moves/current",
            json={"state": "cancelled"},
        )

    # ── Map & pose ────────────────────────────────────────────────────────

    def get_current_map(self) -> dict:
        return self._request("GET", "/chassis/current-map")

    def set_current_map(self, payload: dict) -> dict:
        return self._request("POST", "/chassis/current-map", json=payload)

    def set_pose(self, position: list[float], ori: float, adjust_position: bool = True) -> None:
        self._request(
            "POST",
            "/chassis/pose",
            json={
                "position": position,
                "ori": ori,
                "adjust_position": adjust_position,
            },
        )

    # ── Maps ──────────────────────────────────────────────────────────────

    def list_maps(self) -> list:
        return self._request("GET", "/maps/") or []

    def get_map(self, map_id: int) -> dict:
        return self._request("GET", f"/maps/{map_id}")

    def delete_map(self, map_id: int) -> None:
        self._request("DELETE", f"/maps/{map_id}")

    def create_map(self, payload: dict) -> dict:
        return self._request("POST", "/maps/", json=payload)

    def update_map(self, map_id: int, payload: dict) -> dict:
        return self._request("PATCH", f"/maps/{map_id}", json=payload)

    def delete_all_maps(self) -> None:
        self._request("DELETE", "/maps/")

    # ── Mappings ────────────────────────────────────────────────────────────

    def list_mappings(self) -> list:
        return self._request("GET", "/mappings/") or []

    def start_mapping(self, payload: dict | None = None) -> dict:
        return self._request("POST", "/mappings/", json=payload or {})

    def patch_mappings_current(self, payload: dict) -> dict:
        return self._request("PATCH", "/mappings/current", json=payload)

    def get_mapping(self, mapping_id: int) -> dict:
        return self._request("GET", f"/mappings/{mapping_id}")

    def delete_mapping(self, mapping_id: int) -> None:
        self._request("DELETE", f"/mappings/{mapping_id}")

    def delete_all_mappings(self) -> None:
        self._request("DELETE", "/mappings/")

    def get_mapping_trajectories(self, mapping_id: int) -> list:
        return self._request("GET", f"/mappings/{mapping_id}/trajectories.json") or []

    def get_mapping_landmarks(self, mapping_id: int) -> list:
        return self._request("GET", f"/mappings/{mapping_id}/landmarks.json") or []

    # ── App store ──────────────────────────────────────────────────────────

    def list_app_store_packages(self) -> list:
        return self._request("GET", "/app_store/packages") or []

    def refresh_app_store(self) -> dict:
        return self._request("POST", "/app_store/services/refresh_store")

    def app_store_download_packages(self, packages: list[str]) -> Any:
        return self._request("POST", "/app_store/services/download_packages", json={"packages": packages})

    def app_store_install_packages(self, packages: list[str]) -> Any:
        return self._request("POST", "/app_store/services/install_packages", json={"packages": packages})

    def app_store_install_local_file(self, filename: str) -> Any:
        return self._request("POST", "/app_store/services/install_local_file", json={"filename": filename})

    def app_store_uninstall_packages(self, packages: list[str]) -> Any:
        return self._request("POST", "/app_store/services/uninstall_packages", json={"packages": packages})

    def list_download_tasks(self) -> list:
        return self._request("GET", "/app_store/jobs/download/tasks") or []

    def list_install_tasks(self) -> list:
        return self._request("GET", "/app_store/jobs/install/tasks") or []

    def get_download_task_log(self, task_id: int, start: int = 0, end: int | None = None) -> str:
        params = {"start": start}
        if end is not None:
            params["end"] = end
        return self._request(
            "GET",
            f"/app_store/jobs/download/tasks/{task_id}/log",
            params=params,
            expect_json=False,
        )

    def get_install_task_log(self, task_id: int, start: int = 0, end: int | None = None) -> str:
        params = {"start": start}
        if end is not None:
            params["end"] = end
        return self._request(
            "GET",
            f"/app_store/jobs/install/tasks/{task_id}/log",
            params=params,
            expect_json=False,
        )

    def list_firmware_packages(self) -> list:
        return self._request("GET", "/app_store/firmware/packages") or []

    def install_firmware_packages(self, packages: list[str]) -> Any:
        return self._request("POST", "/app_store/firmware/install_packages", json={"packages": packages})

    # ── Hostnames ────────────────────────────────────────────────────────────

    def list_hostnames(self) -> list:
        return self._request("GET", "/hostnames/") or []

    def get_hostname(self, hostname: str) -> dict:
        hp = hostname.strip("/ ")
        return self._request("GET", f"/hostnames/{hp}")

    def upsert_hostname(self, hostname: str, ip: str) -> dict:
        hp = hostname.strip("/ ")
        return self._request("PATCH", f"/hostnames/{hp}", json={"ip": ip})

    def delete_hostname_entry(self, hostname: str) -> Any:
        hp = hostname.strip("/ ")
        return self._request("DELETE", f"/hostnames/{hp}")

    # ── Bluetooth ────────────────────────────────────────────────────────────

    def bluetooth_connect(self, address: str) -> Any:
        return self._request("POST", "/bluetooth/connect", json={"address": address.strip()})

    def bluetooth_disconnect(self, address: str) -> Any:
        return self._request("POST", "/bluetooth/disconnect", json={"address": address.strip()})


    # ── Device ────────────────────────────────────────────────────────────

    def get_device_info(self) -> dict:
        return self._request("GET", "/device/info")

    def get_wifi_info(self) -> dict:
        return self._request("GET", "/device/wifi_info")

    def list_available_wifis(self) -> list:
        return self._request("GET", "/device/available_wifis") or []

    # ── System settings ───────────────────────────────────────────────────

    def get_settings_effective(self) -> dict:
        return self._request("GET", "/system/settings/effective") or {}

    def get_settings_schema(self) -> dict:
        return self._request("GET", "/system/settings/schema") or {}

    def patch_settings_user(self, patch: dict) -> dict:
        return self._request("PATCH", "/system/settings/user", json=patch)

    # ── Services ──────────────────────────────────────────────────────────

    def post_service(self, path: str, payload: dict | None = None) -> Any:
        return self._request("POST", path, json=payload or {})

    def set_control_mode(self, control_mode: str) -> Any:
        return self.post_service(
            "/services/wheel_control/set_control_mode",
            {"control_mode": control_mode},
        )

    def set_emergency_stop(self, enable: bool) -> Any:
        return self.post_service(
            "/services/wheel_control/set_emergency_stop",
            {"enable": enable},
        )

    def clear_wheel_errors(self) -> Any:
        return self.post_service("/services/wheel_control/clear_errors")

    def confirm_estop(self) -> Any:
        return self.post_service("/services/confirm_estop")

    def restart_service(self) -> Any:
        return self.post_service("/services/restart_service")

    def shutdown(self, *, reboot: bool, target: str = "main_computing_unit") -> Any:
        return self.post_service(
            "/services/baseboard/shutdown",
            {"target": target, "reboot": reboot},
        )

    def wake_up_device(self) -> Any:
        return self.post_service("/services/wake_up_device")

    def jack_up(self) -> Any:
        return self.post_service("/services/jack_up")

    def jack_down(self) -> Any:
        return self.post_service("/services/jack_down")

    def roller_load(self) -> Any:
        return self.post_service("/services/roller_load")

    def roller_unload(self) -> Any:
        return self.post_service("/services/roller_unload")

    def recalibrate_imu(self) -> Any:
        return self.post_service("/services/imu/recalibrate")

    def calibrate_depth_cameras(self) -> Any:
        return self.post_service("/services/calibrate_depth_cameras")

    def calibrate_gyro_scale(self) -> Any:
        return self.post_service("/services/imu/calibrate_gyro_scale")

    def load_cargo(self) -> Any:
        return self.post_service("/services/load_cargo")

    def unload_cargo(self) -> Any:
        return self.post_service("/services/unload_cargo")

    def start_rack_size_detection(self) -> Any:
        return self.post_service("/services/start_rack_size_detection")

    def stop_rack_size_detection(self) -> Any:
        return self.post_service("/services/stop_rack_size_detection")

    def towing_hook_lock(self) -> Any:
        return self.post_service("/services/towing_hook_lock")

    def towing_hook_release(self) -> Any:
        return self.post_service("/services/towing_hook_release")

    def clear_towing_hook_error(self) -> Any:
        return self.post_service("/services/clear_towing_hook_error")

    def start_collecting_landmarks(self) -> Any:
        return self.post_service("/services/start_collecting_landmarks")

    def stop_collecting_landmarks(self) -> Any:
        return self.post_service("/services/stop_collecting_landmarks")

    def get_rgb_image(self, topic: str) -> Any:
        return self.post_service("/services/get_rgb_image", {"topic": topic})

    def get_step_time_status(self) -> dict:
        return self._request("GET", "/services/step_time")

    def apply_step_time(self) -> Any:
        return self._request("POST", "/services/step_time")

    def query_charger_pose(self) -> dict:
        return self._request("GET", "/services/query_pose/charger_pose")

    def query_pallet_pose(self) -> dict:
        return self._request("GET", "/services/query_pose/pallet_pose")

    def query_trailer_pose(self) -> dict:
        return self._request("GET", "/services/query_pose/trailer_pose")

    def get_nav_thumbnail(self, *, require_cap: bool = True) -> dict | None:
        if require_cap:
            caps = (st.session_state.get("device_info") or {}).get("caps") or {}
            if not caps.get("supportsGetNavThumbnail"):
                return None
        return self._request("GET", "/services/get_nav_thumbnail")
