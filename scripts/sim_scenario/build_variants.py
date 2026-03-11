#!/usr/bin/env python3
"""Generate derived sim_scenario snapshots from a base JSON template."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_BACKEND = REPO_ROOT / "python_backend"
if str(PYTHON_BACKEND) not in sys.path:
    sys.path.append(str(PYTHON_BACKEND))

from services.setup_engine_service import SetupEngineService  # type: ignore  # noqa: E402

VARIANTS = [
    {
        "name": "suzuka_leclerc_setup_green",
        "description": "Balanced green setup with calmer rear axle and higher stability",
        "patch": {
            "car": {
                "setup_sliders": {
                    "front_wing": 49,
                    "rear_wing": 54,
                    "beam_wing": 52,
                    "ride_height_front": 49,
                    "ride_height_rear": 55,
                    "suspension_front": 48,
                    "suspension_rear": 46,
                    "antiroll_front": 49,
                    "antiroll_rear": 45,
                    "brake_balance": 54,
                    "brake_duct": 50
                },
                "state": {
                    "brakes": {
                        "duct_opening": 0.50,
                        "bias_front_pct": 54.0
                    }
                },
                "aero_setup": {
                    "front_wing": {"angle_deg": 47.0},
                    "rear_wing": {"angle_deg": 55.0},
                    "beam_wing": {"angle_deg": 42.0},
                    "suspension_front": {"rigidity": 0.53, "efficiency": 0.84},
                    "suspension_rear": {"rigidity": 0.52, "efficiency": 0.86},
                    "antiroll_front_rigidity": 0.50,
                    "antiroll_rear_rigidity": 0.47,
                    "ride_height_front_mm": 39.0,
                    "ride_height_rear_mm": 55.0
                }
            }
        },
    },
    {
        "name": "suzuka_leclerc_oversteer_slippery_rear",
        "description": "Oversteery setup with lighter rear axle and slippery rear traction behaviour",
        "patch": {
            "car": {
                "setup_sliders": {
                    "front_wing": 58,
                    "rear_wing": 40,
                    "beam_wing": 40,
                    "ride_height_front": 46,
                    "ride_height_rear": 57,
                    "suspension_front": 50,
                    "suspension_rear": 64,
                    "antiroll_front": 49,
                    "antiroll_rear": 66,
                    "brake_balance": 50,
                    "brake_duct": 42
                },
                "state": {
                    "brakes": {
                        "duct_opening": 0.42,
                        "bias_front_pct": 50.0
                    }
                },
                "aero_setup": {
                    "front_wing": {"angle_deg": 54.0},
                    "rear_wing": {"angle_deg": 42.0},
                    "beam_wing": {"angle_deg": 34.0},
                    "suspension_front": {"rigidity": 0.54, "efficiency": 0.82},
                    "suspension_rear": {"rigidity": 0.70, "efficiency": 0.78},
                    "antiroll_front_rigidity": 0.50,
                    "antiroll_rear_rigidity": 0.68,
                    "ride_height_front_mm": 37.0,
                    "ride_height_rear_mm": 57.0
                }
            }
        },
    },
    {
        "name": "suzuka_leclerc_push3",
        "description": "Push level 3 (moderate conserve)",
        "patch": {
            "car": {"push_level": 3.0},
        },
    },
    {
        "name": "suzuka_leclerc_push1",
        "description": "Push level 1 (full conserve)",
        "patch": {
            "car": {"push_level": 1.0},
        },
    },
    {
        "name": "suzuka_leclerc_brakeduct60",
        "description": "Brake duct slider 60 (duct opening 0.60)",
        "patch": {
            "car": {
                "setup_sliders": {"brake_duct": 60},
                "state": {"brakes": {"duct_opening": 0.60}},
            }
        },
    },
    {
        "name": "suzuka_leclerc_brakeduct80",
        "description": "Brake duct slider 80 (duct opening 0.80)",
        "patch": {
            "car": {
                "setup_sliders": {"brake_duct": 80},
                "state": {"brakes": {"duct_opening": 0.80}},
            }
        },
    },
    {
        "name": "suzuka_leclerc_rear_relief",
        "description": "Rear downforce relief (less rear wing, higher ride height)",
        "patch": {
            "car": {
                "setup_sliders": {
                    "rear_wing": 46,
                    "ride_height_rear": 55,
                    "ride_height_front": 49,
                },
                "aero_setup": {
                    "rear_wing": {"angle_deg": 46.0},
                    "front_wing": {"angle_deg": 47.0},
                    "ride_height_rear_mm": 55.0,
                    "ride_height_front_mm": 39.5,
                },
            }
        },
    },
    {
        "name": "suzuka_leclerc_brakes_cool",
        "description": "Cool brake starting temps (front 600C, rear 560C)",
        "patch": {
            "car": {
                "state": {
                    "brakes": {
                        "temp_front_c": 600.0,
                        "temp_rear_c": 560.0,
                    }
                }
            }
        },
    },
    {
        "name": "suzuka_leclerc_push1_brakes_hot",
        "description": "Push level 1 but brake temps hot (front 820C, rear 780C)",
        "patch": {
            "car": {
                "push_level": 1.0,
                "state": {
                    "brakes": {
                        "temp_front_c": 820.0,
                        "temp_rear_c": 780.0,
                    }
                },
            }
        },
    },
]

CIRCUIT_GREEN_VARIANTS = {
    "it-1922_monza": {
        "name": "monza_leclerc_setup_green",
        "description": "Circuit-specific green setup for Monza using setup ranges and Pirelli nomination",
        "circuit_name": "Monza",
        "compound_slot": "M",
    },
    "gb-1948_silverstone": {
        "name": "silverstone_leclerc_setup_green",
        "description": "Circuit-specific green setup for Silverstone using setup ranges and Pirelli nomination",
        "circuit_name": "Silverstone",
        "compound_slot": "M",
    },
    "mc-1929_monaco": {
        "name": "monaco_leclerc_setup_green",
        "description": "Circuit-specific green setup for Monaco using setup ranges and Pirelli nomination",
        "circuit_name": "Monaco",
        "compound_slot": "M",
    },
    "be-1925_spa_francorchamps": {
        "name": "spa_leclerc_setup_green",
        "description": "Circuit-specific green setup for Spa using setup ranges and Pirelli nomination",
        "circuit_name": "Spa-Francorchamps",
        "compound_slot": "M",
    },
    "es-1991_barcelona": {
        "name": "barcelona_leclerc_setup_green",
        "description": "Circuit-specific green setup for Barcelona using setup ranges and Pirelli nomination",
        "circuit_name": "Barcelona",
        "compound_slot": "M",
    },
}

PIRELLI_PROFILE_PATH = REPO_ROOT / "config" / "tyres" / "pirelli_track_profile_2025.json"
DEFAULT_TYRE_SURFACE_TEMP_C = 95.0
DEFAULT_TYRE_CORE_TEMP_C = 90.0
DEFAULT_TYRE_WEAR_PCT = 0.0
DEFAULT_TYRE_LAP_AGE = 0


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _build_clean_tyre_state(compound: str, tyre_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = tyre_state or {}
    return {
        "compound": compound,
        "surface_temp_c": source.get("surface_temp_c", DEFAULT_TYRE_SURFACE_TEMP_C)
        if source.get("surface_temp_c") in {DEFAULT_TYRE_SURFACE_TEMP_C}
        else DEFAULT_TYRE_SURFACE_TEMP_C,
        "core_temp_c": source.get("core_temp_c", DEFAULT_TYRE_CORE_TEMP_C)
        if source.get("core_temp_c") in {DEFAULT_TYRE_CORE_TEMP_C}
        else DEFAULT_TYRE_CORE_TEMP_C,
        "wear_pct": source.get("wear_pct", DEFAULT_TYRE_WEAR_PCT)
        if source.get("wear_pct") in {DEFAULT_TYRE_WEAR_PCT}
        else DEFAULT_TYRE_WEAR_PCT,
        "lap_age": source.get("lap_age", DEFAULT_TYRE_LAP_AGE)
        if source.get("lap_age") in {DEFAULT_TYRE_LAP_AGE}
        else DEFAULT_TYRE_LAP_AGE,
    }


def _find_pirelli_nomination(circuit_name: str) -> Dict[str, str]:
    payload = _load_json(PIRELLI_PROFILE_PATH)
    for entry in payload.get("calendar", []):
        if str(entry.get("circuit", "")).lower() in {circuit_name.lower(), "monte carlo" if circuit_name.lower() == "monaco" else circuit_name.lower()}:
            return dict(entry.get("nomination", {}))
    raise SystemExit(f"Pirelli nomination not found for circuit '{circuit_name}'")


def _build_circuit_green_patch(base_data: Dict[str, Any], circuit_id: str, circuit_name: str, compound_slot: str) -> Dict[str, Any]:
    base_car = base_data.get("car", {})
    base_state = base_car.get("state", {})
    base_aero = copy.deepcopy(base_car.get("aero_setup", {}))
    base_brakes = copy.deepcopy(base_state.get("brakes", {}))

    ideal_setup = SetupEngineService.build_ideal_setup(circuit_id, object())
    _, mapping = SetupEngineService.get_circuit_mapping(circuit_id)
    physics = SetupEngineService.map_slider_to_physics(ideal_setup, mapping)
    nomination = _find_pirelli_nomination(circuit_name)
    compound = nomination.get(compound_slot)
    if not compound:
        raise SystemExit(f"Compound slot '{compound_slot}' not found for circuit '{circuit_name}'")

    patch = {
        "car": {
            "setup_sliders": ideal_setup,
            "ideal_setup_sliders": ideal_setup,
            "state": {
                "brakes": {
                    "temp_front_c": 400.0,
                    "temp_rear_c": 350.0,
                    "duct_opening": round(float(physics.get("brake_duct_open", base_brakes.get("duct_opening", 0.5))), 3),
                    "bias_front_pct": round(float(physics.get("brake_balance_pct", base_brakes.get("bias_front_pct", 54.0))), 1),
                },
                "tyres": {},
            },
            "aero_setup": base_aero,
        }
    }

    for tyre_key, tyre_state in base_state.get("tyres", {}).items():
        patch["car"]["state"]["tyres"][tyre_key] = _build_clean_tyre_state(compound, tyre_state)

    front_wing = patch["car"]["aero_setup"].setdefault("front_wing", {})
    rear_wing = patch["car"]["aero_setup"].setdefault("rear_wing", {})
    beam_wing = patch["car"]["aero_setup"].setdefault("beam_wing", {})
    susp_front = patch["car"]["aero_setup"].setdefault("suspension_front", {})
    susp_rear = patch["car"]["aero_setup"].setdefault("suspension_rear", {})

    front_wing["angle_deg"] = float(physics.get("front_wing_deg", front_wing.get("angle_deg", 47.0)))
    rear_wing["angle_deg"] = float(physics.get("rear_wing_deg", rear_wing.get("angle_deg", 55.0)))
    beam_wing["angle_deg"] = float(physics.get("beam_wing_deg", beam_wing.get("angle_deg", 42.0)))
    susp_front["rigidity"] = round(float(physics.get("suspension_front_rigidity", susp_front.get("rigidity", 0.53))), 3)
    susp_front["efficiency"] = round(float(physics.get("suspension_front_efficiency", susp_front.get("efficiency", 0.84))), 3)
    susp_rear["rigidity"] = round(float(physics.get("suspension_rear_rigidity", susp_rear.get("rigidity", 0.52))), 3)
    susp_rear["efficiency"] = round(float(physics.get("suspension_rear_efficiency", susp_rear.get("efficiency", 0.86))), 3)
    patch["car"]["aero_setup"]["antiroll_front_rigidity"] = round(float(physics.get("antiroll_front_rigidity", patch["car"]["aero_setup"].get("antiroll_front_rigidity", 0.5))), 3)
    patch["car"]["aero_setup"]["antiroll_rear_rigidity"] = round(float(physics.get("antiroll_rear_rigidity", patch["car"]["aero_setup"].get("antiroll_rear_rigidity", 0.47))), 3)
    patch["car"]["aero_setup"]["ride_height_front_mm"] = round(float(physics.get("ride_height_front_mm", patch["car"]["aero_setup"].get("ride_height_front_mm", 39.0))), 1)
    patch["car"]["aero_setup"]["ride_height_rear_mm"] = round(float(physics.get("ride_height_rear_mm", patch["car"]["aero_setup"].get("ride_height_rear_mm", 55.0))), 1)

    return patch


def _build_generated_variants(base_data: Dict[str, Any], selected_circuits: Optional[List[str]]) -> List[Dict[str, Any]]:
    variants = copy.deepcopy(VARIANTS)
    circuit_ids = selected_circuits or list(CIRCUIT_GREEN_VARIANTS.keys())
    for circuit_id in circuit_ids:
        spec = CIRCUIT_GREEN_VARIANTS.get(circuit_id)
        if spec is None:
            raise SystemExit(f"Unsupported circuit for green scenario generation: {circuit_id}")
        variants.append(
            {
                "name": spec["name"],
                "description": spec["description"],
                "patch": _build_circuit_green_patch(
                    base_data,
                    circuit_id,
                    spec["circuit_name"],
                    spec["compound_slot"],
                ),
            }
        )
    return variants


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate scenario variants")
    parser.add_argument(
        "--base",
        default=str(Path("scripts/sim_scenario/scenarios/suzuka_leclerc_push5.json")),
        help="Path to base scenario JSON",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("scripts/sim_scenario/scenarios")),
        help="Directory where variants will be written",
    )
    parser.add_argument(
        "--circuits",
        nargs="*",
        help="Optional circuit IDs for generating circuit-specific green scenarios",
    )
    args = parser.parse_args()

    base_path = Path(args.base)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_data = json.loads(base_path.read_text(encoding="utf-8"))

    variants = _build_generated_variants(base_data, args.circuits)

    for variant in variants:
        data = copy.deepcopy(base_data)
        _deep_merge(data, variant["patch"])
        tyres = data.setdefault("car", {}).setdefault("state", {}).setdefault("tyres", {})
        for tyre_key, tyre_state in list(tyres.items()):
            compound = tyre_state.get("compound", "C3")
            tyres[tyre_key] = _build_clean_tyre_state(str(compound), tyre_state)
        meta = data.setdefault("meta", {})
        meta["name"] = variant["name"]
        meta["description"] = variant["description"]
        target_path = output_dir / f"{variant['name']}.json"
        target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Generated {target_path}")


if __name__ == "__main__":
    main()
