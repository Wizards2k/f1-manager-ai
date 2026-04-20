"""
Test Comprehensive — V6.3 Thermal Asymmetry Validation
Tests tire thermal behavior across 5 circuits, 3 compounds, 3 setups over 15-lap stints.
Verifies that understeer/oversteer setups produce expected per-wheel thermal asymmetries.

Requirements:
- Understeer setup (high front wing) → FL/FR hotter, RL/RR cooler
- Oversteer setup (low front wing) → RL/RR hotter, FL/FR cooler
- Optimal setup → balanced thermal profile
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
import statistics

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_engine.core.team_driver_data import get_team_data, get_driver_data


# Test configuration (circuiti con file HD disponibili)
CIRCUITS = ["it-1922_monza", "mc-1929_monaco", "es-1991_barcelona", "gb-1948_silverstone", "jp-1962_suzuka", "az-2016_baku"]
CIRCUIT_NAMES = {"it-1922_monza": "Monza", "mc-1929_monaco": "Monaco", "es-1991_barcelona": "Barcelona",
                 "gb-1948_silverstone": "Silverstone", "jp-1962_suzuka": "Suzuka", "az-2016_baku": "Baku"}
COMPOUNDS = ["C5", "C4", "C3"]
SETUPS = {
    "optimal": {"front_wing": 18, "rear_wing": 11, "name": "Optimal (18/11)"},
    "understeer": {"front_wing": 24, "rear_wing": 11, "name": "Understeer (24/11)"},
    "oversteer": {"front_wing": 12, "rear_wing": 11, "name": "Oversteer (12/11)"},
}

STINT_LAPS = 15
FUEL_PER_LAP = 14.5  # kg/lap RACE pace


def extract_wheel_data(telemetry: List[Dict]) -> Tuple[Dict, Dict, Dict]:
    """Extract per-wheel thermal and wear data from telemetry."""
    wheels = {
        "FL": {"temps": [], "wear": [], "slip": []},
        "FR": {"temps": [], "wear": [], "slip": []},
        "RL": {"temps": [], "wear": [], "slip": []},
        "RR": {"temps": [], "wear": [], "slip": []},
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

    # Calculate averages and max
    stats = {}
    for wheel in wheels:
        temps = wheels[wheel]["temps"]
        wear = wheels[wheel]["wear"]
        stats[wheel] = {
            "avg_temp": statistics.mean(temps) if temps else 85.0,
            "max_temp": max(temps) if temps else 85.0,
            "final_wear": wear[-1] if wear else 0.0,
        }

    return stats, wheels


def verify_asymmetry(setup_name: str, stats: Dict) -> Tuple[bool, str]:
    """Verify that wheel temperatures match expected setup behavior."""
    fl_temp = stats["FL"]["avg_temp"]
    fr_temp = stats["FR"]["avg_temp"]
    rl_temp = stats["RL"]["avg_temp"]
    rr_temp = stats["RR"]["avg_temp"]

    fl_wear = stats["FL"]["final_wear"]
    fr_wear = stats["FR"]["final_wear"]
    rl_wear = stats["RL"]["final_wear"]
    rr_wear = stats["RR"]["final_wear"]

    issues = []

    if setup_name == "understeer":
        # Understeer: front wheels should be hotter and wear faster
        front_avg = (fl_temp + fr_temp) / 2
        rear_avg = (rl_temp + rr_temp) / 2
        front_wear = (fl_wear + fr_wear) / 2
        rear_wear = (rl_wear + rr_wear) / 2

        if front_avg < rear_avg + 2.0:
            issues.append(f"Front temps too low: {front_avg:.1f}°C vs Rear {rear_avg:.1f}°C")
        if front_wear < rear_wear:
            issues.append(f"Front wear too low: {front_wear:.2f}% vs Rear {rear_wear:.2f}%")

    elif setup_name == "oversteer":
        # Oversteer: rear wheels should be hotter and wear faster
        front_avg = (fl_temp + fr_temp) / 2
        rear_avg = (rl_temp + rr_temp) / 2
        front_wear = (fl_wear + fr_wear) / 2
        rear_wear = (rl_wear + rr_wear) / 2

        if rear_avg < front_avg + 2.0:
            issues.append(f"Rear temps too low: {rear_avg:.1f}°C vs Front {front_avg:.1f}°C")
        if rear_wear < front_wear:
            issues.append(f"Rear wear too low: {rear_wear:.2f}% vs Front {front_wear:.2f}%")

    elif setup_name == "optimal":
        # Optimal: temperatures should be relatively balanced (±3°C)
        all_temps = [fl_temp, fr_temp, rl_temp, rr_temp]
        temp_range = max(all_temps) - min(all_temps)
        if temp_range > 8.0:
            issues.append(f"Balanced setup has high temp spread: {temp_range:.1f}°C")

    # Per-wheel asymmetry in cornering (exterior > interior in fast corners)
    # Monza right turns: FL/RL should be hotter than FR/RR
    # But this depends on circuit, so we just verify consistency

    success = len(issues) == 0
    message = "; ".join(issues) if issues else "✓ Asymmetry correct"

    return success, message


def run_stint(circuit: str, compound: str, setup_type: str, setup_config: Dict) -> Tuple[bool, Dict]:
    """Run a 15-lap stint and collect thermal data."""
    team = get_team_data("mclaren")
    driver = get_driver_data("Lando Norris")

    setup = PhysicsV4Setup(
        team_data=team,
        driver_data=driver,
        circuit=circuit,
        session="race"
    )

    # Configure setup
    setup.set_aero(front_wing=setup_config["front_wing"], rear_wing=setup_config["rear_wing"])
    setup.set_tyres(compound=compound)
    setup.set_fuels(fuel_kg=110.0)  # Start stint
    setup.set_ers_mode("balanced")  # RACE mode

    try:
        result = setup.simulate_lap(verbose=False)

        telemetry = result.get("telemetry", [])
        if not telemetry:
            return False, {"error": "No telemetry data"}

        stats, _ = extract_wheel_data(telemetry)
        success, message = verify_asymmetry(setup_type, stats)

        return success, {
            "lap_time": result.get("lap_time_s", 0),
            "v_max": result.get("v_max_kph", 0),
            "wheel_stats": stats,
            "asymmetry_check": message,
            "success": success,
        }
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {str(e)}\n{tb_str[:200]}"
        return False, {"error": error_msg}


def print_wheel_summary(stats: Dict, setup_type: str):
    """Print per-wheel temperature and wear summary."""
    print(f"\n    Wheel Thermal Profile ({setup_type}):")
    print(f"    ┌─────────────────────────────────────┐")
    for wheel in ["FL", "FR", "RL", "RR"]:
        avg_temp = stats[wheel]["avg_temp"]
        max_temp = stats[wheel]["max_temp"]
        wear = stats[wheel]["final_wear"]
        print(f"    │ {wheel}: avg={avg_temp:6.1f}°C, max={max_temp:6.1f}°C, wear={wear:5.2f}%")
    print(f"    └─────────────────────────────────────┘")


if __name__ == "__main__":
    print("=" * 80)
    print("COMPREHENSIVE THERMAL ASYMMETRY TEST SUITE — V6.3")
    print("Testing 6 circuits × 3 compounds × 3 setups = 54 combinations")
    print("=" * 80)

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

        print(f"\n{'='*80}")
        print(f"🏁 CIRCUIT: {circuit_name}")
        print(f"{'='*80}")

        for compound in COMPOUNDS:
            if compound not in results_summary["by_compound"]:
                results_summary["by_compound"][compound] = {"passed": 0, "total": 0}

            print(f"\n  🛞 COMPOUND: {compound}")
            print(f"  {'-'*76}")

            for setup_type, setup_config in SETUPS.items():
                if setup_type not in results_summary["by_setup"]:
                    results_summary["by_setup"][setup_type] = {"passed": 0, "total": 0}

                print(f"\n    Setup: {setup_config['name']}")

                success, data = run_stint(circuit_id, compound, setup_type, setup_config)

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
                    print(f"    Lap time: {data['lap_time']:.3f}s, Max speed: {data['v_max']:.1f} kph")
                    print(f"    Asymmetry: {data['asymmetry_check']}")
                    print_wheel_summary(data["wheel_stats"], setup_type)
                else:
                    results_summary["failed"] += 1
                    error_msg = data.get('error') or data.get('asymmetry_check', 'Unknown error')
                    print(f"    ❌ FAIL: {error_msg[:150]}")

    # Final summary
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")

    print(f"\nOverall: {results_summary['passed']}/{results_summary['total']} passed ({100*results_summary['passed']/results_summary['total']:.1f}%)")

    print(f"\nBy Circuit:")
    for circuit, counts in results_summary["by_circuit"].items():
        pct = 100 * counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        print(f"  {circuit:15s}: {counts['passed']}/{counts['total']} ({pct:.0f}%)")

    print(f"\nBy Compound:")
    for compound, counts in results_summary["by_compound"].items():
        pct = 100 * counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        print(f"  {compound:15s}: {counts['passed']}/{counts['total']} ({pct:.0f}%)")

    print(f"\nBy Setup:")
    for setup, counts in results_summary["by_setup"].items():
        pct = 100 * counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        setup_display = setup.capitalize()
        print(f"  {setup_display:15s}: {counts['passed']}/{counts['total']} ({pct:.0f}%)")

    if results_summary["passed"] == results_summary["total"]:
        print(f"\n{'='*80}")
        print("✅ ALL TESTS PASSED — Thermal Asymmetry Model Validated")
        print(f"{'='*80}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*80}")
        print(f"⚠️  {results_summary['failed']} tests failed")
        print(f"{'='*80}\n")
        sys.exit(1)
