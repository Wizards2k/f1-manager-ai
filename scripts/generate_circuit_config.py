#!/usr/bin/env python3
"""Generate per-circuit physics config JSON from telemetry + mapping data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from math import radians, sin, cos, sqrt, atan2

PIRELLI_DATA_PATH = Path("python_backend/data/pirelli_2025_nomination.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circuit-id", required=True, help="Internal circuit identifier (es. it-1922_monza)")
    parser.add_argument("--telemetry", required=True, help="Path to telemetry JSON (e.g., italy_2024_Q.json)")
    parser.add_argument("--mapping", required=True, help="Path to circuit mapping JSON (sections/legacy params)")
    parser.add_argument(
        "--geojson",
        help="Optional path to circuit GeoJSON (defaults to python_backend/circuits/{circuit_id}.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="python_backend/data/circuits",
        help="Directory where the generated JSON will be stored",
    )
    parser.add_argument(
        "--pit-lane-time",
        type=float,
        default=24.0,
        help="Baseline pit lane delta (seconds) if not provided by data",
    )
    parser.add_argument(
        "--render-speed-scale",
        type=float,
        default=1.0,
        help="Visualization scale for map marker speed",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def load_pirelli_dataset(path: Path = PIRELLI_DATA_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except json.JSONDecodeError:
        return {}


def _normalize_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.lower().strip().replace("-", " ").replace("_", " ")
    return "".join(ch for ch in cleaned if ch.isalnum())


def find_pirelli_entry(
    circuit_id: str,
    circuit_info: Optional[Dict[str, Any]],
    pirelli_dataset: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    calendar: List[Dict[str, Any]] = pirelli_dataset.get("calendar", [])
    candidate_keys = []
    if circuit_id:
        candidate_keys.append(circuit_id)
    if circuit_info:
        candidate_keys.extend(
            [
                circuit_info.get("code"),
                circuit_info.get("location"),
                circuit_info.get("name"),
            ]
        )

    normalized_candidates = {
        _normalize_key(value) for value in candidate_keys if _normalize_key(value)
    }
    if not normalized_candidates:
        return None

    for entry in calendar:
        entry_keys = {
            _normalize_key(entry.get("gp")),
            _normalize_key(entry.get("track")),
        }
        entry_keys = {key for key in entry_keys if key}
        if normalized_candidates & entry_keys:
            return entry
    return None


def resolve_geojson_path(circuit_id: str, override: Optional[str]) -> Optional[Path]:
    if override:
        path = Path(override)
        return path if path.exists() else None
    default_path = Path("python_backend/circuits") / f"{circuit_id}.json"
    if default_path.exists():
        return default_path
    return None


def parse_time_seconds(raw: str | float | int) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    value = raw.strip()
    days = 0
    if "days" in value:
        day_part, time_part = value.split(" days ", maxsplit=1)
        days = int(day_part)
    else:
        time_part = value
    h_str, m_str, s_str = time_part.split(":")
    seconds = float(s_str)
    return days * 86400 + int(h_str) * 3600 + int(m_str) * 60 + seconds


def build_metadata(telemetry: Dict[str, Any], circuit_id: str, pit_lane_time: float) -> Dict[str, Any]:
    return {
        "circuit_id": circuit_id,
        "circuit_name": telemetry.get("CircuitName"),
        "year": telemetry.get("Year"),
        "session_type": telemetry.get("SessionType"),
        "description": telemetry.get("SelectionReason"),
        "pit_lane_time": pit_lane_time,
        "drs_zones": [
            {
                "detection_m": None,
                "start_m": None,
                "end_m": None,
            }
        ]
    }


def build_geometry(mapping: Dict[str, Any], geojson: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    sections_out: List[Dict[str, Any]] = []
    for idx, section in enumerate(mapping.get("sections", []), start=1):
        sections_out.append(
            {
                "id": f"section_{idx:02d}",
                "name": section.get("name"),
                "start_m": section.get("start"),
                "end_m": section.get("end"),
                "kind": section.get("type"),
                "avg_speed": section.get("avg_speed"),
                "corner_number": section.get("corner_number"),
                "bumpiness": section.get("bumpiness"),
                "radius_m": section.get("radius"),
            }
        )

    sector_markers = mapping.get("sector_markers")
    if not sector_markers:
        length = mapping.get("circuit_length") or 0
        sector_markers = [0, round(length / 3, 3), round(2 * length / 3, 3)]

    return {
        "circuit_length": mapping.get("circuit_length"),
        "sections": sections_out,
        "sector_markers": sector_markers,
    }


def build_reference_lap(telemetry: Dict[str, Any]) -> Dict[str, Any]:
    lap_time_sec = parse_time_seconds(telemetry.get("LapTime", 0.0))
    telem_points_out: List[Dict[str, Any]] = []
    for idx, point in enumerate(telemetry.get("TelemetryPoints", [])):
        telem_points_out.append(
            {
                "sequence": idx,
                "distance": point.get("DistanceFromStart"),
                "speed": point.get("Speed"),
                "rpm": point.get("RPM"),
                "gear": point.get("Gear"),
                "throttle": point.get("Throttle"),
                "brake": point.get("Brake"),
                "timestamp": point.get("TimestampSeconds"),
                "drs": point.get("DRS"),
                "x": point.get("X"),
                "y": point.get("Y"),
            }
        )

    mapping = telemetry.get("OfficialSectorMapping", {})
    sector_markers = [
        mapping.get("Sector1EndPointIndex"),
        mapping.get("Sector2EndPointIndex"),
        mapping.get("Sector3EndPointIndex"),
    ]

    return {
        "driver": telemetry.get("Driver"),
        "lap_time": lap_time_sec,
        "fuel_level": telemetry.get("EstimatedFuelLevel"),
        "tire_compound": telemetry.get("TireCompound"),
        "tire_life": telemetry.get("TireLife"),
        "sector_times": [
            telemetry.get("Sector1Time"),
            telemetry.get("Sector2Time"),
            telemetry.get("Sector3Time"),
        ],
        "official_sector_mapping": sector_markers,
        "telemetry_points": telem_points_out,
    }


def legacy_with_default(mapping: Dict[str, Any]) -> Dict[str, Any]:
    return mapping.get("legacy_parameters", {}) or {}


def build_aero_drag(legacy: Dict[str, Any]) -> Dict[str, Any]:
    drag = legacy.get("aerodynamic_drag", 1.0)
    downforce = legacy.get("downforce_importance", 1.0)
    return {
        "cdA_base": drag,
        "cla_front_base": round(downforce * 0.45, 4),
        "cla_rear_base": round(downforce * 0.55, 4),
        "drag_multiplier_straight": 1.0,
        "drag_multiplier_corner": 1.05,
        "drs_drag_delta": -0.12,
    }


def build_grip_handling(legacy: Dict[str, Any]) -> Dict[str, Any]:
    mu = legacy.get("reference_grip", 1.0)
    return {
        "mu_base": mu,
        "k_handling": {"slow": 0.04, "medium": 0.025, "fast": 0.015},
        "section_grip_overrides": {},
        "ride_height_constraints": {"front_min": 25, "rear_min": 35},
    }


def build_tyre_block(
    legacy: Dict[str, Any],
    pirelli_entry: Optional[Dict[str, Any]] = None,
    pirelli_dataset: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "compound_bias": {
            "SOFT": legacy.get("soft_tire_multiplier", 1.0),
            "MEDIUM": legacy.get("medium_tire_multiplier", 1.0),
            "HARD": legacy.get("hard_tire_multiplier", 1.0),
        },
        "wear_multipliers": {"front": 1.0, "rear": 1.0},
        "temperature_targets": {"air_c": [20, 32], "track_c": [25, 45]},
    }

    if pirelli_dataset:
        block["pirelli_metadata"] = {
            "season": pirelli_dataset.get("season"),
            "compounds_info": pirelli_dataset.get("compounds_info"),
        }

    if pirelli_entry:
        block["pirelli_package"] = {
            "round": pirelli_entry.get("round"),
            "gp": pirelli_entry.get("gp"),
            "track": pirelli_entry.get("track"),
            "nomination": pirelli_entry.get("nomination"),
            "lap_time_delta_hint": pirelli_entry.get("lap_time_delta_hint"),
            "wear_rate_base": pirelli_entry.get("wear_rate_base"),
            "notes": pirelli_entry.get("notes"),
        }

    return block


def build_fuel_mass_block(pit_lane_time: float) -> Dict[str, Any]:
    return {
        "fuel_lap_delta_ms": 0.035,
        "max_stint_laps": 15,
        "pit_delta_seconds": pit_lane_time,
    }


def build_weather_block() -> Dict[str, Any]:
    return {
        "air_temp_c": [15, 35],
        "track_temp_c": [20, 50],
        "rain_probability": 0.1,
        "grip_evolution_curve": [0.85, 0.92, 1.0],
        "wind": {"speed_kmh": [0, 25], "direction_deg": 0},
    }


def build_reliability_block() -> Dict[str, Any]:
    return {
        "yellow_flag_prob": 0.08,
        "safety_car_prob": 0.05,
        "mechanical_failure_bias": 0.03,
    }


def build_visual_block(render_speed_scale: float) -> Dict[str, Any]:
    return {
        "render_speed_scale": render_speed_scale,
        "map_offset": {"x": 0.0, "y": 0.0},
        "map_scale": 1.0,
    }


def main() -> None:
    args = parse_args()
    telemetry_path = Path(args.telemetry)
    mapping_path = Path(args.mapping)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    telemetry = read_json(telemetry_path)
    mapping = read_json(mapping_path)
    geojson_path = resolve_geojson_path(args.circuit_id, args.geojson)
    geojson_data = read_json(geojson_path) if geojson_path else None
    legacy = legacy_with_default(mapping)
    pirelli_dataset = load_pirelli_dataset()
    pirelli_entry = find_pirelli_entry(
        args.circuit_id,
        mapping.get("circuit_info"),
        pirelli_dataset,
    )

    config = {
        "metadata": build_metadata(telemetry, args.circuit_id, args.pit_lane_time),
        "geometry": build_geometry(mapping, geojson_data),
        "reference_lap": build_reference_lap(telemetry),
        "aero_drag": build_aero_drag(legacy),
        "grip_handling": build_grip_handling(legacy),
        "tyres": build_tyre_block(legacy, pirelli_entry, pirelli_dataset),
        "fuel_mass": build_fuel_mass_block(args.pit_lane_time),
        "weather": build_weather_block(),
        "reliability": build_reliability_block(),
        "visual": build_visual_block(args.render_speed_scale),
    }

    output_path = output_dir / f"{args.circuit_id}_Telemetry.json"
    output_path.write_text(json.dumps(config, indent=2))
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
