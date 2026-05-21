#!/usr/bin/env python3

from api_client import print_json, request_api


def set_control_mode(control_mode: str) -> dict | None:
    """POST /services/wheel_control/set_control_mode — auto | manual | remote."""
    data = request_api(
        "POST",
        "/services/wheel_control/set_control_mode",
        json_body={"control_mode": control_mode},
    )
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    import sys

    modes = ("auto", "manual", "remote")
    cm = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""
    if cm not in modes:
        from cli_tables import print_indexed_choices

        print_indexed_choices(modes, value_header="mode")
        u = input("Select mode [0–2]: ").strip()
        if u.isdigit() and 0 <= int(u) < len(modes):
            cm = modes[int(u)]
        else:
            print("Need auto/manual/remote")
            sys.exit(1)
    out = set_control_mode(cm)
    if out is not None:
        print_json(out)
