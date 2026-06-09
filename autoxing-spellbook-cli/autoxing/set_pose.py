#!/usr/bin/env python3

from api_client import request_api


def set_pose(x: float, y: float, ori: float, *, z: float = 0.0, adjust_position: bool = True) -> bool:
    """POST /chassis/pose — localize on current map (radians CCW from East)."""
    payload = {
        "position": [float(x), float(y), float(z)],
        "ori": float(ori),
        "adjust_position": bool(adjust_position),
    }
    data = request_api("POST", "/chassis/pose", json_body=payload)
    return data is not None


def _interactive_pick_waypoint():
    from cli_tables import print_waypoints_table
    from get_waypoints import get_waypoints

    wps = get_waypoints()
    if not wps:
        print("No waypoints from overlays — enter pose manually.")
        return None
    print_waypoints_table(wps)
    u = input("Waypoint index [blank = manual]: ").strip()
    if not u.isdigit() or int(u) >= len(wps) or int(u) < 0:
        return None
    return wps[int(u)]


if __name__ == "__main__":
    import sys

    adj_in = True
    if len(sys.argv) >= 4:
        fx, fy, fo = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
        ok = set_pose(fx, fy, fo, adjust_position=adj_in)
        print("OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)

    pick = _interactive_pick_waypoint()
    if pick is not None:
        ok = set_pose(pick["x"], pick["y"], pick["ori"], adjust_position=adj_in)
        print("OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)

    print("Manual pose: x y ori (radians, CCW from East)")
    line = input("x y ori: ").strip().split()
    if len(line) != 3:
        print("Need three numbers.")
        sys.exit(1)
    x, y, o = float(line[0]), float(line[1]), float(line[2])
    yn = input("adjust_position=true? [Y/n]: ").strip().lower()
    adj_in = yn not in ("n", "no")
    ok = set_pose(x, y, o, adjust_position=adj_in)
    print("OK" if ok else "FAILED")
