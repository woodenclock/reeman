#!/usr/bin/env python3

from api_client import print_json, request_api


def set_emergency_stop(enable: bool) -> dict | None:
    """POST /services/wheel_control/set_emergency_stop."""
    data = request_api(
        "POST",
        "/services/wheel_control/set_emergency_stop",
        json_body={"enable": bool(enable)},
    )
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        raw = sys.argv[1].strip().lower()
        en = raw in ("1", "true", "yes", "y", "on")
    else:
        raw = input("Enable e-stop? [y/N]: ").strip().lower()
        en = raw in ("y", "yes", "1", "on")
    out = set_emergency_stop(en)
    if out is not None:
        print_json(out)
