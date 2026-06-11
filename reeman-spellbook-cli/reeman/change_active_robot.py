#!/usr/bin/env python3
"""Select active robot by index in ``credentials/CONSTANTS.yml``."""

from __future__ import annotations

import sys

from credentials import CONFIG_PATH, list_robots, migrate_from_constants_py, robot_config, set_active_index
from credentials._config import active_index as get_active_index
from credentials._config import ensure_config


def main() -> None:
    try:
        if not CONFIG_PATH.is_file():
            migrate_from_constants_py()
        data = ensure_config()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    robots = list_robots(data)
    current = get_active_index(data)

    from cli_tables import print_robots_table

    print_robots_table(robots)
    print(f"Current active_index: {current} ({robots[current]['name']})")

    if len(robots) == 1:
        if current != 0:
            set_active_index(0)
            print("Set active_index to 0.")
        return

    while True:
        choice = input("Select robot index (Enter to keep current): ").strip()
        if choice == "":
            cfg = robot_config()
            print(f"Unchanged — active robot: {cfg.ROBOT_NAME} ({cfg.ROBOT_IP})")
            return
        if choice.isdigit() and 0 <= int(choice) < len(robots):
            cfg = set_active_index(int(choice))
            print(f"Active robot: {cfg.ROBOT_NAME} ({cfg.ROBOT_IP})")
            return
        print("Invalid index.")


if __name__ == "__main__":
    main()
