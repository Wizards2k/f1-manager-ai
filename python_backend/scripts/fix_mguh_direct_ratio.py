#!/usr/bin/env python3
"""Fix mguh_direct_ratio values in all 24 circuit pu_maps.json files.

Correct values per FIA regulations:
- QUALIFY: 1.0 (100% direct to wheels)
- RACE: 0.45 (45% direct, 55% to battery)
- PRACTICE: 0.15 (15% direct, 85% to battery)
- SAFETY_CAR: 0.15 (15% direct, 85% to battery)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = ROOT.parent / "config" / "circuits" / "derived"

# Mapping from map name to correct direct_ratio
CORRECT_RATIOS = {
    "QUALIFY": 1.0,
    "RACE": 0.45,
    "PRACTICE": 0.15,
    "SAFETY_CAR": 0.15,
}

# Alternative names in ers_budget section
ERS_BUDGET_MAP_NAMES = {
    "OVERTAKE": "QUALIFY",     # 4.0 MJ deploy → QUALIFY
    "STANDARD": "RACE",         # 3.63 MJ deploy → RACE
    "RECHARGE": "SAFETY_CAR",   # 0.5 MJ deploy → SAFETY_CAR
}

def fix_circuit_pu_maps(circuit_path):
    """Fix mguh_direct_ratio in a single circuit pu_maps.json file."""
    with open(circuit_path) as f:
        data = json.load(f)

    changes = 0

    # Fix main maps section (PRACTICE, RACE, QUALIFY, SAFETY_CAR)
    if "maps" in data:
        for map_name, map_config in data["maps"].items():
            if map_name in CORRECT_RATIOS:
                old_val = map_config.get("mguh_direct_ratio")
                correct_val = CORRECT_RATIOS[map_name]
                if old_val != correct_val:
                    map_config["mguh_direct_ratio"] = correct_val
                    changes += 1
                    print(f"  {circuit_path.parent.name}: maps[{map_name}].mguh_direct_ratio: {old_val} → {correct_val}")

    # Fix ers_budget.maps section (RACE, QUALIFY, RECHARGE, STANDARD, OVERTAKE)
    if "ers_budget" in data and "maps" in data["ers_budget"]:
        for map_name, map_config in data["ers_budget"]["maps"].items():
            # Determine what this map name corresponds to
            if map_name in ERS_BUDGET_MAP_NAMES:
                primary_map = ERS_BUDGET_MAP_NAMES[map_name]
            else:
                primary_map = map_name  # Use name as-is for RACE, QUALIFY

            if primary_map in CORRECT_RATIOS:
                old_val = map_config.get("mguh_direct_ratio")
                correct_val = CORRECT_RATIOS[primary_map]
                if old_val != correct_val:
                    map_config["mguh_direct_ratio"] = correct_val
                    changes += 1
                    print(f"  {circuit_path.parent.name}: ers_budget.maps[{map_name}].mguh_direct_ratio: {old_val} → {correct_val}")

    # Write back if changes made
    if changes > 0:
        with open(circuit_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    return False

def main():
    circuits = sorted(CIRCUITS_DIR.glob("*/pu_maps.json"))

    print(f"\n{'='*70}")
    print(f"Fixing mguh_direct_ratio in {len(circuits)} circuit files")
    print(f"{'='*70}\n")

    updated_count = 0
    for circuit_path in circuits:
        if fix_circuit_pu_maps(circuit_path):
            updated_count += 1

    print(f"\n{'='*70}")
    print(f"Updated {updated_count}/{len(circuits)} files")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
