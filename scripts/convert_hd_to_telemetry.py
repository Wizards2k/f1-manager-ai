#!/usr/bin/env python3
"""
Convert HD telemetry to Telemetry.json format for Silverstone.

Usage:
    python3 scripts/convert_hd_to_telemetry.py gb-1948_silverstone
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

def load_hd(circuit_id: str) -> Dict[str, Any]:
    """Load HD telemetry data."""
    hd_file = Path(f"python_backend/data/circuits/2025/{circuit_id}_HD.json")
    if not hd_file.exists():
        raise FileNotFoundError(f"HD file not found: {hd_file}")
    return json.loads(hd_file.read_text())

def build_telemetry_from_hd(hd_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert HD data to Telemetry.json format."""
    waypoints = hd_data.get('waypoints', [])
    macro_sectors = hd_data.get('macro_sectors', [])
    
    # Build telemetry points from waypoints
    telemetry_points = []
    for i, wp in enumerate(waypoints):
        telemetry_points.append({
            "distance": wp.get("dist_m", 0.0),
            "speed": wp.get("v_ref_kph", 0.0),
            "timestamp": i * 0.1,  # Approximate timestamp
            "throttle": wp.get("throttle_pct", 0),
            "brake": wp.get("brake_pct", 0),
            "gear": 8,  # Placeholder
            "drs": 14 if wp.get("drs_active", False) else 10,
            "x": 0.0,  # Placeholder
            "y": 0.0,  # Placeholder
        })
    
    # Build sections from macro_sectors
    sections = []
    for sec in macro_sectors:
        sections.append({
            "id": sec.get("id"),
            "name": sec.get("name", sec.get("id")),
            "kind": sec.get("kind", "Straight"),
            "start_m": sec.get("start_m", 0.0),
            "end_m": sec.get("end_m", 0.0),
            "length_m": sec.get("length_m", 0.0),
            "corner_number": 0,
            "v_entry_kph": sec.get("v_entry_kph", 0.0),
            "v_exit_kph": sec.get("v_exit_kph", 0.0),
            "v_min_kph": sec.get("v_min_kph", 0.0),
            "v_max_kph": sec.get("v_max_kph", 0.0),
            "avg_speed": sec.get("avg_speed", 0.0),
            "dt_ref_s": sec.get("dt_ref_s", 0.0),
            "braking_energy_mj": sec.get("braking_energy_mj", 0.0),
            "drs_active": sec.get("drs_active", False),
            "radius_m": sec.get("radius_m"),
            "heat_factor": 1.0,
            "cool_factor": 1.0,
            "bumpiness_factor": 0.0,
            "kerb_severity": 0.0,
            "telemetry_point_start_idx": 0,
            "telemetry_point_end_idx": 0,
        })
    
    # Calculate total dt_ref
    total_dt = sum(sec.get("dt_ref_s", 0.0) for sec in sections)
    
    telemetry_data = {
        "metadata": {
            "circuit_id": hd_data.get("circuit_id", "unknown"),
            "circuit_name": "British Grand Prix",
            "year": 2025,
            "session_type": "Qualifying",
            "description": "Converted from HD telemetry",
            "pit_lane_time": None,
            "drs_zones": []
        },
        "geometry": {
            "circuit_length": hd_data.get("total_length_m", 0.0),
            "sections": sections,
            "sections_version": "v2"
        },
        "reference_lap": {
            "driver": hd_data.get("reference_lap", {}).get("driver", "NOR"),
            "lap_number": hd_data.get("reference_lap", {}).get("lap_number", 1),
            "team": "McLaren",
            "compound": "SOFT",
            "lap_time": hd_data.get("reference_lap", {}).get("lap_time_s", 0.0),
            "telemetry_points": telemetry_points
        },
        "tyres": {
            "compound_bias": {
                "SOFT": 1.0,
                "MEDIUM": 0.96,
                "HARD": 0.94
            },
            "wear_multipliers": {
                "front": 1.0,
                "rear": 1.0
            },
            "temperature_targets": {},
            "pirelli_metadata": {},
            "pirelli_package": {}
        },
        "fuel_mass": {
            "fuel_lap_delta_ms": 0.035,
            "max_stint_laps": 15,
            "pit_delta_seconds": 24.0
        },
        "weather": {
            "air_temp_c": [25, 35],
            "track_temp_c": [35, 50],
            "rain_probability": 0.1,
            "grip_evolution_curve": [1.0],
            "wind": {}
        },
        "reliability": {
            "yellow_flag_prob": 0.08,
            "safety_car_prob": 0.05,
            "mechanical_failure_bias": 0.03
        },
        "visual": {
            "render_speed_scale": 1.0,
            "map_offset": {"x": 0.0, "y": 0.0},
            "map_scale": 1.0
        },
        "tyre_allocation": {
            "weekend_type": "standard",
            "dry_compounds": {
                "soft": "C5",
                "medium": "C4",
                "hard": "C3"
            },
            "dry_allocation": {
                "soft": 2,
                "medium": 3,
                "hard": 2
            },
            "wet_allocation": {
                "intermediate": 1,
                "wet": 2
            },
            "special_rules": {},
            "circuit_characteristics": {}
        }
    }
    
    return telemetry_data

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/convert_hd_to_telemetry.py <circuit_id>")
        sys.exit(1)
    
    circuit_id = sys.argv[1]
    
    try:
        print(f"Loading HD data for {circuit_id}...")
        hd_data = load_hd(circuit_id)
        
        print("Converting to Telemetry format...")
        telemetry_data = build_telemetry_from_hd(hd_data)
        
        output_file = Path(f"python_backend/data/circuits/2025/{circuit_id}_Telemetry.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Saving to {output_file}...")
        output_file.write_text(json.dumps(telemetry_data, indent=2, ensure_ascii=False))
        
        print(f"✅ Conversion complete!")
        print(f"   Circuit: {telemetry_data['metadata']['circuit_name']}")
        print(f"   Length: {telemetry_data['geometry']['circuit_length']:.1f}m")
        print(f"   Lap Time: {telemetry_data['reference_lap']['lap_time']:.3f}s")
        print(f"   Sections: {len(telemetry_data['geometry']['sections'])}")
        print(f"   Telemetry Points: {len(telemetry_data['reference_lap']['telemetry_points'])}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
