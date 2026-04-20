"""Debug test for thermal carryover — single lap with detailed output."""

import sys
from pathlib import Path
from typing import Dict

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration

# Single lap test on Monaco, passing initial_tire_temps explicitly
circuit = "mc-1929_monaco"
compound = "C4"

# Setup
aero_setup = {"front_wing": 18, "rear_wing": 11}
aero_calibration = get_aero_calibration(circuit)

# Lap 1: Cold start (20°C)
initial_tire_temps = {"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0}
cumulative_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}

print(f"Input initial_tire_temps: {initial_tire_temps}")
print(f"Input cumulative_wear: {cumulative_wear}")

result = integrate_lap_hd(
    circuit_id=circuit,
    aero_setup=aero_setup,
    mass_kg=750.0,
    tyre_compound=compound,
    driver_skill=1.0,
    push_level=5,  # Outlap, moderate
    aero_calibration=aero_calibration,
    ers_power_fraction=0.5,
    pu_config={"engine_map": "RACE"},
    initial_tire_temps=initial_tire_temps,
    cumulative_tire_wear=cumulative_wear,
)

final_tire_temps = result.get("final_tire_temps")
final_wear = result.get("cumulative_tire_wear")
lap_time = result.get("lap_time_s")

print(f"\nLap time: {lap_time:.2f}s")
print(f"Output final_tire_temps: {final_tire_temps}")
print(f"Output cumulative_wear: {final_wear}")

if final_tire_temps:
    print(f"\nThermal delta (final - initial):")
    for wheel in ["FL", "FR", "RL", "RR"]:
        delta = final_tire_temps[wheel] - initial_tire_temps[wheel]
        print(f"  {wheel}: {delta:+.1f}°C (from {initial_tire_temps[wheel]:.1f}°C to {final_tire_temps[wheel]:.1f}°C)")

if final_wear:
    print(f"\nWear accumulation:")
    for wheel in ["FL", "FR", "RL", "RR"]:
        delta = final_wear[wheel] - cumulative_wear[wheel]
        print(f"  {wheel}: {delta:+.2f}% (from {cumulative_wear[wheel]:.2f}% to {final_wear[wheel]:.2f}%)")

# Now run Lap 2 with carryover
print(f"\n{'='*70}")
print("LAP 2: With carryover from Lap 1")
print(f"{'='*70}")

print(f"Input initial_tire_temps: {final_tire_temps}")
print(f"Input cumulative_wear: {final_wear}")

result2 = integrate_lap_hd(
    circuit_id=circuit,
    aero_setup=aero_setup,
    mass_kg=735.0,  # 110 - 14.5 fuel consumed
    tyre_compound=compound,
    driver_skill=1.0,
    push_level=9,  # Race pace
    aero_calibration=aero_calibration,
    ers_power_fraction=0.5,
    pu_config={"engine_map": "RACE"},
    initial_tire_temps=final_tire_temps,  # Carryover
    cumulative_tire_wear=final_wear,      # Carryover
)

final_tire_temps_2 = result2.get("final_tire_temps")
final_wear_2 = result2.get("cumulative_tire_wear")
lap_time_2 = result2.get("lap_time_s")

print(f"\nLap time: {lap_time_2:.2f}s")
print(f"Output final_tire_temps: {final_tire_temps_2}")
print(f"Output cumulative_wear: {final_wear_2}")

if final_tire_temps_2:
    print(f"\nThermal delta (final - initial):")
    for wheel in ["FL", "FR", "RL", "RR"]:
        delta = final_tire_temps_2[wheel] - final_tire_temps[wheel]
        print(f"  {wheel}: {delta:+.1f}°C (from {final_tire_temps[wheel]:.1f}°C to {final_tire_temps_2[wheel]:.1f}°C)")
