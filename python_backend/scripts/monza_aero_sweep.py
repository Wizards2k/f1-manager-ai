#!/usr/bin/env python3
from __future__ import annotations
"""
Monza Aero Sweep — V5.7 Diagnostic Script

Tests a range of FW/RW combinations at Monza to identify whether High DF is
still preferred over Low DF (which would be physically incorrect — Monza is
the paradigmatic low-drag circuit).

Reports per-setup:
  - lap_time (target: Low DF < High DF by ~1-3s)
  - top_speed (Low DF should show ~5-15 km/h advantage)
  - aero efficiency hints (if available from sim result)

Usage:
    python monza_aero_sweep.py
    python monza_aero_sweep.py --circuit it-1922_monza
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill

# Aero sweep — covers the full realistic Monza setup space
SWEEPS = [
    ("MIN_DF",   4.0,  6.0,  3.0),   # Absolute minimum drag
    ("LOW_DF",   8.0, 10.0,  5.0),   # Real Monza (calibrated)
    ("LOW+",    12.0, 14.0,  7.0),   # Slightly more DF
    ("MED-",    16.0, 18.0,  9.0),   # Medium-low
    ("MED_DF",  20.0, 24.0, 10.0),   # Medium (Silverstone-like)
    ("MED+",    26.0, 30.0, 13.0),   # Medium-high
    ("HIGH_DF", 32.0, 36.0, 16.0),   # High (Monaco-like)
    ("MAX_DF",  38.0, 42.0, 18.0),   # Absolute maximum
]

CIRCUIT_ID = "it-1922_monza"

# Monza suspension (low-DF category)
SUSP_MONZA = {
    "spring_front": 25.0, "spring_rear": 33.0,
    "arb_front": 8.0, "arb_rear": 13.0,
    "ride_height_front": 10.0, "ride_height_rear": 17.0,
}


def run_setup(fw: float, rw: float, bwing: float, circuit_id: str) -> dict:
    driver = DriverSkill(
        name="Reference",
        quali_skill=1.0, race_skill=1.0,
        braking_skill=1.0, cornering_skill=1.0, throttle_skill=1.0,
        consistency=1.0,
        front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0,
    )

    setup = PhysicsV4Setup(
        driver_data=driver,
        circuit=circuit_id,
        session="qualifying",
    )
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bwing)
    setup.set_suspension(
        spring_front=SUSP_MONZA["spring_front"],
        spring_rear=SUSP_MONZA["spring_rear"],
        ARB_front=SUSP_MONZA["arb_front"],
        ARB_rear=SUSP_MONZA["arb_rear"],
        ride_height_front=SUSP_MONZA["ride_height_front"],
        ride_height_rear=SUSP_MONZA["ride_height_rear"],
    )
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound="C5")
    setup.set_ers_mode("quali_deploy")

    return setup.simulate_lap(verbose=False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Monza aero sweep diagnostic")
    parser.add_argument("--circuit", type=str, default=CIRCUIT_ID)
    args = parser.parse_args()

    circuit_id = args.circuit

    print("=" * 95)
    print(f"  MONZA AERO SWEEP — Diagnostica V5.7")
    print(f"  Circuit: {circuit_id}  |  Compound: C5  |  Fuel: 20kg  |  ERS: quali_deploy")
    print(f"  Real ref time (LOW_DF 8/10): 78.869s")
    print("=" * 95)
    print(f"  {'Name':<8} {'FW':>5} {'RW':>5} {'BW':>5} {'LapTime':>10} {'ΔLow':>8} {'TopV':>9}")
    print("-" * 95)

    results = []
    low_df_time = None

    for name, fw, rw, bwing in SWEEPS:
        r = run_setup(fw, rw, bwing, circuit_id)
        lap = r["lap_time_s"]

        top_v = r.get("v_max_kmh") or r.get("max_speed_kmh") or r.get("v_top_kmh")
        if top_v is None:
            v_arr = r.get("v_profile") or r.get("speed_profile") or []
            if len(v_arr) > 0:
                try:
                    top_v = max(v_arr) * 3.6
                except Exception:
                    top_v = None

        if name == "LOW_DF":
            low_df_time = lap

        delta = (lap - low_df_time) if low_df_time is not None else 0.0
        top_v_str = f"{top_v:7.1f}" if top_v is not None else "    n/a"

        results.append((name, fw, rw, bwing, lap, delta, top_v))
        print(f"  {name:<8} {fw:>5.1f} {rw:>5.1f} {bwing:>5.1f} {lap:>9.3f}s {delta:>+7.3f}s {top_v_str} km/h")

    print("-" * 95)
    fastest = min(results, key=lambda x: x[4])
    print(f"\n  🏁 FASTEST: {fastest[0]} ({fastest[4]:.3f}s)  FW={fastest[1]} RW={fastest[2]} BW={fastest[3]}")

    low_result = next(r for r in results if r[0] == "LOW_DF")
    high_result = next(r for r in results if r[0] == "HIGH_DF")
    real_gap = high_result[4] - low_result[4]
    print(f"  📏 LOW→HIGH gap: {real_gap:+.3f}s   (expected: +1.5 to +3.0s in real F1)")

    if fastest[0] in ("MIN_DF", "LOW_DF", "LOW+"):
        print(f"  ✅ Low-DF preferito — fisica corretta per Monza")
    else:
        print(f"  ❌ High-DF preferito ({fastest[0]}) — drag penalty insufficiente")
        print(f"      → Serve aumentare K_FACTOR wings o ridurre mu_mechanical Monza")

    print("=" * 95)
    return 0


if __name__ == "__main__":
    sys.exit(main())
