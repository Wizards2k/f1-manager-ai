"""Generate circuit setup mapping entries from telemetry cluster + Pirelli data."""

import argparse
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

STOPWORDS = {
    "circuit",
    "circuito",
    "international",
    "grand",
    "prix",
    "course",
    "street",
    "track",
    "autodromo",
    "autodrome",
    "city",
    "gp",
    "de",
    "di",
    "the",
    "of",
    "park",
    "strip",
    "speedway",
}


def load_json(path: Path) -> Any:
    with path.open() as fp:
        return json.load(fp)


def slugify(name: str) -> str:
    if not name:
        return "unknown"
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", ascii_name) if t and t not in STOPWORDS]
    slug = "_".join(tokens) or ascii_name.replace(" ", "_")
    return slug


def clamp(value: float, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def shift_deg_range(rng: Dict[str, float], delta: float) -> None:
    for key in ("min_deg", "max_deg"):
        if key in rng:
            rng[key] = round(clamp(rng[key] + delta, 0.0, 40.0), 2)


def scale_deg_range(rng: Dict[str, float], factor: float) -> None:
    center = (rng["min_deg"] + rng["max_deg"]) / 2
    span = (rng["max_deg"] - rng["min_deg"]) * factor / 2
    rng["min_deg"] = round(clamp(center - span, 0.0, 40.0), 2)
    rng["max_deg"] = round(clamp(center + span, 0.0, 40.0), 2)


def shift_mm_range(rng: Dict[str, float], delta_min: float, delta_max: float, min_bounds=(20.0, 30.0)) -> None:
    min_floor, max_floor = min_bounds
    if "min_mm" in rng:
        rng["min_mm"] = round(clamp(rng["min_mm"] + delta_min, min_floor, 120.0), 1)
    if "max_mm" in rng:
        rng["max_mm"] = round(clamp(rng["max_mm"] + delta_max, max_floor, 150.0), 1)


def shift_ratio(rng: Dict[str, float], delta: float, bounds=(0.0, 1.0)) -> None:
    lo, hi = bounds
    rng["min_open"] = round(clamp(rng["min_open"] + delta, lo, hi), 3)
    rng["max_open"] = round(clamp(rng["max_open"] + delta, lo, hi), 3)
    if rng["min_open"] >= rng["max_open"]:
        rng["max_open"] = round(min(hi, rng["min_open"] + 0.05), 3)


def shift_brake_balance(rng: Dict[str, float], delta: float) -> None:
    rng["min_pct"] = round(clamp(rng["min_pct"] + delta, 50.0, 60.0), 2)
    rng["max_pct"] = round(clamp(rng["max_pct"] + delta, 50.0, 60.0), 2)
    rng["step_pct"] = rng.get("step_pct", 0.1)


def adjust_suspension(entry: Dict[str, Any], rigidity_delta: float) -> None:
    for key in ("suspension_front", "suspension_rear", "antiroll_front", "antiroll_rear"):
        if key in entry:
            rig = entry[key].get("rigidity")
            if rig:
                for bound in ("min", "max"):
                    rig[bound] = round(clamp(rig[bound] + rigidity_delta, 0.2, 1.0), 3)


def build_entry(record: Dict[str, Any], base_template: Dict[str, Any]) -> Dict[str, Any]:
    entry = deepcopy(base_template)
    load_class = record.get("load_class", "balanced")
    metrics = record.get("metrics", {})
    profile = record.get("pirelli_profile") or {}
    track_features = profile.get("track_features") or {}
    wear_rate = profile.get("wear_rate_base") or 0.2
    bumps = track_features.get("bumps", 3)
    kerbs = track_features.get("kerbs", 3)

    load_shift = {
        "low_drag": -4.0,
        "street_hybrid": -1.5,
        "balanced": -0.5,
        "medium_low_df": 0.5,
        "medium_high_df": 1.5,
        "high_df": 3.0,
    }.get(load_class, 0.0)

    shift_deg_range(entry["front_wing"], load_shift)
    shift_deg_range(entry["rear_wing"], load_shift * 0.9)
    shift_deg_range(entry["beam_wing"], load_shift * 0.5)

    straight_pct = metrics.get("straight_pct", 0.5)
    if straight_pct >= 0.65:
        scale_deg_range(entry["rear_wing"], 0.85)
    elif straight_pct <= 0.4:
        scale_deg_range(entry["rear_wing"], 1.05)

    ride_delta = (bumps - 3) * 2.0
    shift_mm_range(entry["ride_height_front"], ride_delta, ride_delta)
    shift_mm_range(entry["ride_height_rear"], ride_delta + 1.5, ride_delta + 1.5)

    rigidity_delta = -0.04 * (bumps - 3)
    adjust_suspension(entry, rigidity_delta)
    if kerbs >= 4:
        adjust_suspension(entry, -0.02)

    heavy_brakes = metrics.get("heavy_brake_events", 0)
    brake_delta = clamp(0.15 * (heavy_brakes - 2), -0.5, 0.8)
    shift_brake_balance(entry["brake_balance"], brake_delta)

    duct_delta = clamp((wear_rate - 0.18) * 1.2, -0.1, 0.2)
    shift_ratio(entry["brake_duct"], duct_delta)

    tyres = profile.get("pirelli_prescriptions")
    if tyres:
        entry["tyre_constraints"] = {
            "min_pressure_front_psi": tyres.get("min_pressure_front_psi"),
            "min_pressure_rear_psi": tyres.get("min_pressure_rear_psi"),
            "max_camber_front_deg": tyres.get("max_camber_front"),
            "max_camber_rear_deg": tyres.get("max_camber_rear"),
        }

    entry["tyre_nomination"] = profile.get("tyre_nomination")

    energy_profile = profile.get("energy_management") or {}
    if not energy_profile:
        if straight_pct >= 0.65:
            energy_profile = {
                "fuel_burn_intensity": "high",
                "ers_deployment_style": "end_of_straight",
                "brake_energy_recovery_kj": round(900 + 400 * straight_pct, 0),
            }
        else:
            energy_profile = {
                "fuel_burn_intensity": "medium",
                "ers_deployment_style": "balanced",
                "brake_energy_recovery_kj": round(600 + 150 * heavy_brakes, 0),
            }
    entry["energy_profile"] = energy_profile

    weather_impact = profile.get("weather_impact") or {}
    entry["cooling_guidance"] = {
        "brake_duct_requirement": weather_impact.get("brake_duct_requirement")
        if weather_impact
        else ("high" if wear_rate >= 0.25 else "medium"),
        "avg_track_temp_delta_c": weather_impact.get("avg_track_temp_change_race") if weather_impact else None,
    }

    notes = [n for n in (profile.get("notes"), record.get("cluster_note")) if n]
    entry.setdefault("constraints", {})
    entry["constraints"]["notes"] = notes

    entry["metadata"] = {
        "circuit_id": record.get("circuit_id"),
        "circuit_name": record.get("circuit_name"),
    }
    entry["cluster_context"] = {
        "load_class": load_class,
        "surface_class": record.get("surface_class"),
        "climate_class": record.get("climate_class"),
        "metrics": metrics,
    }
    entry["pirelli_context"] = {
        "track_category": profile.get("track_category"),
        "corner_distribution": profile.get("corner_distribution"),
        "track_features": profile.get("track_features"),
        "wear_rate_base": profile.get("wear_rate_base"),
    }
    entry["data_sources"] = [
        "tmp/setup_cluster_report_latest.json",
        "config/pirelli_track_profile_2025.json",
    ]
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Update setup_mapping_v2.json using cluster + Pirelli data")
    parser.add_argument("--cluster", default="tmp/setup_cluster_report_latest.json")
    parser.add_argument("--mapping", default="config/setup_mapping_v2.json")
    args = parser.parse_args()

    cluster_data = load_json(Path(args.cluster))
    mapping_path = Path(args.mapping)
    mapping_data = load_json(mapping_path)

    base_template = mapping_data["default"]
    new_mapping: Dict[str, Any] = {
        "_meta": mapping_data.get("_meta", {}),
        "default": base_template,
    }

    for record in cluster_data:
        slug = slugify(record.get("circuit_name"))
        entry = build_entry(record, base_template)
        new_mapping[slug] = entry

    with mapping_path.open("w") as fp:
        json.dump(new_mapping, fp, indent=2, ensure_ascii=False)

    print(f"Updated {mapping_path} with {len(cluster_data)} circuit entries")


if __name__ == "__main__":
    main()
