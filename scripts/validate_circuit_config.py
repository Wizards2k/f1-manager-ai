#!/usr/bin/env python3
"""Validate generated circuit config against source telemetry/mapping files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_circuit_config import parse_time_seconds


REQUIRED_TOP_LEVEL = {
    "metadata",
    "geometry",
    "reference_lap",
    "aero_drag",
    "grip_handling",
    "tyres",
    "fuel_mass",
    "weather",
    "reliability",
    "visual",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Generated circuit config JSON")
    parser.add_argument("--telemetry", required=True, help="Telemetry source JSON (_Q file)")
    parser.add_argument("--mapping", required=True, help="Circuit mapping JSON (sections/legacy)")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def check_required_keys(config: Dict[str, Any]) -> list[str]:
    missing = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in config:
            missing.append(key)
    return missing


def compare_value(label: str, generated: Any, expected: Any) -> str | None:
    if generated != expected:
        return f"Mismatch {label}: generated={generated!r} expected={expected!r}"
    return None


def validate_metadata(config: Dict[str, Any], telemetry: Dict[str, Any]) -> List[str]:
    issues = []
    metadata = config.get("metadata", {})
    issues.extend(
        filter(
            None,
            [
                compare_value("metadata.circuit_name", metadata.get("circuit_name"), telemetry.get("CircuitName")),
                compare_value("metadata.year", metadata.get("year"), telemetry.get("Year")),
                compare_value("metadata.session_type", metadata.get("session_type"), telemetry.get("SessionType")),
            ],
        )
    )
    return issues


def validate_geometry(config: Dict[str, Any], mapping: Dict[str, Any]) -> List[str]:
    issues = []
    geometry = config.get("geometry", {})
    issues.extend(
        filter(
            None,
            [compare_value("geometry.circuit_length", geometry.get("circuit_length"), mapping.get("circuit_length"))],
        )
    )
    config_sections = geometry.get("sections", [])
    if not config_sections:
        issues.append("geometry.sections is empty")
    else:
        # Compare count with mapping sections count
        map_sections = mapping.get("sections", [])
        if len(config_sections) != len(map_sections):
            issues.append(
                f"Section count mismatch: generated={len(config_sections)} expected={len(map_sections)}"
            )
    return issues


def validate_reference_lap(config: Dict[str, Any], telemetry: Dict[str, Any]) -> List[str]:
    ref = config.get("reference_lap", {})
    issues = list(
        filter(
            None,
            [
                compare_value("reference_lap.driver", ref.get("driver"), telemetry.get("Driver")),
                compare_value("reference_lap.tire_compound", ref.get("tire_compound"), telemetry.get("TireCompound")),
                compare_value("reference_lap.tire_life", ref.get("tire_life"), telemetry.get("TireLife")),
                compare_value("reference_lap.fuel_level", ref.get("fuel_level"), telemetry.get("EstimatedFuelLevel")),
            ],
        )
    )

    expected_lap = telemetry.get("LapTime")
    generated_lap = ref.get("lap_time")
    expected_seconds = parse_time_seconds(expected_lap)
    if abs((generated_lap or 0) - expected_seconds) > 1e-3:
        issues.append(
            f"reference_lap.lap_time mismatch: generated={generated_lap} expected={expected_seconds}"
        )

    generated_sectors = ref.get("sector_times", [])
    expected_sectors = [
        telemetry.get("Sector1Time"),
        telemetry.get("Sector2Time"),
        telemetry.get("Sector3Time"),
    ]
    if generated_sectors != expected_sectors:
        issues.append(
            f"reference_lap.sector_times mismatch: generated={generated_sectors} expected={expected_sectors}"
        )

    telem_points = ref.get("telemetry_points", [])
    if not telem_points:
        issues.append("reference_lap.telemetry_points empty")
    else:
        # spot check first and last point distance to ensure ordering
        if telem_points[0].get("distance") is None or telem_points[-1].get("distance") is None:
            issues.append("reference_lap.telemetry_points missing distance in first/last point")
    return issues


def main() -> None:
    args = parse_args()
    config = read_json(Path(args.config))
    telemetry = read_json(Path(args.telemetry))
    mapping = read_json(Path(args.mapping))

    issues: List[str] = []

    missing_keys = check_required_keys(config)
    if missing_keys:
        issues.append(f"Missing top-level blocks: {', '.join(sorted(missing_keys))}")

    issues.extend(validate_metadata(config, telemetry))
    issues.extend(validate_geometry(config, mapping))
    issues.extend(validate_reference_lap(config, telemetry))

    if issues:
        print("Validation FAILED:")
        for entry in issues:
            print(f" - {entry}")
    else:
        print("Validation PASSED: config matches telemetry/mapping expectations.")


if __name__ == "__main__":
    main()
