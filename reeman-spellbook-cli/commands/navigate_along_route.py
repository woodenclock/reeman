#!/usr/bin/env python3
"""Convenience: POST /chassis/moves type=along_given_route."""

import argparse
import sys
from api_client import print_json

from navigate import navigate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="along_given_route move — requires --route and target pose.",
    )
    parser.add_argument("--route", required=True, help="CSV x1,y1,x2,y2,...")
    parser.add_argument("--target-x", type=float, required=True)
    parser.add_argument("--target-y", type=float, required=True)
    parser.add_argument("--target-ori", type=float, default=0.0)
    parser.add_argument("--detour-tolerance", type=float)
    parser.add_argument("--creator", default=None)
    args = parser.parse_args()
    out = navigate(
        args.target_x,
        args.target_y,
        args.target_ori,
        move_type="along_given_route",
        creator=args.creator,
        route_coordinates=args.route,
        detour_tolerance=args.detour_tolerance,
    )
    if out is None:
        sys.exit(1)
    print_json(out)


if __name__ == "__main__":
    main()
