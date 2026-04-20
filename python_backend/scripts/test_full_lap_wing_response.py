#!/usr/bin/env python3
"""Debug: Full lap simulation with different wing angles."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill

def test_full_lap_response():
    """Test if full lap simulation responds correctly to wing angle changes."""

    print("\n" + "="*80)
    print("FULL LAP SIMULATION: WING ANGLE RESPONSE TEST")
    print("="*80)

    # Test on Monaco (tight circuit where downforce matters)
    circuit_id = "mc-1929_monaco"

    configs = [
        ("LOW", 10, 12),
        ("CAL", 16, 18),
        ("HIGH", 22, 24),
    ]

    print(f"Test circuit: Monaco")
    print(f"Driver skill: 1.0 (baseline)")
    print("-"*80)
    print(f"{'Setup':<10} {'FW':<8} {'RW':<8} {'Lap Time (s)':<20} {'Change vs CAL':<15}")
    print("-"*80)

    driver = DriverSkill(
        name="Test",
        quali_skill=1.0,
        race_skill=1.0,
        braking_skill=1.0,
        cornering_skill=1.0,
        throttle_skill=1.0,
        consistency=1.0,
        front_wing_offset=0,
        rear_wing_offset=0,
        brake_bias_offset=0.0
    )
    results = {}

    # Run all simulations first
    for name, fw, rw in configs:
        setup = PhysicsV4Setup(driver_data=driver, circuit=circuit_id, session="qualifying")
        setup.set_aero(front_wing=fw, rear_wing=rw, bwing=10.0)
        setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
        setup.set_tyres(compound="C2")
        setup.set_ers_mode("quali_deploy")

        result = setup.simulate_lap(verbose=False)
        lap_time = result["lap_time_s"]
        results[name] = (fw, rw, lap_time)

    # Display results with comparisons
    cal_time = results["CAL"][2]
    for name, fw, rw in configs:
        lap_time = results[name][2]

        print(f"{name:<10} {fw:<8.1f} {rw:<8.1f} {lap_time:<20.3f}", end="")

        if name == "CAL":
            print(f"{'BASELINE':<15}")
        else:
            delta_s = lap_time - cal_time
            pct = 100 * delta_s / cal_time
            print(f"{delta_s:+.3f}s ({pct:+.2f}%)")

    print("-"*80)

    # Analyze
    low_time = results["LOW"][2]
    high_time = results["HIGH"][2]

    print("\nANALYSIS:")
    print(f"  LOW:  {low_time:.3f}s")
    print(f"  CAL:  {cal_time:.3f}s (baseline)")
    print(f"  HIGH: {high_time:.3f}s")

    # Expected: LOW > CAL > HIGH (lower downforce → slower)
    if low_time > cal_time and cal_time > high_time:
        print("  ✅ CORRECT: More wing → faster lap time")
    elif low_time < cal_time and cal_time < high_time:
        print("  ❌ INVERTED: More wing → SLOWER lap time (BUG FOUND!)")
    else:
        print("  ⚠️ UNEXPECTED PATTERN")

    print("="*80 + "\n")

if __name__ == "__main__":
    test_full_lap_response()
