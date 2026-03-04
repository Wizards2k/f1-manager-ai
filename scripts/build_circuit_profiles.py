#!/usr/bin/env python3
"""
Build per-circuit derived profiles by merging global defaults, raw circuit data (Pirelli/telemetry), and setup bounds.
Outputs JSONs under config/circuits/derived/<circuit_id>/ for tyres, brakes, PU, and damage.

This is a skeleton: fill in merge logic and data contracts before use.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
RAW_CIRCUITS = ROOT / "python_backend" / "data" / "circuits"
DERIVED_BASE = CONFIG / "circuits" / "derived"
CALIBRATION_BASE = CONFIG / "calibration"

GLOBAL_DEFAULTS = {
    "tyres": CONFIG / "tyres" / "tyre_params_global_default.json",
    "brakes": CONFIG / "brakes" / "brake_params_global_default.json",
    "pu_maps": CONFIG / "pu" / "pu_maps_global_default.json",
    "pu_reliability": CONFIG / "pu" / "pu_reliability_global_default.json",
    "damage": CONFIG / "damage" / "damage_coeffs_global_default.json",
}

CALIBRATION_PATHS = {
    "tyres": CALIBRATION_BASE / "tyres",
    "brakes": CALIBRATION_BASE / "brakes",
    "pu": CALIBRATION_BASE / "pu",
}

SETUP_BOUNDS = CONFIG / "setup" / "setup_mapping_v2.json"

WEAR_RATE_REF = 0.18


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def find_setup_entry(setup_bounds: Dict[str, Any], circuit_id: str) -> Tuple[str, Dict[str, Any]]:
    for key, payload in setup_bounds.items():
        if key in {"_meta", "default"}:
            continue
        metadata = payload.get("metadata", {})
        if metadata.get("circuit_id") == circuit_id or key == circuit_id:
            return key, payload
    return "default", setup_bounds.get("default", {})


def load_telemetry(circuit_id: str) -> Optional[Dict[str, Any]]:
    telemetry_path = RAW_CIRCUITS / f"{circuit_id}_Telemetry.json"
    if telemetry_path.exists():
        return load_json(telemetry_path)
    return None


def extract_pirelli_context(setup_entry: Dict[str, Any]) -> Dict[str, Any]:
    return setup_entry.get("pirelli_context", {})


def extract_cluster_metrics(setup_entry: Dict[str, Any]) -> Dict[str, Any]:
    return setup_entry.get("cluster_context", {}).get("metrics", {})


def extract_setup_bounds(setup_entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "brake_duct": setup_entry.get("brake_duct", {}),
        "brake_balance": setup_entry.get("brake_balance", {}),
        "ride_height_front": setup_entry.get("ride_height_front", {}),
        "ride_height_rear": setup_entry.get("ride_height_rear", {}),
        "suspension_front": setup_entry.get("suspension_front", {}),
        "suspension_rear": setup_entry.get("suspension_rear", {}),
    }


def build_penalty_profile(telemetry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fuel_mass = (telemetry or {}).get("fuel_mass", {})
    fuel_lap_delta_ms = fuel_mass.get("fuel_lap_delta_ms", 35.0)
    try:
        coeff = float(fuel_lap_delta_ms) / 1000.0
    except (TypeError, ValueError):
        coeff = 0.035

    profile: Dict[str, Any] = {
        "fuel_reference_kg": 10.0,
        "fuel_penalty_coeff": round(coeff, 6),
    }

    meta = profile.setdefault("_meta", {})
    meta["source"] = "telemetry.fuel_mass.fuel_lap_delta_ms"
    meta["fuel_lap_delta_ms"] = fuel_lap_delta_ms
    return profile


def build_tyres(global_tyres: Dict[str, Any], pirelli_context: Dict[str, Any]) -> Dict[str, Any]:
    derived = deepcopy(global_tyres)
    track_features = pirelli_context.get("track_features", {})
    bumps = track_features.get("bumps", 0) or 0
    kerbs = track_features.get("kerbs", 0) or 0
    avg_speed_rating = track_features.get("avg_speed_rating", 3) or 3
    wear_rate_base = pirelli_context.get("wear_rate_base")

    wear_rate_multiplier = 1.0
    if isinstance(wear_rate_base, (int, float)) and wear_rate_base > 0:
        wear_rate_multiplier = wear_rate_base / WEAR_RATE_REF

    bump_multiplier = 1.0 + (bumps * 0.02) + (kerbs * 0.03)
    cooling_multiplier = clamp(1.0 + (avg_speed_rating - 3) * 0.04, 0.85, 1.15)

    compounds = derived.get("compounds", {})
    for compound in compounds.values():
        base_wear = compound.get("wear_rate_base_pct_per_km")
        if isinstance(base_wear, (int, float)):
            compound["wear_rate_base_pct_per_km"] = base_wear * wear_rate_multiplier * bump_multiplier
        cooling = compound.get("cooling_coeff")
        if isinstance(cooling, (int, float)):
            compound["cooling_coeff"] = cooling * cooling_multiplier

    meta = derived.setdefault("_meta", {})
    meta["derived_context"] = {
        "track_features": track_features,
        "wear_rate_base": wear_rate_base,
        "wear_rate_multiplier": round(wear_rate_multiplier, 3),
        "bump_multiplier": round(bump_multiplier, 3),
        "cooling_multiplier": round(cooling_multiplier, 3),
    }
    return derived


def map_brake_duct_requirement(value: Optional[str]) -> float:
    if not value:
        return 1.0
    lowered = value.lower()
    if "minimum" in lowered:
        return 0.95
    if "maximum" in lowered:
        return 1.08
    if "medium" in lowered:
        return 1.0
    return 1.0


def build_brakes(global_brakes: Dict[str, Any], setup_entry: Dict[str, Any], cluster_metrics: Dict[str, Any]) -> Dict[str, Any]:
    derived = deepcopy(global_brakes)
    heavy_brake_events = cluster_metrics.get("heavy_brake_events") or 0
    duct_requirement = setup_entry.get("cooling_guidance", {}).get("brake_duct_requirement")
    duct_factor = map_brake_duct_requirement(duct_requirement)
    heavy_factor = clamp(1.0 + heavy_brake_events * 0.04, 1.0, 1.2)

    systems = derived.get("systems", {})
    for system in systems.values():
        cooling = system.get("cooling_coeff")
        if isinstance(cooling, (int, float)):
            system["cooling_coeff"] = cooling * duct_factor * heavy_factor

    if "defaults" in derived and "brake_duct" in setup_entry:
        derived["defaults"]["duct_opening_range"] = setup_entry.get("brake_duct", {})

    meta = derived.setdefault("_meta", {})
    meta["derived_context"] = {
        "heavy_brake_events": heavy_brake_events,
        "brake_duct_requirement": duct_requirement,
        "cooling_multiplier": round(duct_factor * heavy_factor, 3),
    }
    return derived


def build_pu_maps(global_pu_maps: Dict[str, Any], setup_entry: Dict[str, Any]) -> Dict[str, Any]:
    derived = deepcopy(global_pu_maps)
    avg_temp_delta = setup_entry.get("cooling_guidance", {}).get("avg_track_temp_delta_c")
    temp_factor = 1.0
    if isinstance(avg_temp_delta, (int, float)):
        temp_factor = clamp(1.0 + (avg_temp_delta / 25.0) * 0.04, 0.9, 1.1)

    for mapping in derived.get("maps", {}).values():
        cooling_share = mapping.get("cooling_share")
        if isinstance(cooling_share, (int, float)):
            mapping["cooling_share"] = clamp(cooling_share * temp_factor, 0.3, 0.7)

    energy_profile = setup_entry.get("energy_profile", {})
    meta = derived.setdefault("_meta", {})
    meta["derived_context"] = {
        "avg_track_temp_delta_c": avg_temp_delta,
        "cooling_share_multiplier": round(temp_factor, 3),
        "fuel_burn_intensity": energy_profile.get("fuel_burn_intensity"),
        "ers_deployment_style": energy_profile.get("ers_deployment_style"),
    }
    return derived


def build_damage(global_damage: Dict[str, Any], setup_entry: Dict[str, Any], pirelli_context: Dict[str, Any]) -> Dict[str, Any]:
    derived = deepcopy(global_damage)
    track_features = pirelli_context.get("track_features") or {}
    bumps = track_features.get("bumps", 0) or 0
    kerbs = track_features.get("kerbs", 0) or 0

    ride_height_front = setup_entry.get("ride_height_front", {})
    ride_height_rear = setup_entry.get("ride_height_rear", {})
    min_front = ride_height_front.get("min_mm") if ride_height_front else None
    min_rear = ride_height_rear.get("min_mm") if ride_height_rear else None

    shock_scale = 1.0 - (bumps * 0.02 + kerbs * 0.03)
    if isinstance(min_front, (int, float)) and min_front < 30:
        shock_scale -= 0.03
    if isinstance(min_rear, (int, float)) and min_rear < 40:
        shock_scale -= 0.03
    shock_scale = clamp(shock_scale, 0.7, 1.05)

    for component in derived.get("components", {}).values():
        for key in ("shock_threshold", "shock_threshold_high_kerb"):
            value = component.get(key)
            if isinstance(value, (int, float)):
                component[key] = value * shock_scale

    meta = derived.setdefault("_meta", {})
    meta["derived_context"] = {
        "track_features": track_features,
        "ride_height_min_front": min_front,
        "ride_height_min_rear": min_rear,
        "shock_threshold_multiplier": round(shock_scale, 3),
    }
    return derived


def add_common_meta(payload: Dict[str, Any], circuit_id: str, setup_key: str, telemetry: Optional[Dict[str, Any]]) -> None:
    meta = payload.setdefault("_meta", {})
    meta["circuit_id"] = circuit_id
    meta["setup_profile_key"] = setup_key
    meta["built_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if telemetry:
        meta["circuit_name"] = telemetry.get("metadata", {}).get("circuit_name")
        meta["telemetry_source"] = f"python_backend/data/circuits/{circuit_id}_Telemetry.json"


def load_calibration(component: str, circuit_id: str) -> Optional[Dict[str, Any]]:
    base = CALIBRATION_PATHS.get(component)
    if not base:
        return None
    path = base / f"{circuit_id}.json"
    if path.exists():
        return load_json(path)
    return None


def merge_circuit_profile(circuit_id: str, args: argparse.Namespace) -> None:
    global_defaults = {k: load_json(v) for k, v in GLOBAL_DEFAULTS.items() if v.exists()}
    setup_bounds = load_json(SETUP_BOUNDS) if SETUP_BOUNDS.exists() else {}

    setup_key, setup_entry = find_setup_entry(setup_bounds, circuit_id)
    telemetry = load_telemetry(circuit_id)
    pirelli_context = extract_pirelli_context(setup_entry)
    cluster_metrics = extract_cluster_metrics(setup_entry)

    out_dir = DERIVED_BASE / circuit_id
    ensure_dir(out_dir)

    tyre_cal = load_calibration("tyres", circuit_id)
    if tyre_cal:
        tyres = tyre_cal
    else:
        tyres = build_tyres(global_defaults.get("tyres", {}), pirelli_context)

    brakes = build_brakes(global_defaults.get("brakes", {}), setup_entry, cluster_metrics)
    brake_cal = load_calibration("brakes", circuit_id)
    if brake_cal:
        brakes["_calibration"] = brake_cal

    pu_cal = load_calibration("pu", circuit_id)
    if pu_cal:
        pu_maps = pu_cal
    else:
        pu_maps = build_pu_maps(global_defaults.get("pu_maps", {}), setup_entry)
    pu_reliability = deepcopy(global_defaults.get("pu_reliability", {}))
    damage = build_damage(global_defaults.get("damage", {}), setup_entry, pirelli_context)
    penalty_profile = build_penalty_profile(telemetry)

    for payload in (tyres, brakes, pu_maps, pu_reliability, damage):
        add_common_meta(payload, circuit_id, setup_key, telemetry)

    outputs = {
        "tyre_params.json": tyres,
        "brake_params.json": brakes,
        "pu_maps.json": pu_maps,
        "pu_reliability.json": pu_reliability,
        "damage_coeffs.json": damage,
        "penalty_profile.json": penalty_profile,
    }

    for filename, content in outputs.items():
        out_path = out_dir / filename
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)

    if args.verbose:
        print(f"Wrote derived profiles for {circuit_id} -> {out_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build derived circuit profiles")
    parser.add_argument("circuit_ids", nargs="+", help="Circuit IDs to process (matching raw directories)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dir(DERIVED_BASE)
    for cid in args.circuit_ids:
        merge_circuit_profile(cid, args)


if __name__ == "__main__":
    main()
