#!/usr/bin/env python3
"""5g-http.cgi: CGI script for Quectel modem JSON API."""

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, "/usr/lib/python3")
sys.path.insert(0, str(__file__ and __import__("pathlib").Path(__file__).parent.parent / "src"))

from quectel.config import load_config
from quectel.modem import Modem


def json_response(data: dict, status: int = 200):
    """Output JSON response for CGI."""
    status_text = {200: "OK", 400: "Bad Request", 500: "Internal Server Error"}
    print(f"Status: {status} {status_text.get(status, 'Unknown')}")
    print("Content-Type: application/json")
    print("Access-Control-Allow-Origin: *")
    print()
    print(json.dumps(data, indent=2))


def get_status(modem: Modem) -> dict:
    """Get full modem status."""
    device = modem.get_device_info()
    network = modem.get_network_info()
    lte, nr5g = modem.get_serving_cell()
    ca = modem.get_carrier_aggregation()
    neighbours = modem.get_neighbour_cells()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device": asdict(device) if device else None,
        "network": asdict(network) if network else None,
        "serving": {
            "lte": asdict(lte) if lte else None,
            "nr5g": asdict(nr5g) if nr5g else None,
        },
        "carrier_aggregation": [asdict(c) for c in ca],
        "neighbours": [asdict(n) for n in neighbours],
    }


def get_device(modem: Modem) -> dict:
    """Get device info only."""
    device = modem.get_device_info()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device": asdict(device) if device else None,
    }


def get_serving(modem: Modem) -> dict:
    """Get serving cell info only."""
    lte, nr5g = modem.get_serving_cell()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serving": {
            "lte": asdict(lte) if lte else None,
            "nr5g": asdict(nr5g) if nr5g else None,
        },
    }


def get_ca(modem: Modem) -> dict:
    """Get carrier aggregation info only."""
    ca = modem.get_carrier_aggregation()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "carrier_aggregation": [asdict(c) for c in ca],
    }


def get_neighbours(modem: Modem) -> dict:
    """Get neighbour cells only."""
    neighbours = modem.get_neighbour_cells()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "neighbours": [asdict(n) for n in neighbours],
    }


def main():
    # Parse query string
    query_string = os.environ.get("QUERY_STRING", "")
    params = {}
    for part in query_string.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            params[key] = value

    action = params.get("action", "status")

    try:
        config = load_config()
        modem = Modem.from_config(config)
    except Exception as e:
        json_response({"error": f"Modem connection failed: {e}"}, status=500)
        return

    try:
        if action == "status":
            data = get_status(modem)
        elif action == "device":
            data = get_device(modem)
        elif action == "serving":
            data = get_serving(modem)
        elif action == "ca":
            data = get_ca(modem)
        elif action == "neighbours":
            data = get_neighbours(modem)
        else:
            json_response(
                {"error": f"Unknown action: {action}", "valid_actions": ["status", "device", "serving", "ca", "neighbours"]},
                status=400,
            )
            return

        json_response(data)

    except Exception as e:
        json_response({"error": f"Query failed: {e}"}, status=500)


if __name__ == "__main__":
    main()
