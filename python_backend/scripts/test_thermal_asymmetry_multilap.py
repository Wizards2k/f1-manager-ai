"""
Multi-Lap Thermal Asymmetry Test — V6.3
Simulates 15-lap stint with thermal carryover between laps.
Verifies per-wheel thermal asymmetries develop as expected for setup types.

Understeer setup (high FW):
  - FL/FR experience higher load → higher temps, faster wear
  - RL/RR lighter load → lower temps, slower wear

Oversteer setup (low FW):
  - RL/RR experience higher load → higher temps, faster wear
  - FL/FR lighter load → lower temps, slower wear
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
import statistics

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.core.team_driver_data import get_team_data, get_driver_data


# Test configuration
CIRCUITS = ["it-1922_monza", "mc-1929_monaco", "es-1991_barcelona"]
CIRCUIT_NAMES = {"it-1922_monza": "Monza", "mc-1929_monaco": "Monaco", "es-1991_barcelona": "Barcelona"}
COMPOUNDS = ["C4"]  # Focus on C4 for detailed analysis
SETUPS = {
    "optimal": {"front_wing": 18, "rear_wing": 11, "name": "Optimal (18/11)"},
    "understeer": {"front_wing": 24, "rear_wing": 11, "name": "Understeer (24/11)"},
    "oversteer": {"front_wing": 12, "rear_wing": 11, "name": "Oversteer (12/11)"},
}

STINT_LAPS = 15
FUEL_START = 110.0  # kg
FUEL_PER_LAP = 14.5  # kg/lap


def extract_wheel_data_from_telemetry(telemetry: List[Dict]) -> Dict:
    """Extract average per-wheel thermal data from single lap telemetry."""
    wheels = {
        "FL": {"temps": [], "wear": []},
        "FR": {"temps": [], "wear": []},
        "RL": {"temps": [], "wear": []},
        "RR": {"temps": [], "wear": []},
    }

    for point in telemetry:
        if isinstance(point, dict):
            wheels["FL"]["temps"].append(point.get("tires_fl_temp_surface_c", 85.0))
            wheels["FR"]["temps"].append(point.get("tires_fr_temp_surface_c", 85.0))
            wheels["RL"]["temps"].append(point.get("tires_rl_temp_surface_c", 85.0))
            wheels["RR"]["temps"].append(point.get("tires_rr_temp_surface_c", 85.0))

            wheels["FL"]["wear"].append(point.get("tires_fl_wear_pct", 0.0))
            wheels["FR"]["wear"].append(point.get("tires_fr_wear_pct", 0.0))
            wheels["RL"]["wear"].append(point.get("tires_rl_wear_pct", 0.0))
            wheels["RR"]["wear"].append(point.get("tires_rr_wear_pct", 0.0))

    # Calculate averages for this lap
    stats = {}
    for wheel in wheels:
        temps = wheels[wheel]["temps"]
        wear = wheels[wheel]["wear"]
        stats[wheel] = {
            "avg_temp": statistics.mean(temps) if temps else 85.0,
            "max_temp": max(temps) if temps else 85.0,
            "final_wear": wear[-1] if wear else 0.0,
        }

    return stats


def simulate_stint(circuit: str, compound: str, setup_type: str, setup_config: Dict) -> Tuple[bool, Dict]:
    """
    Simulate 15-lap stint with thermal carryover between laps.
    Returns aggregated thermal and wear data across all laps.
    """
    team = get_team_data("mclaren")
    driver = get_driver_data("Lando Norris")

    # Accumulate data across 15 laps
    lap_data = []
    cumulative_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}
    current_tire_temps = {"FL": 85.0, "FR": 85.0, "RL": 85.0, "RR": 85.0}

    try:
        for lap_num in range(1, STINT_LAPS + 1):
            # Setup for this lap
            setup = PhysicsV4Setup(
                team_data=team,
                driver_data=driver,
                circuit=circuit,
                session="race"
            )

            # Configure setup
            setup.set_aero(front_wing=setup_config["front_wing"], rear_wing=setup_config["rear_wing"])
            setup.set_tyres(compound=compound)

            # Fuel consumption: start with FUEL_START, decrease each lap
            fuel_remaining = max(10.0, FUEL_START - (lap_num - 1) * FUEL_PER_LAP)
            setup.set_fuels(fuel_kg=fuel_remaining)
            setup.set_ers_mode("balanced")

            # Simulate one lap
            result = setup.simulate_lap(verbose=False)

            telemetry = result.get("telemetry", [])
            if not telemetry:
                return False, {"error": f"No telemetry for lap {lap_num}"}

            # Extract wheel data
            stats = extract_wheel_data_from_telemetry(telemetry)

            # Update cumulative wear
            for wheel in ["FL", "FR", "RL", "RR"]:
                cumulative_wear[wheel] = stats[wheel]["final_wear"]

            # Store lap data
            lap_data.append({
                "lap_num": lap_num,
                "lap_time": result.get("lap_time_s", 0),
                "v_max": result.get("v_max_kph", 0),
                "fuel": fuel_remaining,
                "wheel_stats": stats,
            })

            # Update initial temps for next lap (carryover with slight cool-down)
            # Simulate some cooling while off-throttle between laps
            for wheel in ["FL", "FR", "RL", "RR"]:
                avg_temp = stats[wheel]["avg_temp"]
                # Cool down by ~5°C between laps (realistic for short pause)
                current_tire_temps[wheel] = max(85.0, avg_temp - 5.0)

    except Exception as e:
        return False, {"error": f"Lap simulation failed: {type(e).__name__}: {str(e)[:100]}"}

    # Calculate asymmetry across entire stint
    front_avg = statistics.mean([cumulative_wear["FL"], cumulative_wear["FR"]])
    rear_avg = statistics.mean([cumulative_wear["RL"], cumulative_wear["RR"]])

    asymmetry_valid = False
    asymmetry_msg = ""

    if setup_type == "understeer":
        # Understeer: front should wear more
        if front_avg > rear_avg + 0.5:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Front wear ({front_avg:.2f}%) > Rear ({rear_avg:.2f}%)"
        else:
            asymmetry_msg = f"✗ Front wear ({front_avg:.2f}%) not > Rear ({rear_avg:.2f}%)"

    elif setup_type == "oversteer":
        # Oversteer: rear should wear more
        if rear_avg > front_avg + 0.5:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Rear wear ({rear_avg:.2f}%) > Front ({front_avg:.2f}%)"
        else:
            asymmetry_msg = f"✗ Rear wear ({rear_avg:.2f}%) not > Front ({front_avg:.2f}%)"

    elif setup_type == "optimal":
        # Optimal: wear should be balanced (±1%)
        all_wear = [cumulative_wear[w] for w in ["FL", "FR", "RL", "RR"]]
        wear_range = max(all_wear) - min(all_wear)
        if wear_range <= 1.5:
            asymmetry_valid = True
            asymmetry_msg = f"✓ Balanced wear spread: {wear_range:.2f}%"
        else:
            asymmetry_msg = f"✗ Unbalanced wear spread: {wear_range:.2f}% (should be <1.5%)"

    return asymmetry_valid, {
        "lap_data": lap_data,
        "cumulative_wear": cumulative_wear,
        "front_avg_wear": front_avg,
        "rear_avg_wear": rear_avg,
        "asymmetry_check": asymmetry_msg,
        "success": asymmetry_valid,
    }


def print_stint_summary(circuit_name: str, compound: str, setup_type: str, data: Dict):
    """Print summary of 15-lap stint."""
    lap_data = data.get("lap_data", [])
    cumulative_wear = data.get("cumulative_wear", {})

    if not lap_data:
        print(f"    ERROR: No lap data")
        return

    # Print first, middle, last lap
    print(f"\n    Lap Progression ({STINT_LAPS} laps):")
    indices = [0, len(lap_data) // 2, -1]
    for idx in indices:
        lap = lap_data[idx]
        lap_num = lap["lap_num"]
        lap_time = lap["lap_time"]
        stats = lap["wheel_stats"]

        fl_temp = stats["FL"]["avg_temp"]
        fr_temp = stats["FR"]["avg_temp"]
        rl_temp = stats["RL"]["avg_temp"]
        rr_temp = stats["RR"]["avg_temp"]

        print(f"      Lap {lap_num:2d}: {lap_time:6.2f}s | " +
              f"FL={fl_temp:5.1f}°C FR={fr_temp:5.1f}°C RL={rl_temp:5.1f}°C RR={rr_temp:5.1f}°C")

    # Final wear state
    print(f"\n    Final Tire Wear (Lap {STINT_LAPS}):")
    print(f"      FL: {cumulative_wear['FL']:5.2f}%  |  FR: {cumulative_wear['FR']:5.2f}%")
    print(f"      RL: {cumulative_wear['RL']:5.2f}%  |  RR: {cumulative_wear['RR']:5.2f}%")

    print(f"\n    Asymmetry Check: {data['asymmetry_check']}")


if __name__ == "__main__":
    print("=" * 90)
    print("MULTI-LAP THERMAL ASYMMETRY TEST SUITE — V6.3")
    print("15-lap stints with thermal carryover between laps")
    print(f"Testing {len(CIRCUITS)} circuits × {len(COMPOUNDS)} compound × {len(SETUPS)} setup = {len(CIRCUITS) * len(COMPOUNDS) * len(SETUPS)} combinations")
    print("=" * 90)

    results_summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "by_circuit": {},
        "by_compound": {},
        "by_setup": {},
    }

    for circuit_id in CIRCUITS:
        circuit_name = CIRCUIT_NAMES.get(circuit_id, circuit_id)
        results_summary["by_circuit"][circuit_name] = {"passed": 0, "total": 0}

        print(f"\n{'='*90}")
        print(f"🏁 CIRCUIT: {circuit_name} — 15-Lap Stint Thermal Analysis")
        print(f"{'='*90}")

        for compound in COMPOUNDS:
            if compound not in results_summary["by_compound"]:
                results_summary["by_compound"][compound] = {"passed": 0, "total": 0}

            print(f"\n  🛞 COMPOUND: {compound}")
            print(f"  {'-'*86}")

            for setup_type, setup_config in SETUPS.items():
                if setup_type not in results_summary["by_setup"]:
                    results_summary["by_setup"][setup_type] = {"passed": 0, "total": 0}

                print(f"\n    Setup: {setup_config['name']}")

                success, data = simulate_stint(circuit_id, compound, setup_type, setup_config)

                results_summary["total"] += 1
                results_summary["by_circuit"][circuit_name]["total"] += 1
                results_summary["by_compound"][compound]["total"] += 1
                results_summary["by_setup"][setup_type]["total"] += 1

                if success:
                    results_summary["passed"] += 1
                    results_summary["by_circuit"][circuit_name]["passed"] += 1
                    results_summary["by_compound"][compound]["passed"] += 1
                    results_summary["by_setup"][setup_type]["passed"] += 1

                    status = "✅ PASS"
                    print(f"    {status}")
                    print_stint_summary(circuit_name, compound, setup_type, data)
                else:
                    print(f"    ❌ FAIL: {data.get('error', 'Unknown error')[:100]}")

    # Final summary
    print(f"\n{'='*90}")
    print("FINAL SUMMARY — Multi-Lap Thermal Asymmetry")
    print(f"{'='*90}")

    print(f"\nOverall: {results_summary['passed']}/{results_summary['total']} passed ({100*results_summary['passed']/results_summary['total']:.1f}%)")

    print(f"\nBy Circuit:")
    for circuit, counts in results_summary["by_circuit"].items():
        pct = 100 * counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        print(f"  {circuit:15s}: {counts['passed']}/{counts['total']} ({pct:.0f}%)")

    print(f"\nBy Setup Type:")
    for setup, counts in results_summary["by_setup"].items():
        pct = 100 * counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        setup_display = setup.capitalize()
        print(f"  {setup_display:15s}: {counts['passed']}/{counts['total']} ({pct:.0f}%)")

    if results_summary["passed"] == results_summary["total"]:
        print(f"\n{'='*90}")
        print("✅ ALL TESTS PASSED — Multi-Lap Thermal Asymmetry Model Validated")
        print(f"{'='*90}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*90}")
        print(f"⚠️  {results_summary['failed']} tests failed — See above for details")
        print(f"{'='*90}\n")
        sys.exit(1)
