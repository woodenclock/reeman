#!/usr/bin/env python3

from get_current_map import current_map_id, get_current_map
from get_map_overlays import extract_navigation_points, fetch_map_detail


def get_waypoints(map_id: int | None = None) -> list | None:
    """Navigation targets from active map overlays (landmarks / chargers / barcodes).

    AXBot does not expose a named-waypoint REST list — this parses ``overlays``
    GeoJSON from ``GET /maps/{id}``.
    """
    if map_id is None:
        mid = current_map_id()
    else:
        mid = int(map_id)
        if mid < 0:
            mid = current_map_id()
    if mid is None:
        print("Cannot resolve map id — load a map first (switch_map).")
        return None
    detail = fetch_map_detail(mid)
    if detail is None:
        return None
    return extract_navigation_points(detail)


if __name__ == "__main__":
    import sys

    m: int | None = None
    if len(sys.argv) > 1 and sys.argv[1].strip().lstrip("-").isdigit():
        m = int(sys.argv[1])
    if m is None:
        cm = get_current_map()
        if cm:
            print("Current map:", cm.get("map_name"), "id:", cm.get("id"))
        wps = get_waypoints()
    else:
        wps = get_waypoints(m)
    if wps is not None:
        if wps:
            from cli_tables import print_waypoints_table

            print_waypoints_table(wps)
        else:
            print("No waypoints in current map overlays.")
