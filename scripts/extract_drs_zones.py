#!/usr/bin/env python3
"""Infer DRS activation zones from telemetry points."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DrsZone:
    start_m: float
    end_m: float

    def to_dict(self) -> Dict[str, float]:
        return {"start_m": round(self.start_m, 3), "end_m": round(self.end_m, 3)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", required=True, help="Path to *_Q.json telemetry file")
    parser.add_argument(
        "--drs-threshold",
        type=float,
        default=1.0,
        help="DRS value strictly greater than this is considered 'active' (default: 1)",
    )
    parser.add_argument(
        "--min-length",
        type=float,
        default=50.0,
        help="Minimum length in meters for a DRS interval to be kept (default: 50m)",
    )
    parser.add_argument(
        "--min-throttle",
        type=float,
        default=80.0,
        help="Minimum throttle percentage to consider DRS valid (default: 80)",
    )
    parser.add_argument(
        "--max-brake",
        type=float,
        default=10.0,
        help="Maximum brake percentage during DRS (default: 10)",
    )
    parser.add_argument(
        "--min-speed",
        type=float,
        default=200.0,
        help="Minimum speed (km/h) for DRS validity (default: 200)",
    )
    parser.add_argument(
        "--merge-gap",
        type=float,
        default=30.0,
        help="If gap between consecutive intervals is below this threshold (m), merge them (default: 30m)",
    )
    parser.add_argument(
        "--config",
        help="Optional circuit config JSON to update (metadata.drs_zones will be overwritten)",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print inferred zones as JSON (always printed if --config is not provided)",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _is_point_valid(point: Dict[str, Any], threshold: float, min_throttle: float, max_brake: float, min_speed: float) -> bool:
    drs_value = float(point.get("DRS") or 0.0)
    if drs_value <= threshold:
        return False
    throttle = float(point.get("Throttle") or 0.0)
    if throttle < min_throttle:
        return False
    brake = float(point.get("Brake") or 0.0)
    if brake > max_brake:
        return False
    speed = float(point.get("Speed") or 0.0)
    if speed < min_speed:
        return False
    return True


def infer_drs_zones(
    telemetry: Dict[str, Any],
    threshold: float,
    min_length: float,
    min_throttle: float,
    max_brake: float,
    min_speed: float,
) -> List[DrsZone]:
    points = telemetry.get("TelemetryPoints", [])
    if not points:
        return []

    # Ensure points are sorted by distance
    points = sorted(points, key=lambda p: p.get("DistanceFromStart", 0.0))

    zones: List[DrsZone] = []
    current_start: Optional[float] = None
    last_distance: Optional[float] = None

    for point in points:
        distance = float(point.get("DistanceFromStart") or 0.0)

        if _is_point_valid(point, threshold, min_throttle, max_brake, min_speed):
            if current_start is None:
                current_start = distance
        else:
            if current_start is not None:
                end_m = last_distance if last_distance is not None else distance
                if end_m - current_start >= min_length:
                    zones.append(DrsZone(start_m=current_start, end_m=end_m))
                current_start = None
        last_distance = distance

    # Close final interval if telemetry ends while DRS still active
    if current_start is not None and last_distance is not None:
        if last_distance - current_start >= min_length:
            zones.append(DrsZone(start_m=current_start, end_m=last_distance))

    return zones


def merge_adjacent_zones(zones: List[DrsZone], gap_threshold: float) -> List[DrsZone]:
    if not zones:
        return []
    merged: List[DrsZone] = [zones[0]]
    for zone in zones[1:]:
        last = merged[-1]
        gap = zone.start_m - last.end_m
        if 0 <= gap <= gap_threshold:
            last.end_m = zone.end_m
        else:
            merged.append(zone)
    return merged


def update_config(config_path: Path, zones: List[DrsZone]) -> None:
    config = read_json(config_path)
    metadata = config.setdefault("metadata", {})
    metadata["drs_zones"] = [zone.to_dict() for zone in zones]
    config_path.write_text(json.dumps(config, indent=2))
    print(f"Updated {config_path} with {len(zones)} DRS zones")


def main() -> None:
    args = parse_args()
    telemetry = read_json(Path(args.telemetry))
    zones = infer_drs_zones(
        telemetry,
        args.drs_threshold,
        args.min_length,
        args.min_throttle,
        args.max_brake,
        args.min_speed,
    )

    zones = merge_adjacent_zones(zones, args.merge_gap)

    if args.config:
        update_config(Path(args.config), zones)
    if args.print_json or not args.config:
        print(json.dumps([zone.to_dict() for zone in zones], indent=2))


if __name__ == "__main__":
    main()
