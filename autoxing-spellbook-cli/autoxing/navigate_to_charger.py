#!/usr/bin/env python3

from api_client import print_json, request_api

DEFAULT_CREATOR = "autoxing_spellbook_cli"


def navigate_to_charger(*, creator: str | None = None) -> dict | None:
    """POST /chassis/moves with ``type: charge``."""
    data = request_api(
        "POST",
        "/chassis/moves",
        json_body={"creator": creator or DEFAULT_CREATOR, "type": "charge"},
    )
    return data if isinstance(data, dict) else None


if __name__ == "__main__":
    ans = input("Dispatch charge dock move? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("Aborted.")
    else:
        out = navigate_to_charger()
        if out is not None:
            print_json(out)
