#!/usr/bin/env python3
"""Test Phase 2 di V6.0: braking logic semplificato con v_max_corner + brake_needed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.push_penalty import compute_push_penalty

DRIVER = DriverSkill(
    name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
    cornering_skill=1.0, throttle_skill=1.0, consistency=1.0,
    front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0
)

def test_monaco():
    """Test Monaco con V6.0 Phase 2."""
    print("=" * 80)
    print("TEST V6.0 PHASE 2: MONACO")
    print("=" * 80)

    # Setup calibrato
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit="mc-1929_monaco", session="qualifying")
    setup.set_aero(front_wing=38.0, rear_wing=42.0, bwing=18.0)
    setup.set_suspension(
        spring_front=10.0, spring_rear=18.0,
        ARB_front=25.0, ARB_rear=30.0,
        ride_height_front=16.0, ride_height_rear=23.0
    )
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound="C6")
    setup.set_ers_mode("quali_deploy")

    try:
        r = setup.simulate_lap(verbose=True)
        lap_time = r["lap_time_s"]
        ref_time = 69.954
        error_pct = (lap_time - ref_time) / ref_time * 100

        print("\n" + "=" * 80)
        print(f"RISULTATI MONACO")
        print(f"  Tempo: {lap_time:.3f}s vs {ref_time:.3f}s (ref)")
        print(f"  Errore: {error_pct:+.2f}%")

        if abs(error_pct) < 5.0:
            print(f"  ✅ PHASE 2 TEST PASSED (target <5%)")
        else:
            print(f"  ❌ PHASE 2 TEST FAILED (target <5%)")

        print("=" * 80)
        return abs(error_pct) < 5.0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_monaco()
    sys.exit(0 if success else 1)
