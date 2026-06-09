#!/usr/bin/env python3

from api_client import print_json, request_api

REQUEST_TIMEOUT = 60


def restart_service() -> dict | None:
    """POST /services/restart_service — restarts robot software stack."""
    data = request_api("POST", "/services/restart_service", json_body={}, timeout=REQUEST_TIMEOUT)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    confirm = input("Restart all robot software services? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
    else:
        out = restart_service()
        if out is not None:
            print_json(out)
