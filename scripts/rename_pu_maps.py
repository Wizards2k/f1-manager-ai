#!/usr/bin/env python3
"""Batch-rename PU map labels inside derived circuit configs.

Usage (from repo root):
    python3 scripts/rename_pu_maps.py \
        --root config/circuits/derived --pattern '**/pu_maps.json'

Features:
- Renames legacy map names (ECONOMY, STANDARD, RICH, QUALY, RECHARGE)
  to the new canonical names (PRACTICE, RACE, QUALIFY, SAFETY_CAR).
- Handles collisions by keeping the entry with the highest priority.
- Updates `maps`, `ers_budget.maps`, SOC warnings, and per-map notes.
- Prints progress every N files so long runs show percentage complete.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, Tuple

ENGINE_MAP_RENAME = {
    "RECHARGE": "SAFETY_CAR",
    "ECONOMY": "PRACTICE",
    "WET": "PRACTICE",  # Wet profiles share PRACTICE map params
    "STANDARD": "RACE",
    "RICH": "RACE",
    "QUALY": "QUALIFY",
    "QUALITY": "QUALIFY",
}

# Higher value wins when duplicate keys collide
ENGINE_MAP_PRIORITY = {
    "SAFETY_CAR": 10,
    "PRACTICE": 10,
    "RACE": 10,
    "QUALIFY": 10,
    # Legacy aliases, lower priority than canonical names
    "RECHARGE": 1,
    "ECONOMY": 1,
    "WET": 0,
    "STANDARD": 1,
    "RICH": 2,
    "QUALY": 1,
    "QUALITY": 1,
}

LEGACY_TOKENS = sorted(ENGINE_MAP_RENAME.keys(), key=len, reverse=True)


def _rename_token(text: str) -> str:
    for token in LEGACY_TOKENS:
        if token in text:
            text = text.replace(token, ENGINE_MAP_RENAME[token])
    return text


def _remap_map_dict(data: Dict[str, object]) -> Tuple[Dict[str, object], bool]:
    if not isinstance(data, dict):
        return data, False

    new_maps: Dict[str, object] = {}
    priority_seen: Dict[str, int] = {}
    changed = False

    for key, value in data.items():
        target_key = ENGINE_MAP_RENAME.get(key, key)
        prio = ENGINE_MAP_PRIORITY.get(key, ENGINE_MAP_PRIORITY.get(target_key, 0))
        prev = priority_seen.get(target_key, -1)
        if prio >= prev:
            priority_seen[target_key] = prio
            if target_key != key:
                changed = True
            new_maps[target_key] = deepcopy(value)
        else:
            changed = True  # Lower priority entry dropped

    return (new_maps if changed else data), changed


def _update_notes(map_entry: dict) -> bool:
    notes = map_entry.get("notes")
    if isinstance(notes, dict):
        name = notes.get("map")
        if isinstance(name, str):
            new_name = ENGINE_MAP_RENAME.get(name, name)
            if new_name != name:
                notes["map"] = new_name
                return True
    return False


def process_file(path: Path, dry_run: bool = False) -> bool:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    changed = False

    # maps
    maps = data.get("maps")
    if isinstance(maps, dict):
        new_maps, did_change = _remap_map_dict(maps)
        if did_change:
            data["maps"] = new_maps
            changed = True
        for entry in data["maps"].values():
            if _update_notes(entry):
                changed = True

    # ers budget maps + warnings
    ers_budget = data.get("ers_budget")
    if isinstance(ers_budget, dict):
        budget_maps = ers_budget.get("maps")
        if isinstance(budget_maps, dict):
            new_budget_maps, did_change = _remap_map_dict(budget_maps)
            if did_change:
                ers_budget["maps"] = new_budget_maps
                changed = True
        warnings = ers_budget.get("warnings")
        if isinstance(warnings, list):
            new_warn = [_rename_token(w) for w in warnings]
            if new_warn != warnings:
                ers_budget["warnings"] = new_warn
                changed = True

    # standalone warnings section
    soc = data.get("soc_warnings")
    if isinstance(soc, list):
        new_soc = [_rename_token(w) for w in soc]
        if new_soc != soc:
            data["soc_warnings"] = new_soc
            changed = True

    penalties = data.get("engine_map_penalties")
    if isinstance(penalties, dict):
        new_penalties, did_change = _remap_map_dict(penalties)
        if did_change:
            data["engine_map_penalties"] = new_penalties
            changed = True

    if changed and not dry_run:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def iter_files(root: Path, pattern: str) -> Iterable[Path]:
    if "**" in pattern or pattern.endswith(".json"):
        yield from root.glob(pattern)
    else:
        yield from root.rglob(pattern)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename legacy PU map labels inside JSON configs")
    parser.add_argument("--root", default="config/circuits/derived", help="Base folder to scan")
    parser.add_argument(
        "--pattern",
        default="**/pu_maps.json",
        help="Glob relative to root (default: **/pu_maps.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report files that would change")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-file progress output")
    parser.add_argument(
        "--progress-step",
        type=int,
        default=10,
        help="Print progress every N files (default: 10)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root folder {root} does not exist", file=sys.stderr)
        return 1

    files = sorted(iter_files(root, args.pattern))
    total = len(files)
    if not files:
        print("No files matched pattern", file=sys.stderr)
        return 1

    updated = 0
    for idx, path in enumerate(files, 1):
        changed = process_file(path, dry_run=args.dry_run)
        if changed:
            updated += 1
        if not args.quiet and (idx % args.progress_step == 0 or idx == total):
            pct = idx / total * 100.0
            status = "changed" if changed else "checked"
            print(f"[{idx:03}/{total}] {pct:5.1f}% {status} -> {path.relative_to(root)}")

    print(f"Done. {updated}/{total} files {'would be ' if args.dry_run else ''}updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
