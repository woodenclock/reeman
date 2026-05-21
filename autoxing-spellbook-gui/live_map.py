"""Live map page — map image canvas with overlays, live pose, history trail, click-to-set-pose."""

from __future__ import annotations

import base64
import io
import math
import struct
import time
from typing import Any

import requests
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

import maps
import mappings_hub
from api.client import DEFAULT_CREATOR, TERMINAL_MOVE_STATES, ApiError, base_url_from_session, get_client
from api.caps import has_cap
from api.websocket import get_ws_manager, ws_url_from_base
from navigation import confirm_cancel_move
from ui_api_block import api_block, response_preview

MAX_HISTORY = 500
DEFAULT_TRAIL_LEN = 200
POSE_DEDUP_DIST_M = 0.001
POSE_DEDUP_ORI_RAD = 0.01
MAX_DISPLAY_WIDTH = 1100

COLOR_OVERLAY_POINT = (76, 175, 80, 230)
COLOR_OVERLAY_LINE = (76, 175, 80, 180)
COLOR_TRAIL = (33, 150, 243)
COLOR_ROBOT = (33, 150, 243, 255)
COLOR_ROBOT_OUTLINE = (13, 71, 161, 255)
COLOR_PENDING_XY = (244, 67, 54, 230)
COLOR_PENDING_READY = (255, 152, 0, 230)
COLOR_LIDAR = (255, 235, 59, 220)
COLOR_GRID = (0, 0, 0, 55)

LAYERS: list[dict[str, Any]] = [
    {"key": "lidar", "label": "LIDAR PTS.", "topic": "/scan_matched_points2", "enabled": True,
     "help": "LiDAR point cloud in world frame (`/scan_matched_points2`)"},
    {"key": "costmap_l", "label": "COSTMAP L", "topic": "/maps/5cm/1hz", "enabled": True,
     "help": "5 cm/px obstacle costmap at 1 Hz (`/maps/5cm/1hz`)"},
    {"key": "costmap_h", "label": "COSTMAP H", "topic": "/maps/1cm/1hz", "enabled": True,
     "help": "1 cm/px obstacle costmap at 1 Hz (`/maps/1cm/1hz`)"},
    {"key": "ws_map", "label": "WS MAP", "topic": "/map", "enabled": False,
     "help": "Live map PNG from WebSocket `/map` (localization / mapping mode)"},
    {"key": "ws_path", "label": "PATH", "topic": "/path", "enabled": False,
     "help": "Global plan polyline from `/path`"},
    {"key": "map_info", "label": "MAP INFO", "topic": None, "enabled": True,
     "help": "Show map metadata badge (name, id, resolution, origin)"},
    {"key": "ematch", "label": "EMATCH MAP", "topic": None, "enabled": False,
     "help": "Not exposed by the AXBot REST/WS API — only available via the official rb-admin web UI."},
    {"key": "bump", "label": "BUMP MAP", "topic": None, "enabled": False,
     "help": "Not exposed by the AXBot REST/WS API — only available via the official rb-admin web UI."},
    {"key": "grid", "label": "GRID", "topic": None, "enabled": True,
     "help": "Client-side 1 m world-frame grid overlay"},
]

# Module-level cache so PNG/cloud decode is reused across fragment ticks.
_decode_cache: dict[str, tuple[Any, Any]] = {}


def _ws_snapshot() -> dict:
    if not st.session_state.get("ws_enabled"):
        return {}
    base = base_url_from_session()
    return get_ws_manager(ws_url_from_base(base)).snapshot()


def _world_to_pixel(wx: float, wy: float, ox: float, oy: float, res: float, img_h: int) -> tuple[float, float]:
    return ((wx - ox) / res, img_h - (wy - oy) / res)


def _pixel_to_world(px: float, py: float, ox: float, oy: float, res: float, img_h: int) -> tuple[float, float]:
    return (ox + px * res, oy + (img_h - py) * res)


def _pick_image_url(detail: dict) -> str | None:
    for key in ("image_url", "image", "url", "thumbnail_url", "thumbnail"):
        v = detail.get(key)
        if v and isinstance(v, str) and v.startswith("http"):
            return v
    return None


@st.cache_data(show_spinner=False, ttl=300)
def _fetch_map_image(image_url: str) -> bytes:
    resp = requests.get(image_url, timeout=15)
    resp.raise_for_status()
    return resp.content


def _load_base_image(detail: dict) -> Image.Image | None:
    url = _pick_image_url(detail)
    if not url:
        return None
    try:
        raw = _fetch_map_image(url)
    except requests.RequestException:
        return None
    try:
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _prepare_canvas(detail: dict, base: Image.Image) -> tuple[Image.Image, float, float, float, int]:
    """Return (display_image, ox, oy, effective_resolution_m_per_pixel, image_height).

    Downscales wide images to a known max width so click coords stay in the displayed pixel space
    even without `use_column_width`. effective_resolution accounts for any downscaling.
    """
    nat_res = float(detail.get("grid_resolution", 0.05))
    ox = float(detail.get("grid_origin_x", 0.0))
    oy = float(detail.get("grid_origin_y", 0.0))
    w0 = base.size[0]
    if w0 <= MAX_DISPLAY_WIDTH:
        return base, ox, oy, nat_res, base.size[1]
    scale = MAX_DISPLAY_WIDTH / w0
    new_size = (MAX_DISPLAY_WIDTH, int(base.size[1] * scale))
    display = base.resize(new_size, Image.LANCZOS)
    eff_res = nat_res / scale
    return display, ox, oy, eff_res, display.size[1]


def _draw_overlays(draw: ImageDraw.ImageDraw, ox: float, oy: float, res: float, img_h: int,
                   points: list[dict], lines: list[dict]) -> None:
    for line in lines:
        coords = [_world_to_pixel(c[0], c[1], ox, oy, res, img_h) for c in line["coords"]]
        if len(coords) >= 2:
            draw.line(coords, fill=COLOR_OVERLAY_LINE, width=2)
    for p in points:
        x, y = _world_to_pixel(p["x"], p["y"], ox, oy, res, img_h)
        r = 6
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=COLOR_OVERLAY_POINT)
        name = str(p.get("name") or "")
        if name:
            draw.text((x + r + 2, y - r - 2), name, fill=COLOR_OVERLAY_POINT)


def _draw_trail(canvas: Image.Image, ox: float, oy: float, res: float, img_h: int,
                history: list[dict], trail_len: int) -> None:
    if len(history) < 2:
        return
    samples = history[-trail_len:]
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    n = len(samples)
    for i in range(1, n):
        a = samples[i - 1]
        b = samples[i]
        pa = _world_to_pixel(a["x"], a["y"], ox, oy, res, img_h)
        pb = _world_to_pixel(b["x"], b["y"], ox, oy, res, img_h)
        frac = i / max(n - 1, 1)
        alpha = int(30 + (200 - 30) * frac)
        odraw.line([pa, pb], fill=(*COLOR_TRAIL, alpha), width=2)
    canvas.alpha_composite(overlay)


def _triangle_points(cx: float, cy: float, ori_rad: float, size: float = 14) -> list[tuple[float, float]]:
    a = -ori_rad  # image Y is flipped relative to world Y
    tip = (cx + size * math.cos(a), cy + size * math.sin(a))
    back = size * 0.55
    spread = 2.4
    left = (cx + back * math.cos(a + spread), cy + back * math.sin(a + spread))
    right = (cx + back * math.cos(a - spread), cy + back * math.sin(a - spread))
    return [tip, left, right]


def _draw_robot(draw: ImageDraw.ImageDraw, ox: float, oy: float, res: float, img_h: int,
                pose: dict) -> None:
    pos = pose.get("pos") if pose else None
    ori = pose.get("ori") if pose else None
    if not pos or len(pos) < 2 or pos[0] is None or pos[1] is None or ori is None:
        return
    cx, cy = _world_to_pixel(float(pos[0]), float(pos[1]), ox, oy, res, img_h)
    pts = _triangle_points(cx, cy, float(ori), size=16)
    draw.polygon(pts, fill=COLOR_ROBOT, outline=COLOR_ROBOT_OUTLINE)


def _draw_pending(draw: ImageDraw.ImageDraw, ox: float, oy: float, res: float, img_h: int) -> None:
    stage = st.session_state.get("livemap_pending_stage", "idle")
    if stage == "idle":
        return
    x = st.session_state.get("livemap_pending_x_input")
    y = st.session_state.get("livemap_pending_y_input")
    if x is None or y is None:
        return
    cx, cy = _world_to_pixel(float(x), float(y), ox, oy, res, img_h)
    if stage == "have_xy":
        r = 9
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=COLOR_PENDING_XY, width=3)
        draw.line([(cx - 4, cy), (cx + 4, cy)], fill=COLOR_PENDING_XY, width=2)
        draw.line([(cx, cy - 4), (cx, cy + 4)], fill=COLOR_PENDING_XY, width=2)
    else:  # have_xy_ori
        r = 7
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=COLOR_PENDING_READY)
        ori = _current_pending_ori_rad()
        if ori is not None:
            pts = _triangle_points(cx, cy, float(ori), size=18)
            draw.polygon(pts, outline=COLOR_PENDING_READY, fill=(*COLOR_PENDING_READY[:3], 120))


def _layer_topic(key: str) -> str | None:
    for layer in LAYERS:
        if layer["key"] == key:
            return layer.get("topic")
    return None


def _sync_ws_topic(topic: str, enable: bool) -> None:
    if not st.session_state.get("ws_enabled"):
        return
    base = base_url_from_session()
    mgr = get_ws_manager(ws_url_from_base(base))
    try:
        if enable:
            mgr.enable_topic(topic)
        else:
            mgr.disable_topic(topic)
    except Exception:  # noqa: BLE001 — manager logs internally; UI shouldn't crash
        pass


def _toggle_layer(key: str) -> None:
    layers: set = st.session_state.setdefault("livemap_layers", set())
    topic = _layer_topic(key)
    if key in layers:
        layers.discard(key)
        if topic:
            _sync_ws_topic(topic, enable=False)
    else:
        layers.add(key)
        if topic:
            _sync_ws_topic(topic, enable=True)


def _ensure_layer_subscriptions() -> None:
    """Idempotently re-assert WS subscriptions for active layers (handles reconnect)."""
    if not st.session_state.get("ws_enabled"):
        return
    active: set = st.session_state.get("livemap_layers", set())
    if not active:
        return
    for layer in LAYERS:
        if layer["key"] in active and layer.get("topic"):
            _sync_ws_topic(layer["topic"], enable=True)


def _decode_costmap(topic: str, msg: dict) -> Image.Image | None:
    data_b64 = msg.get("data")
    if not data_b64:
        return None
    cache_key = msg.get("stamp") or hash(data_b64)
    cached = _decode_cache.get(topic)
    if cached and cached[0] == cache_key:
        return cached[1]
    try:
        raw = base64.b64decode(data_b64)
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:  # noqa: BLE001 — bad frame, skip
        return None
    _decode_cache[topic] = (cache_key, img)
    return img


def _draw_costmap(canvas: Image.Image, ox: float, oy: float, res: float, img_h: int,
                  topic: str, msg: dict, alpha: int = 110) -> None:
    cm = _decode_costmap(topic, msg)
    if cm is None:
        return
    cm_res = float(msg.get("resolution") or res)
    origin = msg.get("origin") or [ox, oy]
    if not isinstance(origin, (list, tuple)) or len(origin) < 2:
        return
    cm_ox, cm_oy = float(origin[0]), float(origin[1])

    scale = cm_res / res if res > 0 else 1.0
    new_w = max(1, int(round(cm.size[0] * scale)))
    new_h = max(1, int(round(cm.size[1] * scale)))
    cm_scaled = cm.resize((new_w, new_h), Image.NEAREST)

    if 0 <= alpha < 255:
        r, g, b, a = cm_scaled.split()
        a = a.point(lambda v: int(v * alpha / 255))
        cm_scaled = Image.merge("RGBA", (r, g, b, a))

    # Costmap (cm_ox, cm_oy) is bottom-left in world. Convert to display pixel,
    # then offset up by costmap height to get its top-left.
    px_bl, py_bl = _world_to_pixel(cm_ox, cm_oy, ox, oy, res, img_h)
    paste_x = int(round(px_bl))
    paste_y = int(round(py_bl - new_h))
    # Image.paste clips automatically and uses the alpha channel as mask.
    canvas.paste(cm_scaled, (paste_x, paste_y), cm_scaled)


def _extract_lidar_points(msg: dict) -> list[tuple[float, float]]:
    """Try several plausible schemas — actual /scan_matched_points2 shape isn't documented."""
    pts = msg.get("points")
    if pts is None:
        pts = msg.get("data")
    if pts is None:
        return []
    # [[x, y], ...]
    if isinstance(pts, list) and pts and isinstance(pts[0], (list, tuple)) and len(pts[0]) >= 2:
        out = []
        for p in pts:
            try:
                out.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError):
                continue
        return out
    # [x1, y1, x2, y2, ...]
    if isinstance(pts, list) and pts and isinstance(pts[0], (int, float)):
        try:
            return [(float(pts[i]), float(pts[i + 1])) for i in range(0, len(pts) - 1, 2)]
        except (TypeError, ValueError):
            return []
    # Base64-packed float32 [x, y, x, y, ...]
    if isinstance(pts, str):
        try:
            raw = base64.b64decode(pts)
            count = len(raw) // 4
            if count < 2:
                return []
            floats = struct.unpack(f"<{count}f", raw[: count * 4])
            return [(float(floats[i]), float(floats[i + 1])) for i in range(0, len(floats) - 1, 2)]
        except Exception:  # noqa: BLE001
            return []
    # {x: [...], y: [...]}
    if isinstance(pts, dict):
        xs, ys = pts.get("x"), pts.get("y")
        if isinstance(xs, list) and isinstance(ys, list):
            try:
                return [(float(x), float(y)) for x, y in zip(xs, ys)]
            except (TypeError, ValueError):
                return []
    return []


def _draw_lidar(canvas: Image.Image, ox: float, oy: float, res: float, img_h: int,
                msg: dict) -> None:
    pts = _extract_lidar_points(msg)
    if not pts:
        return
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    w, h = canvas.size
    for wx, wy in pts:
        px, py = _world_to_pixel(wx, wy, ox, oy, res, img_h)
        if 0 <= px < w and 0 <= py < h:
            odraw.ellipse([(px - 1.5, py - 1.5), (px + 1.5, py + 1.5)], fill=COLOR_LIDAR)
    canvas.alpha_composite(overlay)


def _draw_ws_path(draw: ImageDraw.ImageDraw, ox: float, oy: float, res: float, img_h: int, msg: dict) -> None:
    positions = msg.get("positions") or []
    pts: list[tuple[float, float]] = []
    for p in positions:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append(_world_to_pixel(float(p[0]), float(p[1]), ox, oy, res, img_h))
    if len(pts) >= 2:
        draw.line(pts, fill=(255, 0, 255), width=3)


def _draw_grid(canvas: Image.Image, ox: float, oy: float, res: float, img_h: int,
               step_m: float = 1.0) -> None:
    if res <= 0:
        return
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    w, h = canvas.size

    x_start = math.floor(ox / step_m) * step_m
    x_end = ox + w * res
    x = x_start
    while x <= x_end:
        px = (x - ox) / res
        if 0 <= px <= w:
            odraw.line([(px, 0), (px, h)], fill=COLOR_GRID, width=1)
        x += step_m

    y_start = math.floor(oy / step_m) * step_m
    y_end = oy + h * res
    y = y_start
    while y <= y_end:
        py = img_h - (y - oy) / res
        if 0 <= py <= h:
            odraw.line([(0, py), (w, py)], fill=COLOR_GRID, width=1)
        y += step_m

    canvas.alpha_composite(overlay)


def _draw_map_info(canvas: Image.Image, detail: dict) -> None:
    lines = [
        f"name : {detail.get('map_name') or '—'}",
        f"id   : {detail.get('id', '—')}   uid: {detail.get('uid') or '—'}",
        f"res  : {float(detail.get('grid_resolution', 0.0)):.4f} m/px",
        f"orig : ({float(detail.get('grid_origin_x', 0.0)):.3f}, "
        f"{float(detail.get('grid_origin_y', 0.0)):.3f}) m",
    ]
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    pad = 6
    line_h = 14
    box_w = 320
    box_h = pad * 2 + line_h * len(lines)
    odraw.rectangle([(8, 8), (8 + box_w, 8 + box_h)], fill=(255, 255, 255, 215),
                    outline=(0, 0, 0, 180), width=1)
    for i, t in enumerate(lines):
        odraw.text((8 + pad, 8 + pad + i * line_h), t, fill=(0, 0, 0, 255))
    canvas.alpha_composite(overlay)


def _compose_image(detail: dict, base: Image.Image, pose: dict,
                   history: list[dict], trail_len: int,
                   ws_snap: dict, active_layers: set
                   ) -> tuple[Image.Image, float, float, float, int]:
    display, ox, oy, res, img_h = _prepare_canvas(detail, base)
    canvas = display.copy()

    if "costmap_l" in active_layers:
        msg = ws_snap.get("/maps/5cm/1hz")
        if msg:
            _draw_costmap(canvas, ox, oy, res, img_h, "/maps/5cm/1hz", msg, alpha=110)
    if "costmap_h" in active_layers:
        msg = ws_snap.get("/maps/1cm/1hz")
        if msg:
            _draw_costmap(canvas, ox, oy, res, img_h, "/maps/1cm/1hz", msg, alpha=130)

    if "ws_map" in active_layers:
        msg = ws_snap.get("/map")
        if msg:
            _draw_costmap(canvas, ox, oy, res, img_h, "/map", msg, alpha=100)

    if "grid" in active_layers:
        _draw_grid(canvas, ox, oy, res, img_h, step_m=1.0)

    points, lines = maps._parse_overlays(detail.get("overlays"))
    draw = ImageDraw.Draw(canvas)
    _draw_overlays(draw, ox, oy, res, img_h, points, lines)

    if "ws_path" in active_layers:
        msg_path = ws_snap.get("/path")
        if msg_path:
            draw_path = ImageDraw.Draw(canvas)
            _draw_ws_path(draw_path, ox, oy, res, img_h, msg_path)

    _draw_trail(canvas, ox, oy, res, img_h, history, trail_len)
    draw = ImageDraw.Draw(canvas)
    _draw_pending(draw, ox, oy, res, img_h)
    _draw_robot(draw, ox, oy, res, img_h, pose)

    if "lidar" in active_layers:
        msg = ws_snap.get("/scan_matched_points2")
        if msg:
            _draw_lidar(canvas, ox, oy, res, img_h, msg)

    if "map_info" in active_layers:
        _draw_map_info(canvas, detail)

    return canvas.convert("RGB"), ox, oy, res, img_h


def _append_pose(pose: dict) -> None:
    pos = pose.get("pos") if pose else None
    ori = pose.get("ori") if pose else None
    if not pos or len(pos) < 2 or pos[0] is None or pos[1] is None or ori is None:
        return
    x, y = float(pos[0]), float(pos[1])
    o = float(ori)
    buf: list[dict] = st.session_state.livemap_pose_history
    if buf:
        last = buf[-1]
        do = ((last["ori"] - o + math.pi) % (2 * math.pi)) - math.pi
        if (
            abs(last["x"] - x) < POSE_DEDUP_DIST_M
            and abs(last["y"] - y) < POSE_DEDUP_DIST_M
            and abs(do) < POSE_DEDUP_ORI_RAD
        ):
            return
    buf.append({"t": time.time(), "x": x, "y": y, "ori": o})
    if len(buf) > MAX_HISTORY:
        del buf[: len(buf) - MAX_HISTORY]


def _current_pending_ori_rad() -> float | None:
    if st.session_state.get("livemap_pending_stage") == "idle":
        return None
    val = st.session_state.get("livemap_pending_ori_input")
    if val is None:
        return None
    if st.session_state.get("livemap_use_deg", True):
        return math.radians(float(val))
    return float(val)


def _handle_click(click: dict, ox: float, oy: float, res: float, img_h: int) -> None:
    wx, wy = _pixel_to_world(float(click["x"]), float(click["y"]), ox, oy, res, img_h)
    stage = st.session_state.get("livemap_pending_stage", "idle")
    if stage in ("idle", "have_xy_ori"):
        st.session_state.livemap_pending_x_input = round(wx, 3)
        st.session_state.livemap_pending_y_input = round(wy, 3)
        st.session_state.livemap_pending_first_x = wx
        st.session_state.livemap_pending_first_y = wy
        st.session_state.livemap_pending_stage = "have_xy"
    elif stage == "have_xy":
        fx = st.session_state.get("livemap_pending_first_x") or wx
        fy = st.session_state.get("livemap_pending_first_y") or wy
        dx = wx - float(fx)
        dy = wy - float(fy)
        ori_rad = math.atan2(dy, dx) if (dx * dx + dy * dy) > 1e-9 else 0.0
        use_deg = st.session_state.get("livemap_use_deg", True)
        st.session_state.livemap_pending_ori_input = round(
            math.degrees(ori_rad) if use_deg else ori_rad, 3
        )
        st.session_state.livemap_pending_stage = "have_xy_ori"


def _reset_pending() -> None:
    st.session_state.livemap_pending_stage = "idle"
    st.session_state.livemap_pending_first_x = None
    st.session_state.livemap_pending_first_y = None
    st.session_state.livemap_last_click = None
    # Leave the X/Y/ori input values alone so the widgets keep their last value


def _nudge_pose(dx: float = 0.0, dy: float = 0.0, dori_deg: float = 0.0) -> None:
    """on_click callback: shift the pending pose by deltas (dx/dy in meters, dori in degrees)."""
    if dx:
        st.session_state.livemap_pending_x_input = round(
            float(st.session_state.livemap_pending_x_input) + dx, 3
        )
    if dy:
        st.session_state.livemap_pending_y_input = round(
            float(st.session_state.livemap_pending_y_input) + dy, 3
        )
    if dori_deg:
        use_deg = st.session_state.get("livemap_use_deg", True)
        step = dori_deg if use_deg else math.radians(dori_deg)
        st.session_state.livemap_pending_ori_input = round(
            float(st.session_state.livemap_pending_ori_input) + step, 4
        )
    stage = st.session_state.get("livemap_pending_stage", "idle")
    if (dx or dy) and stage == "idle":
        st.session_state.livemap_pending_stage = "have_xy"
        st.session_state.livemap_pending_first_x = float(st.session_state.livemap_pending_x_input)
        st.session_state.livemap_pending_first_y = float(st.session_state.livemap_pending_y_input)
    elif dori_deg and stage == "have_xy":
        st.session_state.livemap_pending_stage = "have_xy_ori"


def _snap_to_robot() -> None:
    """on_click callback: copy the live /tracked_pose into the pending pose inputs."""
    pose = _ws_snapshot().get("/tracked_pose") or {}
    pos = pose.get("pos")
    ori = pose.get("ori")
    if not pos or len(pos) < 2 or pos[0] is None or pos[1] is None:
        return
    st.session_state.livemap_pending_x_input = round(float(pos[0]), 3)
    st.session_state.livemap_pending_y_input = round(float(pos[1]), 3)
    st.session_state.livemap_pending_first_x = float(pos[0])
    st.session_state.livemap_pending_first_y = float(pos[1])
    if ori is not None:
        use_deg = st.session_state.get("livemap_use_deg", True)
        val = math.degrees(float(ori)) if use_deg else float(ori)
        st.session_state.livemap_pending_ori_input = round(val, 4)
        st.session_state.livemap_pending_stage = "have_xy_ori"
    else:
        st.session_state.livemap_pending_stage = "have_xy"


def _ensure_map_loaded(map_id: int) -> dict | None:
    cached = st.session_state.get("livemap_map_detail")
    if cached and cached.get("id") == map_id:
        return cached
    client = get_client(base_url_from_session())
    try:
        detail = client.get_map(int(map_id))
    except ApiError as exc:
        st.error(f"GET /maps/{map_id} failed: {exc}")
        return None
    st.session_state.livemap_map_detail = detail
    st.session_state.livemap_selected_map_id = map_id
    st.session_state.livemap_pose_history = []
    _reset_pending()
    return detail


def _stage_caption(stage: str) -> str:
    return {
        "idle": "Click the map for X/Y, or type values below",
        "have_xy": "Click again to set heading (or type heading below)",
        "have_xy_ori": "Pose ready — review values and press **Apply pose**",
    }.get(stage, stage)


def _find_home_point(overlays_raw: Any) -> dict | None:
    points, _ = maps._parse_overlays(overlays_raw if isinstance(overlays_raw, str) else None)
    candidates = []
    for p in points:
        name = (p.get("name") or "").strip().lower()
        ptype = (p.get("type") or "").strip().lower()
        if name in ("home", "home_point", "home point"):
            candidates.append((0, p))
        elif "home" in name or "home" in ptype:
            candidates.append((1, p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[0][1]


@st.fragment(run_every="1s")
def _live_fragment() -> None:
    detail = st.session_state.get("livemap_map_detail")
    if not detail:
        st.info("Pick a map above.")
        return

    base = _load_base_image(detail)
    if base is None:
        st.warning("No usable map image URL on this map (or fetch failed).")
        return

    _ensure_layer_subscriptions()
    snap = _ws_snapshot()
    pose = snap.get("/tracked_pose") or {}
    _append_pose(pose)

    trail_len = st.session_state.get("livemap_trail_len", DEFAULT_TRAIL_LEN)
    active_layers: set = st.session_state.get("livemap_layers", set())
    composite, ox, oy, res, img_h = _compose_image(
        detail, base, pose, st.session_state.livemap_pose_history, trail_len,
        snap, active_layers,
    )

    pos = pose.get("pos") or [None, None]
    ori = pose.get("ori")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("X (m)", f"{pos[0]:.3f}" if pos[0] is not None else "—")
    m2.metric("Y (m)", f"{pos[1]:.3f}" if pos[1] is not None else "—")
    m3.metric("Heading (°)", f"{math.degrees(ori):.1f}" if ori is not None else "—")
    m4.metric("Trail", f"{len(st.session_state.livemap_pose_history)}")

    stage = st.session_state.get("livemap_pending_stage", "idle")
    st.caption(_stage_caption(stage))

    click = streamlit_image_coordinates(
        composite,
        key=f"livemap_canvas_{detail.get('id')}",
    )
    if click and click != st.session_state.livemap_last_click:
        st.session_state.livemap_last_click = click
        _handle_click(click, ox, oy, res, img_h)
        st.rerun()

    with st.expander("Canvas debug", expanded=False):
        st.caption(
            f"display = {composite.size[0]}×{composite.size[1]} px · "
            f"grid_origin = ({ox:.3f}, {oy:.3f}) m · "
            f"effective_resolution = {res:.5f} m/px · "
            f"natural_resolution = {float(detail.get('grid_resolution', 0.0)):.5f} m/px"
        )
        if click:
            cwx, cwy = _pixel_to_world(float(click["x"]), float(click["y"]), ox, oy, res, img_h)
            st.caption(
                f"last click pixel = ({click['x']}, {click['y']}) → world = ({cwx:.3f}, {cwy:.3f}) m"
            )


def _send_goto_charger(client) -> None:
    payload = {"creator": DEFAULT_CREATOR, "type": "charge"}
    with st.status("Dispatching charge move…", expanded=False):
        try:
            created = client.create_move(payload)
            mv = created.get("id") if isinstance(created, dict) else None
            if mv is not None:
                st.session_state.active_move_id = mv
            st.toast(f"Charge move {mv} dispatched", icon="🔌")
        except ApiError as exc:
            st.toast(f"Charge move failed: {exc}", icon="❌")


def _send_return_home(client, detail: dict, pose: dict) -> None:
    home = _find_home_point(detail.get("overlays"))
    if not home:
        st.toast("No 'home' landmark in overlays — add a Point named 'home'", icon="⚠️")
        return
    target_ori = float(pose.get("ori")) if pose.get("ori") is not None else 0.0
    payload = {
        "creator": DEFAULT_CREATOR,
        "type": "standard",
        "target_x": float(home["x"]),
        "target_y": float(home["y"]),
        "target_ori": target_ori,
    }
    with st.status("Dispatching return-to-home…", expanded=False):
        try:
            created = client.create_move(payload)
            mv = created.get("id") if isinstance(created, dict) else None
            if mv is not None:
                st.session_state.active_move_id = mv
            st.toast(f"Home move {mv} dispatched", icon="🏠")
        except ApiError as exc:
            st.toast(f"Home move failed: {exc}", icon="❌")


def _pending_standard_move_payload(snap: dict) -> tuple[dict | None, str | None]:
    """Build POST /chassis/moves JSON for type=standard from pending pose inputs."""
    stage = st.session_state.get("livemap_pending_stage", "idle")
    if stage not in ("have_xy", "have_xy_ori"):
        return (
            None,
            "Pick a goal on the map (first click = position, second = heading) or nudge X/Y.",
        )
    x_val = float(st.session_state.livemap_pending_x_input)
    y_val = float(st.session_state.livemap_pending_y_input)
    use_deg = st.session_state.get("livemap_use_deg", True)
    ori_in = float(st.session_state.livemap_pending_ori_input)
    live_ori = (snap.get("/tracked_pose") or {}).get("ori")

    if stage == "have_xy_ori":
        ori_rad = math.radians(ori_in) if use_deg else ori_in
    elif live_ori is not None:
        ori_rad = float(live_ori)
    else:
        return (
            None,
            "No heading yet — second-click the map for orientation or enable WebSocket for live pose.",
        )

    payload = {
        "creator": DEFAULT_CREATOR,
        "type": "standard",
        "target_x": x_val,
        "target_y": y_val,
        "target_ori": ori_rad,
    }
    return payload, None


def _send_standard_to_goal(client, snap: dict) -> None:
    payload, reason = _pending_standard_move_payload(snap)
    if not payload:
        st.toast(reason or "Cannot build move payload", icon="⚠️")
        return
    try:
        created = client.create_move(payload)
        mv = created.get("id") if isinstance(created, dict) else None
        if mv is not None:
            st.session_state.active_move_id = mv
        st.toast(f"Standard move {mv} dispatched", icon="🧭")
    except ApiError as exc:
        st.toast(f"Move failed: {exc}", icon="❌")


@st.fragment(run_every="2s")
def _livemap_active_move_strip() -> None:
    """Compact poll of session ``active_move_id`` with cancel affordance."""
    move_id = st.session_state.get("active_move_id")
    if not move_id:
        st.caption(
            "No active move in session — dispatch with **Standard goal** below, charger/home, "
            "or the **Navigation** hub (**Send move** tab)."
        )
        return
    client = get_client(base_url_from_session())
    try:
        md = client.get_move(int(move_id))
    except ApiError as exc:
        st.warning(f"GET /chassis/moves/{move_id}: {exc}")
        return
    state = md.get("state", "—")
    color = {
        "idle": "gray",
        "moving": "blue",
        "succeeded": "green",
        "failed": "red",
        "cancelled": "orange",
    }.get(str(state), "gray")
    st.badge(str(state), color=color)
    st.caption(f"Tracked id **`{move_id}`** · auto-refresh")
    if md.get("fail_reason_str"):
        st.caption(md["fail_reason_str"])
    if st.button("Cancel current move", key="livemap_btn_cancel_move", use_container_width=True):
        confirm_cancel_move()
    if state in TERMINAL_MOVE_STATES:
        st.session_state.active_move_id = None


def _pose_readiness(snap: dict, current_map: dict | None) -> tuple[list[str], list[str]]:
    """Inspect WS state + current map and return (blockers, warnings) for POST /chassis/pose.

    Blockers disable the Apply-pose button (request will reliably fail).
    Warnings keep the button enabled but inform the user.
    """
    blockers: list[str] = []
    warnings: list[str] = []

    if not st.session_state.get("ws_enabled"):
        warnings.append(
            "WebSocket telemetry is off — robot state is unknown. "
            "Enable WS in the sidebar to see live blockers."
        )

    if current_map is None or not current_map.get("id"):
        blockers.append(
            "No map is currently active on the robot. "
            "Activate one on **Maps → Map library** tab (`POST /chassis/current-map`) before setting pose."
        )

    wheel = snap.get("/wheel_state") or {}
    if wheel:
        if wheel.get("emergency_stop_pressed"):
            blockers.append("Emergency stop is engaged — release it before setting pose.")
        ctrl_mode = wheel.get("control_mode")
        if ctrl_mode and ctrl_mode != "auto":
            blockers.append(
                f"Wheel control mode is **{ctrl_mode}** — switch to **auto** "
                "(Services → wheel_control/set_control_mode) before setting pose."
            )

    slam = snap.get("/slam/state") or {}
    if slam:
        slam_state = slam.get("state")
        if slam_state and slam_state not in ("positioning", "running"):
            blockers.append(
                f"SLAM state is **{slam_state}** — robot can't localize on the current map. "
                "Ensure a map is loaded and the lidar/cameras are powered on."
            )

    planning = snap.get("/planning_state") or {}
    move_state = planning.get("move_state")
    if move_state == "moving":
        warnings.append(
            "Robot is currently **moving** — Apply pose will interrupt navigation. "
            "Cancel the active move first if that's not intended."
        )

    battery = snap.get("/battery_state") or {}
    pct = battery.get("percentage")
    if isinstance(pct, (int, float)) and pct < 0.1:
        warnings.append(f"Battery is low ({pct * 100:.0f}%) — set pose may fail mid-adjust.")

    alerts_msg = snap.get("/alerts") or {}
    alerts = alerts_msg.get("alerts") or []
    errs = [a for a in alerts if isinstance(a, dict) and a.get("level") == "error"]
    if errs:
        codes = ", ".join(str(a.get("code")) for a in errs[:3])
        warnings.append(f"{len(errs)} active alert(s) (codes: {codes}) — check Telemetry → Alerts.")

    return blockers, warnings


def _state_chip(label: str, value: str, kind: str = "neutral") -> str:
    """Inline HTML chip for the readiness strip. kind: ok | warn | bad | neutral."""
    bg = {
        "ok":      "#1b5e20",
        "warn":    "#ef6c00",
        "bad":     "#b71c1c",
        "neutral": "#37474f",
    }.get(kind, "#37474f")
    return (
        f"<span style='display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;"
        f"border-radius:10px;background:{bg};color:#fff;font-size:0.78em;"
        f"font-family:ui-monospace,Menlo,monospace;'>"
        f"<b>{label}</b> {value}</span>"
    )


def _render_readiness_panel(snap: dict, current_map: dict | None) -> tuple[list[str], list[str]]:
    """Compact state strip + blocker/warning callouts. Returns (blockers, warnings) for gating."""
    blockers, warnings = _pose_readiness(snap, current_map)

    chips: list[str] = []

    if current_map and current_map.get("id"):
        chips.append(_state_chip(
            "map", f"{current_map.get('map_name') or current_map.get('id')}", "ok"
        ))
    else:
        chips.append(_state_chip("map", "none", "bad"))

    wheel = snap.get("/wheel_state") or {}
    if wheel:
        estop = bool(wheel.get("emergency_stop_pressed"))
        chips.append(_state_chip(
            "e-stop", "PRESSED" if estop else "clear", "bad" if estop else "ok"
        ))
        mode = wheel.get("control_mode") or "?"
        chips.append(_state_chip(
            "ctrl", mode, "ok" if mode == "auto" else "bad"
        ))
    else:
        chips.append(_state_chip("e-stop", "?", "neutral"))
        chips.append(_state_chip("ctrl", "?", "neutral"))

    slam = snap.get("/slam/state") or {}
    if slam:
        s = slam.get("state") or "?"
        kind = "ok" if s in ("positioning", "running") else "bad"
        chips.append(_state_chip("slam", s, kind))
    else:
        chips.append(_state_chip("slam", "?", "neutral"))

    planning = snap.get("/planning_state") or {}
    move = planning.get("move_state")
    if move:
        kind = "warn" if move == "moving" else "ok"
        chips.append(_state_chip("move", move, kind))

    battery = snap.get("/battery_state") or {}
    pct = battery.get("percentage")
    if isinstance(pct, (int, float)):
        kind = "bad" if pct < 0.1 else ("warn" if pct < 0.2 else "ok")
        chips.append(_state_chip("batt", f"{pct * 100:.0f}%", kind))

    st.markdown(
        "<div style='line-height:1.9'>" + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )

    if blockers:
        st.error("Apply pose is blocked:\n\n- " + "\n- ".join(blockers))
    if warnings:
        for w in warnings:
            st.warning(w)

    return blockers, warnings


def _render_pending_controls(blockers: list[str]) -> tuple[bool, dict]:
    """Render editable X/Y/heading inputs + Apply / Reset. Returns (apply_clicked, payload_preview).

    `blockers` is a list of human-readable strings; if non-empty, Apply pose is disabled.
    """
    stage = st.session_state.get("livemap_pending_stage", "idle")
    st.markdown("**Pending pose**")
    st.caption(_stage_caption(stage))

    use_deg = st.toggle("Heading in degrees", key="livemap_use_deg")
    ori_label = "Heading (°)" if use_deg else "Heading (rad)"

    st.number_input("X (m)", key="livemap_pending_x_input", format="%.3f", step=0.1)
    st.number_input("Y (m)", key="livemap_pending_y_input", format="%.3f", step=0.1)
    st.number_input(
        ori_label, key="livemap_pending_ori_input", format="%.3f",
        step=1.0 if use_deg else 0.05,
    )

    st.button(
        "Snap to robot pose",
        on_click=_snap_to_robot,
        use_container_width=True,
        help="Copy live /tracked_pose into the inputs (good starting point for nudging)",
    )

    st.markdown("**Nudge (Δ)**")
    nudge_options = [1, 5, 10, 25, 50, 100]
    cur_step = int(st.session_state.get("livemap_nudge_step_cm", 10))
    if cur_step not in nudge_options:
        cur_step = 10
    step_cm = st.select_slider(
        "Step (cm)", options=nudge_options, value=cur_step,
        key="livemap_nudge_step_cm",
    )
    ori_options = [1, 5, 15, 45, 90]
    cur_ori_step = int(st.session_state.get("livemap_nudge_ori_deg", 5))
    if cur_ori_step not in ori_options:
        cur_ori_step = 5
    ori_step_deg = st.select_slider(
        "Heading step (°)", options=ori_options, value=cur_ori_step,
        key="livemap_nudge_ori_deg",
    )

    dxy = float(step_cm) / 100.0

    # 3×3 D-pad for X/Y nudges (top = +Y, right = +X)
    _, up_col, _ = st.columns(3)
    up_col.button(
        "↑", key="livemap_nudge_up", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dy": dxy},
        help=f"+Y by {step_cm} cm",
    )
    left_col, ctr_col, right_col = st.columns(3)
    left_col.button(
        "←", key="livemap_nudge_left", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dx": -dxy},
        help=f"−X by {step_cm} cm",
    )
    ctr_col.markdown(
        f"<div style='text-align:center;font-size:0.75em;color:#888;'>{step_cm}<br>cm</div>",
        unsafe_allow_html=True,
    )
    right_col.button(
        "→", key="livemap_nudge_right", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dx": dxy},
        help=f"+X by {step_cm} cm",
    )
    _, dn_col, _ = st.columns(3)
    dn_col.button(
        "↓", key="livemap_nudge_down", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dy": -dxy},
        help=f"−Y by {step_cm} cm",
    )

    rot_l, rot_r = st.columns(2)
    rot_l.button(
        f"↶ {ori_step_deg}°", key="livemap_nudge_ccw", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dori_deg": ori_step_deg},
        help=f"Rotate CCW by {ori_step_deg}°",
    )
    rot_r.button(
        f"↷ {ori_step_deg}°", key="livemap_nudge_cw", use_container_width=True,
        on_click=_nudge_pose, kwargs={"dori_deg": -ori_step_deg},
        help=f"Rotate CW by {ori_step_deg}°",
    )

    x_val = float(st.session_state.livemap_pending_x_input)
    y_val = float(st.session_state.livemap_pending_y_input)
    ori_in = float(st.session_state.livemap_pending_ori_input)
    ori_rad = math.radians(ori_in) if use_deg else ori_in

    st.divider()

    adjust = st.checkbox(
        "Adjust position", value=True, key="livemap_adjust",
        help="`adjust_position` flag on POST /chassis/pose — refine pose after set",
    )

    if blockers:
        apply_help = "Blocked:\n• " + "\n• ".join(blockers)
    else:
        apply_help = "POST /chassis/pose with the values shown above"
    apply_clicked = st.button(
        "Apply pose",
        type="primary",
        use_container_width=True,
        disabled=bool(blockers),
        help=apply_help,
    )
    if st.button("Reset click", use_container_width=True):
        _reset_pending()
        st.rerun()

    payload = {
        "position": [x_val, y_val, 0.0],
        "ori": ori_rad,
        "adjust_position": bool(adjust),
    }
    return apply_clicked, payload


def _render_layer_row() -> None:
    """Pill-button row for layer toggles. Disabled buttons (EMATCH/BUMP) show tooltip only."""
    active: set = st.session_state.setdefault("livemap_layers", set())
    cols = st.columns(len(LAYERS))
    for col, layer in zip(cols, LAYERS):
        key = layer["key"]
        with col:
            if not layer["enabled"]:
                st.button(
                    layer["label"],
                    key=f"livemap_layer_{key}",
                    use_container_width=True,
                    disabled=True,
                    help=layer["help"],
                )
            else:
                is_on = key in active
                st.button(
                    layer["label"],
                    key=f"livemap_layer_{key}",
                    use_container_width=True,
                    type="primary" if is_on else "secondary",
                    help=layer["help"],
                    on_click=_toggle_layer,
                    args=(key,),
                )


def _render_nav_thumbnail_panel(client) -> None:
    """200×200 nav composite when firmware advertises ``supportsGetNavThumbnail``."""
    st.markdown("**Nav thumbnail** (`GET /services/get_nav_thumbnail`)")
    if not has_cap("supportsGetNavThumbnail"):
        st.caption("Not advertised in **`device_info.caps`** for this firmware.")
        return
    if st.button("Fetch thumbnail", key="livemap_nav_thumb_btn", use_container_width=True):
        try:
            blob = client.get_nav_thumbnail(require_cap=False)
        except ApiError as exc:
            st.warning(str(exc))
            return
        if not blob:
            st.caption("Empty response.")
            return
        m = blob.get("map") or {}
        b64 = m.get("data")
        if isinstance(b64, str) and b64.strip():
            try:
                raw = base64.b64decode(b64)
                st.image(
                    Image.open(io.BytesIO(raw)).convert("RGB"),
                    caption=blob.get("map_name") or "nav",
                    use_container_width=True,
                )
            except Exception:  # noqa: BLE001
                st.caption("Could not decode `map.data` PNG.")
        with st.expander("Raw JSON", expanded=False):
            st.json(blob)


def render_live_canvas() -> None:
    """Map select, layers, canvas, pose — map activation/delete on **Map library** tab."""
    st.caption(
        "**Live canvas** — click-to-pose, layers, navigation shortcuts. "
        "**Switch maps** → same page **Map library** tab (`POST /chassis/current-map`, `DELETE /maps/{id}`)."
    )

    client = get_client(base_url_from_session())

    current: dict = {}
    try:
        current = client.get_current_map() or {}
    except ApiError:
        pass

    _cm = current.get("map_name") or current.get("id")
    _cid = current.get("id", "—")
    _uid = current.get("uid") or "—"
    if current.get("id"):
        st.info(
            f"**Robot active map:** **`{_cm}`** · id **`{_cid}`** · uid **`{_uid}`** "
            "(change under **Maps → Map library**)."
        )
    else:
        st.warning(
            "No **`GET /chassis/current-map`** payload — activate a map under **Maps → Map library** before pose/moves."
        )

    maps_list: list = []
    try:
        maps_list = client.list_maps() or []
    except ApiError:
        pass

    if not maps_list and not current:
        st.warning("No maps available — test connection in the sidebar or open **Map library**.")
        return

    options = [m["id"] for m in maps_list] if maps_list else [current.get("id")]
    current_id = current.get("id")
    saved_id = st.session_state.get("livemap_selected_map_id")
    default_id = saved_id or current_id or options[0]
    if default_id not in options:
        options = [default_id, *options]

    sel_col, refresh_col = st.columns([4, 1])
    with sel_col:
        selected = st.selectbox(
            "Map",
            options=options,
            index=options.index(default_id),
            format_func=lambda mid: next(
                (f"{m.get('map_name')} (id={mid})" for m in maps_list if m["id"] == mid),
                f"id={mid}",
            )
            + (" · active" if mid == current_id else ""),
            key="livemap_map_select",
        )
    with refresh_col:
        if st.button("Reload map", use_container_width=True):
            st.session_state.livemap_map_detail = None
            _fetch_map_image.clear()

    detail = _ensure_map_loaded(int(selected))
    if not detail:
        return

    st.session_state.maps_selected_id = detail.get("id")
    st.session_state.maps_selected_detail = detail
    maps._sync_livemap_session(int(selected), detail)

    if not st.session_state.get("ws_enabled"):
        st.caption(
            "WebSocket telemetry is off — live pose arrow and history will not update. "
            "Toggle it in the sidebar."
        )

    _render_layer_row()

    canvas_col, ctrl_col = st.columns([4, 1])
    with canvas_col:
        _live_fragment()

    with ctrl_col:
        st.markdown("**Robot state**")
        blockers, _warnings = _render_readiness_panel(_ws_snapshot(), current)
        _render_nav_thumbnail_panel(client)
        st.divider()
        apply_clicked, payload = _render_pending_controls(blockers)

        st.divider()
        st.markdown("**Dispatch**")
        live_pose = _ws_snapshot().get("/tracked_pose") or {}
        home_pt = _find_home_point(detail.get("overlays"))
        home_disabled = home_pt is None
        if st.button(
            "Return to home",
            use_container_width=True,
            disabled=home_disabled,
            help=(
                f"Send standard move to overlay landmark 'home' at "
                f"({home_pt['x']:.2f}, {home_pt['y']:.2f})"
                if home_pt else
                "Add a Point named 'home' to the map overlays to enable"
            ),
        ):
            _send_return_home(client, detail, live_pose)
            st.rerun()
        if st.button(
            "Go to charger",
            use_container_width=True,
            help="POST /chassis/moves with `type: charge` — robot routes to its charging dock",
        ):
            _send_goto_charger(client)
            st.rerun()

        st.divider()
        st.markdown("**Active move**")
        _livemap_active_move_strip()

        st.divider()
        st.markdown("**Standard goal**")
        snap_goal = _ws_snapshot()
        _, goal_err = _pending_standard_move_payload(snap_goal)
        if goal_err:
            st.caption(goal_err)
        if st.button(
            "Send standard move to goal",
            use_container_width=True,
            disabled=bool(blockers) or goal_err is not None,
            help="POST /chassis/moves — target X/Y/heading from **Pending pose** (second click sets heading)",
        ):
            _send_standard_to_goal(client, snap_goal)
            st.rerun()

        st.divider()
        st.session_state.livemap_trail_len = st.slider(
            "Trail length",
            min_value=20,
            max_value=MAX_HISTORY,
            value=st.session_state.get("livemap_trail_len", DEFAULT_TRAIL_LEN),
            step=20,
        )
        if st.button("Clear history", use_container_width=True):
            st.session_state.livemap_pose_history = []
            st.rerun()

    sent_error: str | None = None
    if apply_clicked:
        with st.status("Setting pose…", expanded=False):
            try:
                client.set_pose(
                    payload["position"],
                    payload["ori"],
                    adjust_position=payload["adjust_position"],
                )
                st.toast("Pose updated", icon="✅")
                _reset_pending()
            except ApiError as exc:
                sent_error = str(exc)
                st.toast(f"Set pose failed: {exc}", icon="❌")

    st.divider()
    with st.expander("API · POST /chassis/pose", expanded=False):
        if apply_clicked and not sent_error:
            api_block(
                "POST", "/chassis/pose",
                request=payload, response={"status": "ok"},
                note="Submitted from Live canvas.",
            )
        elif apply_clicked and sent_error:
            api_block(
                "POST", "/chassis/pose",
                request=payload, response=None, error=sent_error,
            )
        else:
            api_block(
                "POST", "/chassis/pose",
                request=payload,
                note="Edit values above (or click on the map) then press **Apply pose**.",
            )

    with st.expander(f"API · GET /maps/{detail.get('id')}", expanded=False):
        api_block(
            "GET", f"/maps/{detail.get('id')}",
            response=response_preview(detail),
            note="Cached on the page; press **Reload map** to re-fetch.",
        )


def render_live_map() -> None:
    st.title("Maps & live canvas")
    st.markdown(
        "**Live canvas** — layers, **`/tracked_pose`**, click-to-pose, moves. "
        "**Map library** — thumbnails and **`POST /chassis/current-map`** / **`DELETE /maps/{id}`**. "
        "**Overlays** / **Set pose** — helpers matching "
        "[Current map and pose](https://autoxingtech.github.io/axbot_rest_book/reference/current_map_and_pose.html). "
        "Specialist **`POST /chassis/moves`** types live under **Navigation**."
    )
    tab_live, tab_library, tab_mapping, tab_over, tab_pose = st.tabs(
        ["Live canvas", "Map library", "Mapping", "Overlays", "Set pose (form)"],
    )
    with tab_live:
        render_live_canvas()
    with tab_library:
        maps.render_browser(compact=True)
    with tab_mapping:
        mappings_hub.render_mappings_tab()
    with tab_over:
        maps.render_overlays(compact=True)
    with tab_pose:
        maps.render_pose(compact=True)
