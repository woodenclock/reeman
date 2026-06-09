#!/usr/bin/env python3

from pathlib import Path

import requests

from api_client import base_url, request_api

REQUEST_TIMEOUT = 120
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def normalize_dest_path(dest_path: str) -> Path:
    """Resolve relative paths under cwd; append ``.png`` when no image extension."""
    path = Path(dest_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        path = path.with_suffix(".png")
    return path


def download_map(dest_path: str, map_id: int | None = None, *, prefer: str = "image_url") -> str | None:
    """Fetch map raster from ``GET /maps/{id}`` (``image_url`` or ``thumbnail_url``).

    Returns path written, or ``None``.
    """
    if map_id is None:
        from get_current_map import current_map_id

        mid = current_map_id()
    else:
        mid = int(map_id)
    if mid is None or mid < 0:
        print("No valid map id.")
        return None

    meta = request_api("GET", f"/maps/{mid}", timeout=REQUEST_TIMEOUT)
    if not isinstance(meta, dict):
        return None

    img = None
    if prefer == "thumbnail_url":
        img = meta.get("thumbnail_url") or meta.get("image_url")
    else:
        img = meta.get("image_url") or meta.get("thumbnail_url")
    if not img:
        print("No image_url/thumbnail_url in map detail.")
        return None

    root = base_url()
    if img.startswith("/"):
        img_url = f"{root.rstrip('/')}{img}"
    elif img.startswith("http://") or img.startswith("https://"):
        img_url = img
    else:
        img_url = f"{root.rstrip('/')}/{img.lstrip('/')}"

    try:
        ir = requests.get(img_url, timeout=REQUEST_TIMEOUT)
        ir.raise_for_status()
        path = normalize_dest_path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(ir.content)
        return str(path)
    except requests.exceptions.RequestException as e:
        print(f"Download failed: {e}")
        return None


def _default_filename(map_id: int, map_name: str | None = None) -> str:
    if map_name and map_name.strip():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in map_name.strip())
        safe = safe.strip("._") or f"map_{map_id}"
        return safe
    return f"map_{map_id}"


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else ""
    mid: int | None = None
    chosen_name: str | None = None

    if len(sys.argv) > 2 and sys.argv[2].strip().lstrip("-").isdigit():
        mid = int(sys.argv[2])
    elif len(sys.argv) == 2 and out.isdigit():
        mid = int(out)
        out = f"map_{mid}.png"

    if mid is None:
        from cli_tables import print_maps_table
        from get_maps import get_maps

        maps = get_maps() or []
        if not maps:
            print("No maps.")
            sys.exit(1)
        print_maps_table(maps)
        u = input("Map index (or enter map id): ").strip()
        if u.isdigit() and int(u) < len(maps):
            chosen = maps[int(u)]
            mid = int(chosen["id"])
            chosen_name = chosen.get("name")
        elif u.isdigit():
            mid = int(u)
        else:
            print("Invalid selection.")
            sys.exit(1)

    if not out:
        default = _default_filename(mid, chosen_name)
        out = (
            input(f"Output filename in current dir [{default}]: ").strip() or default
        )

    saved = download_map(out, mid)
    if saved:
        print("Saved:", saved)
    else:
        sys.exit(1)
