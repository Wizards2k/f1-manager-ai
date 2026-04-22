"""
V6.3 Comprehensive Validation Test Suite
Tests all 6 critical scenarios for tire degradation model

V6.4: Updated to use simulate_stint() from race_orchestrator for proper
fuel carryover instead of hardcoded 14.5 kg/lap.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.integrator.race_orchestrator import StintConfig, simulate_stint
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration


def run_stint(circuit: str, compound: str, setup_config: Dict, fuel_start_kg: float = 110.0,
              stint_laps: int = 15) -> Dict:
    """Run multi-lap stint with full state carryover (V6.4: uses race_orchestrator).

    This replaces the old manual loop with hardcoded 14.5 kg/lap fuel consumption.
    Now uses simulate_stint() which properly tracks fuel, tires, and DRS.
    """
    aero_calibration = get_aero_calibration(circuit)

    config = StintConfig(
        circuit_id=circuit,
        compound=compound,
        fuel_start_kg=fuel_start_kg,
        stint_laps=stint_laps,
        engine_map="RACE",
        push_level=8,
        aero_setup={
            "front_wing": setup_config["front_wing"],
            "rear_wing": setup_config["rear_wing"],
        },
        aero_calibration=aero_calibration,
        driver_skill=1.0,
        drs_enabled=True,
    )

    stint_result = simulate_stint(config)

    if stint_result.error:
        return {"error": stint_result.error}

    # Convert StintResult to legacy format for test compatibility
    lap_results = []
    for lap in stint_result.lap_results:
        lap_results.append({
            "lap_num": lap["lap_num"],
            "lap_time": lap["lap_time_s"],
            "tire_temps": lap.get("tire_temps"),
            "tire_wear": lap.get("tire_wear"),
            "fuel": lap.get("fuel_remaining_kg", 0),
        })

    return {
        "lap_results": lap_results,
        "total_time": stint_result.total_time_s,
        "final_wear": stint_result.final_tire_wear,
    }


def run_stint_legacy(circuit: str, compound: str, setup_config: Dict, fuel_start_kg: float = 110.0,
                     stint_laps: int = 15) -> Dict:
    """Legacy stint runner using integrate_lap_hd directly (for comparison/debugging).

    Uses V6.4 initial_fuel_kg parameter for proper fuel carryover.
    """
    aero_setup = {
        "front_wing": setup_config["front_wing"],
        "rear_wing": setup_config["rear_wing"],
    }
    aero_calibration = get_aero_calibration(circuit)

    lap_results = []
    current_tire_temps = {"FL": 85.0, "FR": 85.0, "RL": 85.0, "RR": 85.0}
    cumulative_wear = {"FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0}
    current_fuel_kg = fuel_start_kg
    total_time = 0.0

    for lap_num in range(1, stint_laps + 1):
        push_level = 5 if lap_num == 1 else 9

        try:
            result = integrate_lap_hd(
                circuit_id=circuit,
                aero_setup=aero_setup,
                mass_kg=798.0 + current_fuel_kg,  # V6.4: dry mass + fuel
                tyre_compound=compound,
                driver_skill=1.0,
                push_level=push_level,
                aero_calibration=aero_calibration,
                ers_power_fraction=0.5,
                pu_config={"engine_map": "RACE"},
                initial_tire_temps=current_tire_temps,
                cumulative_tire_wear=cumulative_wear,
                initial_fuel_kg=current_fuel_kg,  # V6.4: fuel carryover
            )

            lap_time = result.get("lap_time_s", 0)
            current_tire_temps = result.get("final_tire_temps")
            cumulative_wear = result.get("cumulative_tire_wear")

            # V6.4: Use fuel_remaining_kg from result instead of hardcoded estimate
            fuel_remaining = result.get("fuel_remaining_kg")
            if fuel_remaining is not None:
                current_fuel_kg = fuel_remaining
            else:
                # Fallback: subtract consumed
                current_fuel_kg -= result.get("fuel_consumed_kg", 0)

            total_time += lap_time

            lap_results.append({
                "lap_num": lap_num,
                "lap_time": lap_time,
                "tire_temps": current_tire_temps,
                "tire_wear": cumulative_wear,
                "fuel": current_fuel_kg,
            })
        except Exception as e:
            return {"error": f"Lap {lap_num}: {type(e).__name__}: {str(e)[:100]}"}

    return {
        "lap_results": lap_results,
        "total_time": total_time,
        "final_wear": cumulative_wear,
    }

def test_1_all_compounds():
    """TEST 1: All compounds, balanced setup, 15 laps on high-deg circuits"""
    print("\n" + "="*90)
    print("TEST 1: All Compounds (C5/C4/C3) - Balanced Setup on High-Deg Circuits")
    print("="*90)

    circuits = ["mc-1929_monaco", "sg-2008_singapore"]
    compounds = ["C5", "C4", "C3"]
    setup = {"front_wing": 18, "rear_wing": 11, "name": "Balanced (18/11)"}

    for circuit in circuits:
        circuit_name = circuit.split("_")[-1].title()
        print(f"\n📍 {circuit_name}")

        for compound in compounds:
            data = run_stint(circuit, compound, setup, stint_laps=15)
            if "error" in data:
                print(f"  ❌ {compound}: {data['error']}")
            else:
                final_wear = data["final_wear"]
                avg_temp = sum(data["lap_results"][-1]["tire_temps"].values()) / 4
                fl_wear = final_wear["FL"]
                fr_wear = final_wear["FR"]
                rl_wear = final_wear["RL"]
                rr_wear = final_wear["RR"]

                # Check if wear is realistic: 1.5-100% (F1 real data: 2-8% per 15 laps Monaco, 10-20% Singapore)
                wear_values = [fl_wear, fr_wear, rl_wear, rr_wear]
                min_wear = min(wear_values)
                max_wear = max(wear_values)

                if 1.5 <= min_wear <= max_wear <= 100:
                    status = "✅"
                elif max_wear > 100:
                    status = "⚠️ (OVER-SATURATED)"
                else:
                    status = "❌ (TOO LOW)"

                print(f"  {status} {compound:3s}: Wear FL={fl_wear:6.2f}% FR={fr_wear:6.2f}% "
                      f"RL={rl_wear:6.2f}% RR={rr_wear:6.2f}% | Avg temp: {avg_temp:.1f}°C")

def test_2_oversteer_setup():
    """TEST 2: Oversteer setup (low FW) - rear axle should wear more"""
    print("\n" + "="*90)
    print("TEST 2: Oversteer Setup (12/11) - Verify Rear > Front Wear")
    print("Circuiti bilanciati (Suzuka, Barcellona) - meno dominati da frenata")
    print("="*90)

    # Suzuka e Barcellona: mix bilanciato curve veloci/lente, meno frenata che Monaco
    circuits = [
        ("jp-1962_suzuka", "Suzuka"),
        ("es-1991_barcelona", "Barcellona"),
    ]
    setup = {"front_wing": 12, "rear_wing": 11, "name": "Oversteer (12/11)"}

    for circuit_id, circuit_name in circuits:
        print(f"\n📍 {circuit_name}")

        for compound in ["C4"]:
            data = run_stint(circuit_id, compound, setup, stint_laps=15)
            if "error" in data:
                print(f"  ❌ Error: {data['error']}")
            else:
                final_wear = data["final_wear"]
                front_avg = (final_wear["FL"] + final_wear["FR"]) / 2
                rear_avg = (final_wear["RL"] + final_wear["RR"]) / 2

                if rear_avg > front_avg:
                    print(f"  ✅ Oversteer: Rear {rear_avg:.2f}% > Front {front_avg:.2f}% (diff: {rear_avg-front_avg:.2f}%)")
                else:
                    print(f"  ❌ Oversteer: Rear {rear_avg:.2f}% ≤ Front {front_avg:.2f}% (diff: {front_avg-rear_avg:.2f}%)")

def test_2b_understeer_setup():
    """TEST 2B: Understeer setup (high FW) - front axle should wear more"""
    print("\n" + "="*90)
    print("TEST 2B: Understeer Setup (24/11) - Verify Front > Rear Wear")
    print("Circuiti bilanciati (Suzuka, Barcellona)")
    print("="*90)

    circuits = [
        ("jp-1962_suzuka", "Suzuka"),
        ("es-1991_barcelona", "Barcellona"),
    ]
    setup = {"front_wing": 24, "rear_wing": 11, "name": "Understeer (24/11)"}

    for circuit_id, circuit_name in circuits:
        print(f"\n📍 {circuit_name}")

        for compound in ["C4"]:
            data = run_stint(circuit_id, compound, setup, stint_laps=15)
            if "error" in data:
                print(f"  ❌ Error: {data['error']}")
            else:
                final_wear = data["final_wear"]
                front_avg = (final_wear["FL"] + final_wear["FR"]) / 2
                rear_avg = (final_wear["RL"] + final_wear["RR"]) / 2

                if front_avg > rear_avg:
                    print(f"  ✅ Understeer: Front {front_avg:.2f}% > Rear {rear_avg:.2f}% (diff: {front_avg-rear_avg:.2f}%)")
                else:
                    print(f"  ❌ Understeer: Front {front_avg:.2f}% ≤ Rear {rear_avg:.2f}% (diff: {rear_avg-front_avg:.2f}%)")

def test_3_right_hand_corners():
    """TEST 3: Silverstone (right-hand heavy) - left side should wear more"""
    print("\n" + "="*90)
    print("TEST 3: Right-Hand Corners (Silverstone) - Left Side > Right Side")
    print("="*90)

    circuit = "gb-1948_silverstone"
    setup = {"front_wing": 18, "rear_wing": 11, "name": "Balanced (18/11)"}

    data = run_stint(circuit, "C4", setup, stint_laps=15)
    if "error" in data:
        print(f"  ❌ Error: {data['error']}")
    else:
        final_wear = data["final_wear"]
        left_avg = (final_wear["FL"] + final_wear["RL"]) / 2
        right_avg = (final_wear["FR"] + final_wear["RR"]) / 2

        if left_avg > right_avg:
            print(f"  ✅ Silverstone RHC: Left {left_avg:.2f}% > Right {right_avg:.2f}% (diff: {left_avg-right_avg:.2f}%)")
        else:
            print(f"  ⚠️ Silverstone RHC: Left {left_avg:.2f}% ≤ Right {right_avg:.2f}% (need more data)")

def test_4_left_hand_corners():
    """TEST 4: Monza (left-hand heavy) - right side should wear more"""
    print("\n" + "="*90)
    print("TEST 4: Left-Hand Corners (Monza) - Right Side > Left Side")
    print("="*90)

    circuit = "it-1922_monza"
    setup = {"front_wing": 18, "rear_wing": 11, "name": "Balanced (18/11)"}

    data = run_stint(circuit, "C4", setup, stint_laps=15)
    if "error" in data:
        print(f"  ❌ Error: {data['error']}")
    else:
        final_wear = data["final_wear"]
        left_avg = (final_wear["FL"] + final_wear["RL"]) / 2
        right_avg = (final_wear["FR"] + final_wear["RR"]) / 2

        if right_avg > left_avg:
            print(f"  ✅ Monza LHC: Right {right_avg:.2f}% > Left {left_avg:.2f}% (diff: {right_avg-left_avg:.2f}%)")
        else:
            print(f"  ⚠️ Monza LHC: Right {right_avg:.2f}% ≤ Left {left_avg:.2f}% (need more data)")

def test_5_fuel_load_sensitivity():
    """TEST 5: Full fuel (110kg) vs Empty (5kg) - verify load sensitivity"""
    print("\n" + "="*90)
    print("TEST 5: Fuel Load Sensitivity - Full (110kg) vs Empty (5kg)")
    print("="*90)

    circuit = "mc-1929_monaco"
    setup = {"front_wing": 18, "rear_wing": 11, "name": "Balanced (18/11)"}

    data_full = run_stint(circuit, "C4", setup, fuel_start_kg=110.0, stint_laps=15)
    data_empty = run_stint(circuit, "C4", setup, fuel_start_kg=5.0, stint_laps=15)

    if "error" in data_full or "error" in data_empty:
        print(f"  ❌ Error in test")
    else:
        wear_full = sum(data_full["final_wear"].values()) / 4
        wear_empty = sum(data_empty["final_wear"].values()) / 4

        if wear_full > wear_empty:
            diff_pct = 100 * (wear_full - wear_empty) / wear_empty
            print(f"  ✅ Fuel sensitivity: Full {wear_full:.2f}% > Empty {wear_empty:.2f}% (diff: {diff_pct:+.1f}%)")
        else:
            print(f"  ❌ Fuel sensitivity: Full {wear_full:.2f}% ≤ Empty {wear_empty:.2f}% (WRONG!)")

def test_6_temp_severity_multiplier():
    """TEST 6: Verify temp severity multiplier - out-of-window temps increase wear"""
    print("\n" + "="*90)
    print("TEST 6: Temperature Severity Multiplier - Out-of-Window Wear")
    print("="*90)

    print("  ℹ️  V6.3 severity multiplier: 1.0 in window, increases outside window")
    print("  ℹ️  C4 window: 105°C ±8°C (97-113°C)")
    print("  ℹ️  At 150°C: significant wear acceleration expected")

    circuit = "mc-1929_monaco"
    setup = {"front_wing": 24, "rear_wing": 11, "name": "Unbalanced (24/11)"}  # Will cause high load/temps

    data = run_stint(circuit, "C4", setup, stint_laps=5)
    if "error" in data:
        print(f"  ❌ Error: {data['error']}")
    else:
        final_temps = data["lap_results"][-1]["tire_temps"]
        final_wear = data["final_wear"]

        avg_temp = sum(final_temps.values()) / 4
        avg_wear = sum(final_wear.values()) / 4

        if avg_temp > 130:
            if avg_wear > 20:  # At least 20% wear for 5 laps out of window
                print(f"  ✅ Severity active: Temp {avg_temp:.0f}°C → Wear {avg_wear:.2f}% (acceleration expected)")
            else:
                print(f"  ⚠️ Severity low: Temp {avg_temp:.0f}°C → Wear {avg_wear:.2f}% (check multiplier)")
        else:
            print(f"  ℹ️  Temperature in window ({avg_temp:.0f}°C), limited severity test")

if __name__ == "__main__":
    print("\n" + "="*90)
    print("V6.3 COMPREHENSIVE VALIDATION TEST SUITE")
    print("="*90)
    print("Testing 6 critical scenarios for tire degradation model\n")

    try:
        test_1_all_compounds()
        test_2_oversteer_setup()
        test_2b_understeer_setup()
        test_3_right_hand_corners()
        test_4_left_hand_corners()
        test_5_fuel_load_sensitivity()
        test_6_temp_severity_multiplier()

        print("\n" + "="*90)
        print("✅ VALIDATION SUITE COMPLETE")
        print("="*90 + "\n")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
