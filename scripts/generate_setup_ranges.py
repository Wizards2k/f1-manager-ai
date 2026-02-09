#!/usr/bin/env python3
"""Generate setup ranges JSON files from setup_mapping_v2.json.

Outputs: config/setup/setup_ranges/<circuit_id or key>.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DEFAULT_SETUP_FIELDS = [
    "front_wing",
    "rear_wing",
    "beam_wing",
    "ride_height_front",
    "ride_height_rear",
    "suspension_front",
    "suspension_rear",
    "antiroll_front",
    "antiroll_rear",
    "brake_balance",
    "brake_duct",
]

BASE_FIELD_PARAMS = {
    "front_wing": {"optimal": 52, "tolerance": 6, "range": (42, 70), "weight": 1.1},
    "rear_wing": {"optimal": 58, "tolerance": 6, "range": (45, 75), "weight": 1.0},
    "beam_wing": {"optimal": 50, "tolerance": 8, "range": (35, 70), "weight": 0.7},
    "ride_height_front": {"optimal": 48, "tolerance": 8, "range": (30, 70), "weight": 0.8},
    "ride_height_rear": {"optimal": 55, "tolerance": 8, "range": (35, 75), "weight": 0.8},
    "suspension_front": {"optimal": 50, "tolerance": 10, "range": (20, 80), "weight": 0.6},
    "suspension_rear": {"optimal": 50, "tolerance": 10, "range": (20, 80), "weight": 0.6},
    "antiroll_front": {"optimal": 50, "tolerance": 10, "range": (20, 80), "weight": 0.5},
    "antiroll_rear": {"optimal": 50, "tolerance": 10, "range": (20, 80), "weight": 0.5},
    "brake_balance": {"optimal": 50, "tolerance": 6, "range": (40, 60), "weight": 0.4},
    "brake_duct": {"optimal": 50, "tolerance": 10, "range": (30, 70), "weight": 0.4},
}


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "config" / "setup" / "setup_mapping_v2.json"
OUTPUT_DIR = REPO_ROOT / "config" / "setup" / "setup_ranges"


def build_ranges_payload(mapping_key: str, mapping: dict) -> dict:
    ranges = {}
    for field in DEFAULT_SETUP_FIELDS:
        params = BASE_FIELD_PARAMS.get(field, {})
        min_range, max_range = params.get("range", (0, 100))
        ranges[field] = {
            "min": int(min_range),
            "max": int(max_range),
            "target": int(params.get("optimal", 50)),
            "tolerance": int(params.get("tolerance", 10)),
            "weight": float(params.get("weight", 1.0)),
        }

    metadata = mapping.get("metadata", {}) if isinstance(mapping, dict) else {}
    circuit_id = metadata.get("circuit_id") or metadata.get("circuitId")

    return {
        "circuit_key": mapping_key,
        "circuit_id": circuit_id,
        "ranges": ranges,
        "source": {
            "mapping_file": str(MAPPING_PATH.relative_to(REPO_ROOT)),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with MAPPING_PATH.open("r", encoding="utf-8") as handle:
        mapping_data = json.load(handle)

    for key, entry in mapping_data.items():
        if key.startswith("_"):
            continue
        payload = build_ranges_payload(key, entry)
        filename = payload.get("circuit_id") or key
        output_path = OUTPUT_DIR / f"{filename}.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    print(f"Generated setup ranges in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
