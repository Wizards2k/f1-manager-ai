"""Debug test for wear calculation — check load_kn and wear_delta values."""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Add temporary debug hook to print load_kn and wear values
import lap_simulator.physics_engine.integrator.waypoint_integrator as integrator_module

original_integrate_lap = integrator_module.integrate_lap_hd

def debug_integrate_lap_hd(*args, **kwargs):
    """Wrapper to capture and print wear debug info."""
    # We'll need to intercept at a lower level, so let's just run and instrument
    result = original_integrate_lap(*args, **kwargs)
    return result

# Monkey-patch for visibility
integrator_module.integrate_lap_hd = debug_integrate_lap_hd

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration

circuit = "mc-1929_monaco"
compound = "C4"
aero_setup = {"front_wing": 18, "rear_wing": 11}
aero_calibration = get_aero_calibration(circuit)

print("Testing wear calculation with debug output...")
print(f"Circuit: {circuit}, Compound: {compound}")
print(f"Aero: FW={aero_setup['front_wing']}, RW={aero_setup['rear_wing']}")

result = integrate_lap_hd(
    circuit_id=circuit,
    aero_setup=aero_setup,
    mass_kg=750.0,
    tyre_compound=compound,
    driver_skill=1.0,
    push_level=9,
    aero_calibration=aero_calibration,
    ers_power_fraction=0.5,
    pu_config={"engine_map": "RACE"},
    initial_tire_temps={"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0},
    cumulative_tire_wear={"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0},
)

print(f"\nLap time: {result.get('lap_time_s'):.2f}s")
print(f"Final wear: {result.get('cumulative_tire_wear')}")
print(f"Final temps: {result.get('final_tire_temps')}")

# Check telemetry for wear values
telemetry = result.get('telemetry', [])
if telemetry:
    print(f"\nTelemetry length: {len(telemetry)} waypoints")
    # Check wear in last telemetry entry
    last_entry = telemetry[-1]
    print(f"Last waypoint wear:")
    for wheel in ['FL', 'FR', 'RL', 'RR']:
        field = f'tires_{wheel.lower()}_wear_pct'
        if field in last_entry:
            print(f"  {wheel}: {last_entry[field]:.4f}%")
