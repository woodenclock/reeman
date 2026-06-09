#!/usr/bin/env python3
"""GET/PUT/DELETE /device/chrony/* — NTP time sync configuration (v2.7.1+)."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import parse_json_file, print_json, request_api


def get_chrony_conf() -> str | None:
    return request_api("GET", "/device/chrony/chrony.conf", prefer_text=True)


def get_chrony_sources() -> list | None:
    data = request_api("GET", "/device/chrony/sources")
    return data if isinstance(data, list) else data


def set_chrony_sources(sources: list[str]) -> dict | None:
    data = request_api("PUT", "/device/chrony/sources", json_body=sources)
    return data if isinstance(data, dict) else data


def reset_chrony_sources() -> dict | None:
    data = request_api("DELETE", "/device/chrony/sources")
    return data if isinstance(data, dict) else data


def get_chrony_allows() -> list | None:
    data = request_api("GET", "/device/chrony/allows")
    return data if isinstance(data, list) else data


def set_chrony_allows(rules: list[str]) -> dict | None:
    data = request_api("PUT", "/device/chrony/allows", json_body=rules)
    return data if isinstance(data, dict) else data


def disable_chrony_ntp_server() -> dict | None:
    data = request_api("DELETE", "/device/chrony/allows")
    return data if isinstance(data, dict) else data


def _load_string_array(path: str) -> list[str]:
    if path == "-":
        raw = sys.stdin.read()
        parsed = json.loads(raw)
    else:
        parsed = parse_json_file(path)
    if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
        print("JSON must be an array of strings.", file=sys.stderr)
        raise SystemExit(1)
    return parsed


def main() -> None:
    p = argparse.ArgumentParser(description="Chrony NTP configuration on robot")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("conf", help="GET /device/chrony/chrony.conf (plain text)")

    src = sub.add_parser("sources", help="NTP upstream sources")
    src_sub = src.add_subparsers(dest="action")
    src_sub.add_parser("get", help="GET /device/chrony/sources")
    set_src = src_sub.add_parser("set", help="PUT /device/chrony/sources")
    set_src.add_argument("json_path", nargs="?", default="-", help="JSON string array")
    src_sub.add_parser("reset", help="DELETE /device/chrony/sources — restore defaults")

    alw = sub.add_parser("allows", help="NTP server access rules")
    alw_sub = alw.add_subparsers(dest="action")
    alw_sub.add_parser("get", help="GET /device/chrony/allows")
    set_alw = alw_sub.add_parser("set", help="PUT /device/chrony/allows")
    set_alw.add_argument("json_path", nargs="?", default="-", help='JSON array, e.g. ["allow 192.168.0.0/16"]')
    alw_sub.add_parser("disable", help="DELETE /device/chrony/allows — disable NTP server")

    args = p.parse_args()

    if args.cmd == "conf":
        text = get_chrony_conf()
        if text is None:
            raise SystemExit(1)
        print(text, end="" if text.endswith("\n") else "\n")
        return

    if args.cmd == "sources":
        if args.action == "get":
            result = get_chrony_sources()
        elif args.action == "set":
            result = set_chrony_sources(_load_string_array(args.json_path))
        elif args.action == "reset":
            result = reset_chrony_sources()
        else:
            src.print_help()
            raise SystemExit(2)
    elif args.cmd == "allows":
        if args.action == "get":
            result = get_chrony_allows()
        elif args.action == "set":
            result = set_chrony_allows(_load_string_array(args.json_path))
        elif args.action == "disable":
            c = input("Disable robot NTP server? [y/N]: ").strip().lower()
            if c not in ("y", "yes"):
                print("Aborted.")
                raise SystemExit(0)
            result = disable_chrony_ntp_server()
        else:
            alw.print_help()
            raise SystemExit(2)
    else:
        p.print_help()
        raise SystemExit(2)

    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
