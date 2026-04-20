#!/usr/bin/env python3
"""Test fallback a V5.7 (disabilita V6.0) per verificare baseline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd

DRIVER = DriverSkill(
    name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
    cornering_skill=1.0, throttle_skill=1.0, consistency=1.0,
    front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0
)

def test_fallback():
    """Test con V6.0 disabilitato (passare None ai nuovi parametri)."""
    print("="*80)
    print("TEST FALLBACK (V6.0 disabilitato = V5.7 baseline)")
    print("="*80)

    # Simula una call diretta a integrate_lap_hd senza v_max_corner_array/brake_needed
    # Questo testa il fallback comportamento
    result = integrate_lap_hd(
        circuit_id="mc-1929_monaco",
        aero_setup={"front_wing": 38.0, "rear_wing": 42.0, "b_wing": 18.0},
        mass_kg=798.0,
        tyre_compound="C6",
        driver_skill=1.0,
        verbose=True,
        mu_override={"C6": 2.33, "C5": 2.26, "C4": 2.1, "C3": 1.96},
        max_brake_decel_g_override=4.8,
        max_lateral_g_override=8.0,
        suspension_setup={
            "spring_front": 10.0, "spring_rear": 18.0,
            "ARB_front": 25.0, "ARB_rear": 30.0,
            "ride_height_front": 0.016, "ride_height_rear": 0.023,
        },
        ers_power_fraction=1.0,
        reference_pull_strength=0.0,
        pu_lookup_blend=0.0,
        pu_config={"engine_map": "QUALIFY"},
    )

    lap_time = result["lap_time_s"]
    ref_time = 69.954
    error_pct = (lap_time - ref_time) / ref_time * 100

    print(f"\nTempo: {lap_time:.3f}s vs {ref_time:.3f}s (ref)")
    print(f"Errore: {error_pct:+.2f}%")
    print("="*80)

if __name__ == "__main__":
    test_fallback()
