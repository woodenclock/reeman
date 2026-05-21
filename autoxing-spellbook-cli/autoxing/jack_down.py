#!/usr/bin/env python3
"""Lower jack device — POST /services/jack_down (monitor progress via ``jack_state``)."""

from api_client import print_json, request_api


def jack_down() -> dict | None:
    """POST /services/jack_down — lower jack; monitor via WebSocket ``/jack_state``."""
    data = request_api("POST", "/services/jack_down", json_body={})
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    out = jack_down()
    if out is not None:
        print_json(out)
