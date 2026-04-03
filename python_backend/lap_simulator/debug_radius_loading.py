"""
DEBUG: Trace where Turn 1 radius 668.5m becomes 27.9m
"""

import json
import sys
sys.path.insert(0, '.')

print("Step 1: Load raw telemetry JSON")
with open('python_backend/data/circuits/2025/it-1922_monza_Telemetry.json') as f:
    data = json.load(f)
    turn1_raw = data['geometry']['sections'][1]
    print(f"  Turn 1 radius from JSON: {turn1_raw.get('radius_m')}")

print("\nStep 2: Load via config_loader")
from lap_simulator.config_loader import load_circuit_config, _parse_section

# Test direct _parse_section
section_parsed = _parse_section(turn1_raw)
print(f"  After _parse_section: {section_parsed.curve_profile.radius_m}")

# Test via load_circuit_config
config = load_circuit_config("it-1922_monza")
section_from_config = config.sections[1]
print(f"  After load_circuit_config: {section_from_config.curve_profile.radius_m}")

print("\nStep 3: Check if there's a post-processing step")
print(f"  Section ID: {section_from_config.section_id}")
print(f"  Section name: {section_from_config.name}")
print(f"  Curvature factor: {section_from_config.curve_profile.curvature_factor}")

# Check if curvature_factor is being used somewhere to recalculate radius
if section_from_config.curve_profile.curvature_factor > 0:
    # curvature_factor = 1.0 / (1.0 + radius / 100.0)
    # Solve for radius: 1 - cf = radius / 100, so radius = 100 * (1 - cf) / cf
    cf = section_from_config.curve_profile.curvature_factor
    calc_radius = 100 * (1 - cf) / cf
    print(f"  Calculated radius from curvature_factor: {calc_radius}")

print("\nConclusion:")
print(f"  Expected radius: 668.5m")
print(f"  Actual radius: {section_from_config.curve_profile.radius_m}m")
print(f"  ERROR: Radius is wrong!")
