#!/usr/bin/env python3
"""POST /services/get_rgb_image — latest RGB camera frame (v2.8.0+)."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from api_client import print_json, request_api


def get_rgb_image(topic: str) -> dict | None:
    data = request_api(
        "POST",
        "/services/get_rgb_image",
        json_body={"topic": topic},
    )
    return data if isinstance(data, dict) else data


def main() -> None:
    p = argparse.ArgumentParser(description="POST /services/get_rgb_image (needs caps.supportsGetRgbImage)")
    p.add_argument(
        "--topic",
        default="/rgb_cameras/front/compressed",
        help="camera topic (default: /rgb_cameras/front/compressed)",
    )
    p.add_argument("--list-sensors", action="store_true", help="run list_sensors and exit")
    p.add_argument("--jpeg-out", help="decode image data to this JPEG path")
    p.add_argument("--json-out", help="write full JSON response here")
    args = p.parse_args()

    if args.list_sensors:
        from list_sensors import list_sensors

        sensors = list_sensors()
        if sensors is None:
            raise SystemExit(1)
        print_json(sensors)
        return

    blob = get_rgb_image(args.topic)
    if blob is None:
        raise SystemExit(1)

    image_b64 = blob.get("data") if isinstance(blob.get("data"), str) else None
    if args.jpeg_out and image_b64:
        Path(args.jpeg_out).write_bytes(base64.standard_b64decode(image_b64))
        print(f"Wrote JPEG to {args.jpeg_out}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(blob, indent=2), encoding="utf-8")
        print(f"Wrote JSON to {args.json_out}")

    if not args.jpeg_out and not args.json_out:
        preview = dict(blob)
        if isinstance(preview.get("data"), str) and len(preview["data"]) > 80:
            preview["data"] = f"<base64 JPEG, {len(preview['data'])} chars>"
        print_json(preview)


if __name__ == "__main__":
    main()
