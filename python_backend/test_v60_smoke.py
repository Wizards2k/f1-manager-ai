#!/usr/bin/env python3
"""Smoke test V6.0 Phase 2 su 3 circuiti: Monaco, Silverstone, Monza."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill

DRIVER = DriverSkill(
    name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
    cornering_skill=1.0, throttle_skill=1.0, consistency=1.0,
    front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0
)

CIRCUITS = {
    "monaco": {
        "circuit_id": "mc-1929_monaco",
        "front_wing": 38.0, "rear_wing": 42.0, "bwing": 18.0,
        "spring_f": 10.0, "spring_r": 18.0, "arb_f": 25.0, "arb_r": 30.0,
        "rh_f": 16.0, "rh_r": 23.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 69.954,
    },
    "silverstone": {
        "circuit_id": "gb-1948_silverstone",
        "front_wing": 22.0, "rear_wing": 26.0, "bwing": 10.0,
        "spring_f": 25.0, "spring_r": 33.0, "arb_f": 25.0, "arb_r": 30.0,
        "rh_f": 2.0, "rh_r": 9.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 85.010,
    },
    "monza": {
        "circuit_id": "it-1922_monza",
        "front_wing": 8.0, "rear_wing": 10.0, "bwing": 5.0,
        "spring_f": 25.0, "spring_r": 33.0, "arb_f": 8.0, "arb_r": 13.0,
        "rh_f": 10.0, "rh_r": 17.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 78.869,
    },
}

def test_circuit(name, config):
    """Test un circuito."""
    print(f"\n{'='*80}")
    print(f"  {name.upper()}")
    print(f"{'='*80}")

    setup = PhysicsV4Setup(
        driver_data=DRIVER,
        circuit=config["circuit_id"],
        session="qualifying"
    )
    setup.set_aero(
        front_wing=config["front_wing"],
        rear_wing=config["rear_wing"],
        bwing=config["bwing"]
    )
    setup.set_suspension(
        spring_front=config["spring_f"],
        spring_rear=config["spring_r"],
        ARB_front=config["arb_f"],
        ARB_rear=config["arb_r"],
        ride_height_front=config["rh_f"],
        ride_height_rear=config["rh_r"]
    )
    setup.set_fuels(fuel_kg=config["fuel_kg"], fuel_mix="rich")
    setup.set_tyres(compound=config["compound"])
    setup.set_ers_mode("quali_deploy")

    try:
        r = setup.simulate_lap(verbose=True)
        lap_time = r["lap_time_s"]
        ref_time = config["ref_time"]
        error_pct = (lap_time - ref_time) / ref_time * 100

        print(f"\n  Tempo: {lap_time:.3f}s vs {ref_time:.3f}s (ref)")
        print(f"  Errore: {error_pct:+.2f}%")

        if abs(error_pct) < 5.0:
            print(f"  ✅ PASSED (target <5%)")
            return True
        else:
            print(f"  ❌ FAILED (target <5%)")
            return False

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 80)
    print("V6.0 PHASE 2 SMOKE TEST: 3 CIRCUITI")
    print("=" * 80)

    results = {}
    for name, config in CIRCUITS.items():
        results[name] = test_circuit(name, config)

    print(f"\n{'='*80}")
    print("RIEPILOGO")
    print(f"{'='*80}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name.capitalize()}")

    print(f"\nRisultato: {passed}/{total} circuiti passati")
    print("=" * 80)

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
