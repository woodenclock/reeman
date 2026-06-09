#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from api_client import request_api


def patch_settings_user(patch: dict) -> dict | None:
    """PATCH /system/settings/user."""
    data = request_api("PATCH", "/system/settings/user", json_body=patch)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: patch_settings path/to/patch.json")
        print('       patch_settings "-"   # read JSON object from stdin')
        sys.exit(1)
    path = sys.argv[1].strip()
    if path == "-":
        patch_raw = sys.stdin.read()
    else:
        patch_raw = Path(path).expanduser().resolve().read_text(encoding="utf-8")
    try:
        parsed = json.loads(patch_raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}")
        sys.exit(1)
    if not isinstance(parsed, dict):
        print("JSON must be a single object.")
        sys.exit(1)
    result = patch_settings_user(parsed)
    if result is not None:
        print(json.dumps(result, indent=2) if result else "(empty response)")
    else:
        sys.exit(1)
