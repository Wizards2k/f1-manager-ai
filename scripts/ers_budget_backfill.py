#!/usr/bin/env python3
"""Backfill ERS mode-specific budgets into circuit pu_maps.json files."""

from __future__ import annotations

import json
from pathlib import Path
import argparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = REPO_ROOT / "config" / "circuits" / "derived"

MODE_SPECS = {
    "RECHARGE": {
        "source": "SAFETY_CAR",
        "defaults": {
            "deploy_mj_per_lap": 0.45,
            "harvest_mj_per_lap": 2.0,
            "target_soc_end_lap": 0.95,
        },
        "bucket_primary_pct": 0.15,
        "bucket_secondary_pct": 0.25,
        "bucket_exit_pct": 0.60,
        "defense_reserve_mj": 0.10,
    },
    "STANDARD": {
        "source": "RACE",
        "defaults": {
            "deploy_mj_per_lap": 3.6,
            "harvest_mj_per_lap": 1.0,
            "target_soc_end_lap": 0.35,
        },
        "bucket_primary_pct": 0.55,
        "bucket_secondary_pct": 0.30,
        "bucket_exit_pct": 0.15,
        "defense_reserve_mj": 0.25,
    },
    "OVERTAKE": {
        "source": "QUALIFY",
        "defaults": {
            "deploy_mj_per_lap": 4.0,
            "harvest_mj_per_lap": 0.6,
            "target_soc_end_lap": 0.20,
        },
        "bucket_primary_pct": 0.70,
        "bucket_secondary_pct": 0.20,
        "bucket_exit_pct": 0.10,
        "defense_reserve_mj": 0.10,
    },
    "DEFENCE": {
        "source": "RACE",
        "defaults": {
            "deploy_mj_per_lap": 3.1,
            "harvest_mj_per_lap": 1.2,
            "target_soc_end_lap": 0.55,
        },
        "bucket_primary_pct": 0.35,
        "bucket_secondary_pct": 0.40,
        "bucket_exit_pct": 0.25,
        "defense_reserve_mj": 0.40,
    },
}

QUALIFY_BUCKETS = {
    "bucket_primary_pct": 0.65,
    "bucket_secondary_pct": 0.25,
    "bucket_exit_pct": 0.10,
    "defense_reserve_mj": 0.0,
}


def _round_if_number(value):
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    return value


def _ensure_mode_entry(maps: dict, mode: str, spec: dict) -> bool:
    entry = maps.get(mode)
    source = maps.get(spec["source"], {})
    changed = False
    if entry is None:
        entry = {}
        maps[mode] = entry
        changed = True

    defaults = spec.get("defaults", {})
    for field in ("deploy_mj_per_lap", "harvest_mj_per_lap", "target_soc_end_lap"):
        if entry.get(field) is None:
            value = source.get(field)
            if value is None:
                value = defaults.get(field)
            if value is not None:
                entry[field] = _round_if_number(value)
                changed = True

    for bucket_field in ("bucket_primary_pct", "bucket_secondary_pct", "bucket_exit_pct"):
        if entry.get(bucket_field) is None:
            entry[bucket_field] = spec.get(bucket_field)
            changed = True

    if entry.get("defense_reserve_mj") is None and spec.get("defense_reserve_mj") is not None:
        entry["defense_reserve_mj"] = spec["defense_reserve_mj"]
        changed = True

    return changed


def _ensure_qualify_buckets(maps: dict) -> bool:
    entry = maps.get("QUALIFY")
    if not entry:
        return False
    changed = False
    for field, default in QUALIFY_BUCKETS.items():
        if entry.get(field) is None:
            entry[field] = default
            changed = True
    return changed


def process_file(path: Path) -> bool:
    data = json.loads(path.read_text())
    budget = data.get("ers_budget")
    if not isinstance(budget, dict):
        return False
    maps = budget.setdefault("maps", {})
    changed = False

    for mode, spec in MODE_SPECS.items():
        changed |= _ensure_mode_entry(maps, mode, spec)

    changed |= _ensure_qualify_buckets(maps)

    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ERS mode budgets for circuit PU maps")
    parser.add_argument(
        "--circuit",
        help="Circuit ID (folder name under config/circuits/derived) to process",
    )
    args = parser.parse_args()

    if args.circuit:
        candidate = DERIVED_DIR / args.circuit / "pu_maps.json"
        paths = [candidate] if candidate.exists() else []
        if not paths:
            print(f"No pu_maps.json found for circuit '{args.circuit}'")
            return
    else:
        paths = sorted(DERIVED_DIR.glob("*/pu_maps.json"))

    updated_files = []
    for pu_map in paths:
        if process_file(pu_map):
            updated_files.append(str(pu_map.relative_to(REPO_ROOT)))

    if updated_files:
        print("Updated ERS modes in:")
        for rel in updated_files:
            print(f"  - {rel}")
    else:
        print("No ERS budget changes necessary.")
if __name__ == "__main__":
    main()
