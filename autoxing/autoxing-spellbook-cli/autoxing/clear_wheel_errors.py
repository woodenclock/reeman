#!/usr/bin/env python3

from api_client import print_json, request_api


def clear_wheel_errors() -> dict | None:
    """POST /services/wheel_control/clear_errors."""
    data = request_api("POST", "/services/wheel_control/clear_errors", json_body={})
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    out = clear_wheel_errors()
    if out is not None:
        print_json(out)
