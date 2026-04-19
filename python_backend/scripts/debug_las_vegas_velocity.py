#!/usr/bin/env python3
"""Debug Las Vegas straight speed — confronta sim vs telemetria reale."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.integrator.waypoint_integrator import load_hd_waypoints
from scripts.calibrate_v57 import ALL_CIRCUITS, SUSP_SETUPS, DRIVER

circuit_id = "us-2023_las_vegas"
cfg = ALL_CIRCUITS["las_vegas"]

# Setup
setup = PhysicsV4Setup(driver_data=DRIVER, circuit=circuit_id, session="qualifying")
setup.set_aero(front_wing=15, rear_wing=9, bwing=10.0)
setup.set_suspension(**SUSP_SETUPS[cfg["susp_source"]])
setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
setup.set_tyres(compound=cfg["compound"])
setup.set_ers_mode("quali_deploy")

# Run sim with telemetry export
result = setup.simulate_lap(verbose=True)

print("\n" + "="*80)
print("LAS VEGAS VELOCITY ANALYSIS")
print("="*80)

# Load waypoints per debugging
waypoints = load_hd_waypoints(circuit_id)

# Find longest straight (distance between 2 corners with radius > 500m)
print(f"\nTotal lap time: {result['lap_time_s']:.3f}s (ref: {cfg['ref_time']:.3f}s, "
      f"error: {100*(result['lap_time_s']-cfg['ref_time'])/cfg['ref_time']:+.2f}%)")

# Show velocity extremes
print(f"\nVelocity stats:")
print(f"  Max: {result.get('max_speed', 'N/A')} m/s")
print(f"  Min: {result.get('min_speed', 'N/A')} m/s")

# Check drag and power
print(f"\nAero diagnostics:")
print(f"  FW: 15°, RW: 9° (low-DF setup for speed circuit)")

# Find straights with v_ref > 250 kph (~70 m/s)
print(f"\nLong straights (v_ref > 70 m/s):")
for i, wp in enumerate(waypoints):
    v_ref = wp.get('v_ref_kph', 0) / 3.6
    radius = wp.get('radius_m', 999)
    if v_ref > 70 and radius > 500:
        print(f"  WP {i}: v_ref={wp.get('v_ref_kph', 0):.1f} kph, radius={radius:.0f}m")
