#!/usr/bin/env python3

from api_client import print_json, request_api


def list_moves() -> list | None:
    """GET /chassis/moves — full history."""
    data = request_api("GET", "/chassis/moves")
    return data if isinstance(data, list) else None


if __name__ == "__main__":
    moves = list_moves()
    if moves is not None:
        print_json(moves)
