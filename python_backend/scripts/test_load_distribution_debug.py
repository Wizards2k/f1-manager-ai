"""Debug load distribution for oversteer setup"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration

def test_load_distribution():
    """Test oversteer vs balanced setup load distribution"""
    circuit = "mc-1929_monaco"
    compound = "C4"
    aero_calibration = get_aero_calibration(circuit)

    setups = {
        "balanced": {"front_wing": 18, "rear_wing": 11},
        "oversteer": {"front_wing": 12, "rear_wing": 11},
        "understeer": {"front_wing": 24, "rear_wing": 11},
    }

    print("=" * 90)
    print("LOAD DISTRIBUTION DEBUG - Monaco Circuit")
    print("=" * 90)

    for setup_name, setup in setups.items():
        print(f"\n{setup_name.upper()} Setup: FW={setup['front_wing']}, RW={setup['rear_wing']}")
        print("-" * 90)

        result = integrate_lap_hd(
            circuit_id=circuit,
            aero_setup=setup,
            mass_kg=750.0,
            tyre_compound=compound,
            driver_skill=1.0,
            push_level=9,
            aero_calibration=aero_calibration,
            ers_power_fraction=0.5,
            pu_config={"engine_map": "RACE"},
        )

        # Check telemetry for load info
        telemetry = result.get('telemetry', [])
        if telemetry and len(telemetry) > 100:
            # Sample waypoints at 25%, 50%, 75% of lap
            indices = [len(telemetry) // 4, len(telemetry) // 2, 3 * len(telemetry) // 4]

            for idx in indices:
                wp = telemetry[idx]
                print(f"\n  Waypoint {idx} (distance: {wp.get('distance_m', 0):.0f}m):")
                print(f"    Velocity: {wp.get('velocity_kph', 0):.1f} kph")
                print(f"    Radius: {wp.get('radius_m', 0):.0f}m")

                # Extract tire wear data
                fl_wear = wp.get('tires_fl_wear_pct', 0)
                fr_wear = wp.get('tires_fr_wear_pct', 0)
                rl_wear = wp.get('tires_rl_wear_pct', 0)
                rr_wear = wp.get('tires_rr_wear_pct', 0)

                print(f"    Wear: FL={fl_wear:.2f}% FR={fr_wear:.2f}% RL={rl_wear:.2f}% RR={rr_wear:.2f}%")

        final_wear = result.get('cumulative_tire_wear', {})
        front_avg = (final_wear.get('FL', 0) + final_wear.get('FR', 0)) / 2
        rear_avg = (final_wear.get('RL', 0) + final_wear.get('RR', 0)) / 2

        print(f"\n  Final Lap Wear:")
        print(f"    Front avg: {front_avg:.2f}%")
        print(f"    Rear avg:  {rear_avg:.2f}%")
        print(f"    Front/Rear ratio: {front_avg/max(0.01, rear_avg):.2f}x")

if __name__ == "__main__":
    test_load_distribution()
