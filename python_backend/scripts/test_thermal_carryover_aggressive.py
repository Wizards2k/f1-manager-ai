"""
15-Lap Thermal Carryover Test with Aggressive Underdriving — V6.3
Uses low push_level (3-4) to force slip and wear accumulation.
Tests understeer vs oversteer thermal asymmetries.
"""

import sys
from pathlib import Path
from typing import Dict

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.core.team_driver_data import get_team_data, get_driver_data
from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration


def simulate_15lap_stint(circuit: str, compound: str, setup_type: str, setup_config: Dict) -> Dict:
    """
    Simulate 15-lap race stint with aggressive underdriving to force slip/wear.
    Push_level 3-4 (conservative) ensures slip margin and measurable wear.
    """
    team = get_team_data("mclaren")
    driver = get_driver_data("Lando Norris")

    setup = PhysicsV4Setup(
        team_data=team,
        driver_data=driver,
        circuit=circuit,
        session="race"
    )

    setup.set_aero(front_wing=setup_config["front_wing"], rear_wing=setup_config["rear_wing"])
    setup.set_tyres(compound=compound)
    setup.set_ers_mode("balanced")

    aero_setup = {
        "front_wing": setup_config["front_wing"],
        "rear_wing": setup_config["rear_wing"],
    }
    aero_calibration = get_aero_calibration(circuit)

    lap_results = []
    current_tire_temps = {"FL": 20.0, "FR": 20.0, "RL": 20.0, "RR": 20.0}
    cumulative_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}
    total_time = 0.0

    for lap_num in range(1, 16):
        fuel_remaining = max(5.0, 110.0 - (lap_num - 1) * 14.5)

        # Aggressive underdriving: push_level 3-4 creates slip margin (not maximum grip)
        # Lap 1: outlap conservative (push_level 2)
        # Laps 2-15: controlled race pace (push_level 4) with deliberate margin
        push_level = 2 if lap_num == 1 else 4

        try:
            result = integrate_lap_hd(
                circuit_id=circuit,
                aero_setup=aero_setup,
                mass_kg=750.0,
                tyre_compound=compound,
                driver_skill=0.85,  # Reduced from 1.0 to create more slip
                push_level=push_level,
                aero_calibration=aero_calibration,
                ers_power_fraction=0.5,
                pu_config={"engine_map": "RACE"},
                initial_tire_temps=current_tire_temps,
                cumulative_tire_wear=cumulative_wear,
            )

            lap_time = result.get("lap_time_s", 0)
            v_max = result.get("v_max_kph", 0)
            total_time += lap_time

            current_tire_temps = result.get("final_tire_temps")
            cumulative_wear = result.get("cumulative_tire_wear")

            if current_tire_temps is None:
                return {
                    "error": f"Lap {lap_num}: final_tire_temps is None",
                    "lap_num": lap_num,
                }

            lap_results.append({
                "lap_num": lap_num,
                "lap_time": lap_time,
                "v_max": v_max,
                "fuel": fuel_remaining,
                "tire_temps": current_tire_temps,
                "tire_wear": cumulative_wear,
            })

        except Exception as e:
            return {
                "error": f"Lap {lap_num} failed: {type(e).__name__}: {str(e)[:100]}",
                "lap_num": lap_num,
            }

    # Analyze asymmetry
    if not lap_results:
        return {"error": "No lap results"}

    final_wear = lap_results[-1]["tire_wear"]
    if not final_wear:
        return {"error": "No final wear data"}

    front_wear_avg = (final_wear.get("FL", 0) + final_wear.get("FR", 0)) / 2
    rear_wear_avg = (final_wear.get("RL", 0) + final_wear.get("RR", 0)) / 2

    asymmetry_valid = False
    asymmetry_msg = ""

    if setup_type == "understeer":
        if front_wear_avg > rear_wear_avg + 0.2:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Front wear {front_wear_avg:.3f}% > Rear {rear_wear_avg:.3f}%"
        else:
            asymmetry_msg = f"✗ Front wear {front_wear_avg:.3f}% ≤ Rear {rear_wear_avg:.3f}%"

    elif setup_type == "oversteer":
        if rear_wear_avg > front_wear_avg + 0.2:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Rear wear {rear_wear_avg:.3f}% > Front {front_wear_avg:.3f}%"
        else:
            asymmetry_msg = f"✗ Rear wear {rear_wear_avg:.3f}% ≤ Front {front_wear_avg:.3f}%"

    elif setup_type == "optimal":
        wear_range = max(final_wear.values()) - min(final_wear.values())
        if wear_range <= 0.5:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Balanced wear: range {wear_range:.3f}%"
        else:
            asymmetry_msg = f"✗ Imbalanced wear: range {wear_range:.3f}%"

    return {
        "lap_results": lap_results,
        "total_time": total_time,
        "final_wear": final_wear,
        "front_wear_avg": front_wear_avg,
        "rear_wear_avg": rear_wear_avg,
        "asymmetry_msg": asymmetry_msg,
        "asymmetry_valid": asymmetry_valid,
    }


def print_stint_summary(circuit: str, compound: str, setup_type: str, data: Dict):
    """Print 15-lap stint summary."""
    if "error" in data:
        print(f"    ❌ ERROR: {data['error']}")
        return

    lap_results = data.get("lap_results", [])
    final_wear = data.get("final_wear", {})

    print(f"\n    Lap Progression:")
    for idx in [0, 7, 14]:
        if idx < len(lap_results):
            lap = lap_results[idx]
            temps = lap.get("tire_temps", {})
            wear = lap.get("tire_wear", {})

            fl_temp = temps.get("FL", 0) if temps else 0
            fr_temp = temps.get("FR", 0) if temps else 0
            rl_temp = temps.get("RL", 0) if temps else 0
            rr_temp = temps.get("RR", 0) if temps else 0

            fl_wear = wear.get("FL", 0) if wear else 0
            fr_wear = wear.get("FR", 0) if wear else 0
            rl_wear = wear.get("RL", 0) if wear else 0
            rr_wear = wear.get("RR", 0) if wear else 0

            print(
                f"      Lap {lap['lap_num']:2d}: Time {lap['lap_time']:6.2f}s | "
                f"Temps FL={fl_temp:5.1f}°C FR={fr_temp:5.1f}°C RL={rl_temp:5.1f}°C RR={rr_temp:5.1f}°C | "
                f"Wear FL={fl_wear:6.3f}% FR={fr_wear:6.3f}% RL={rl_wear:6.3f}% RR={rr_wear:6.3f}%"
            )

    print(f"\n    Final Wear (Lap 15):")
    print(
        f"      FL: {final_wear.get('FL', 0):7.3f}%  FR: {final_wear.get('FR', 0):7.3f}%  "
        f"RL: {final_wear.get('RL', 0):7.3f}%  RR: {final_wear.get('RR', 0):7.3f}%"
    )

    print(f"\n    Asymmetry: {data['asymmetry_msg']}")
    print(f"    Total Time: {data['total_time']:.2f}s")


if __name__ == "__main__":
    print("=" * 100)
    print("15-LAP THERMAL CARRYOVER TEST — V6.3 (Monaco, Aggressive Underdriving)")
    print("Push_level 2-4 to force slip/wear. Driver_skill 0.85 for natural driving errors.")
    print("=" * 100)

    circuits = ["mc-1929_monaco"]
    compounds = ["C4"]
    setups = {
        "optimal": {"front_wing": 18, "rear_wing": 11, "name": "Optimal (18/11)"},
        "understeer": {"front_wing": 24, "rear_wing": 11, "name": "Understeer (24/11)"},
        "oversteer": {"front_wing": 12, "rear_wing": 11, "name": "Oversteer (12/11)"},
    }

    passed = 0
    failed = 0

    for circuit in circuits:
        circuit_name = circuit.split("_")[-1].title()
        print(f"\n{'='*100}")
        print(f"🏁 {circuit_name} — 15-Lap Stint (Aggressive Underdriving for Slip/Wear)")
        print(f"{'='*100}")

        for compound in compounds:
            print(f"\n  🛞 {compound} Compound")
            print(f"  {'-'*96}")

            for setup_type, setup_config in setups.items():
                print(f"\n    Setup: {setup_config['name']}")

                data = simulate_15lap_stint(circuit, compound, setup_type, setup_config)

                if "error" not in data and data.get("asymmetry_valid"):
                    print(f"    ✅ PASS")
                    passed += 1
                else:
                    print(f"    ❌ FAIL")
                    failed += 1

                print_stint_summary(circuit, compound, setup_type, data)

    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}/{passed + failed}")

    if failed == 0:
        print("\n✅ ALL TESTS PASSED — 15-Lap Thermal Carryover with Slip/Wear Verified\n")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} tests failed\n")
        sys.exit(1)
